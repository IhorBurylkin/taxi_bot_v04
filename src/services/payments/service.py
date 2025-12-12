# src/services/payments/service.py
"""
Бизнес-логика платежей.
Поддержка Telegram Stars (XTR), балансы, возвраты.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from src.shared.events.payment_events import (
    PaymentRequested,
    PaymentSucceeded,
    PaymentFailed,
    RefundRequested,
    RefundCompleted,
)
from src.shared.models.payment import (
    PaymentDTO,
    PaymentStatus,
    PaymentMethod,
    PaymentCreateRequest,
    StarsInvoiceRequest,
    StarsPaymentResult,
)

if TYPE_CHECKING:
    from src.infra.database import DatabaseManager
    from src.infra.redis_client import RedisClient
    from src.infra.event_bus import EventBus


class PaymentService:
    """
    Сервис управления платежами.
    
    Ответственности:
    - Создание и обработка платежей
    - Интеграция с Telegram Stars (XTR)
    - Расчёт комиссий
    - Управление балансами водителей
    - Возвраты средств
    """
    
    def __init__(
        self,
        db: "DatabaseManager",
        redis: "RedisClient",
        event_bus: "EventBus",
    ) -> None:
        self.db = db
        self.redis = redis
        self.event_bus = event_bus
        
        # Константы из конфига (будут загружаться через DI)
        self.platform_commission_percent: float = 15.0
        self.stars_to_usd_rate: float = 0.013
        self.min_balance_stars: int = 100
        self.withdrawal_min_stars: int = 500
    
    # === СОЗДАНИЕ ПЛАТЕЖА ===
    
    async def create_payment(self, request: PaymentCreateRequest) -> PaymentDTO:
        """
        Создать новый платёж.
        
        1. Генерирует UUID
        2. Рассчитывает комиссии
        3. Сохраняет в БД
        4. Публикует событие PaymentRequested
        """
        payment_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Расчёт комиссии и выплаты водителю
        platform_commission = request.amount * (self.platform_commission_percent / 100)
        driver_payout = request.amount - platform_commission
        
        # Конвертация в Stars если нужно
        amount_stars = None
        if request.method == PaymentMethod.STARS:
            amount_stars = self._convert_to_stars(request.amount)
        
        payment = PaymentDTO(
            id=payment_id,
            trip_id=request.trip_id,
            payer_id=request.payer_id,
            payee_id=request.payee_id,
            amount=request.amount,
            currency=request.currency,
            amount_stars=amount_stars,
            method=request.method,
            status=PaymentStatus.PENDING,
            platform_commission=platform_commission,
            driver_payout=driver_payout,
            created_at=now,
        )
        
        # Сохранение в БД
        await self._save_payment(payment)
        
        # Публикация события
        event = PaymentRequested(
            payment_id=payment_id,
            trip_id=request.trip_id,
            payer_id=request.payer_id,
            payee_id=request.payee_id,
            amount=request.amount,
            currency=request.currency,
            payment_method=request.method.value,
        )
        await self.event_bus.publish("payment.requested", event.model_dump())
        
        return payment
    
    # === ОБРАБОТКА ОПЛАТЫ ===
    
    async def process_stars_payment(
        self,
        payment_id: str,
        result: StarsPaymentResult,
    ) -> PaymentDTO:
        """
        Обработать результат оплаты через Telegram Stars.
        
        Вызывается после получения успешного pre_checkout или successful_payment
        от Telegram.
        """
        payment = await self.get_payment(payment_id)
        if not payment:
            raise ValueError(f"Платёж {payment_id} не найден")
        
        if result.success:
            # Обновляем статус на SUCCEEDED
            payment.status = PaymentStatus.SUCCEEDED
            payment.telegram_payment_charge_id = result.telegram_payment_charge_id
            payment.provider_payment_charge_id = result.provider_payment_charge_id
            payment.paid_at = datetime.utcnow()
            
            await self._update_payment(payment)
            
            # Начисляем баланс водителю
            await self._credit_driver_balance(
                driver_id=payment.payee_id,
                amount_stars=payment.amount_stars or 0,
                payment_id=payment_id,
            )
            
            # Публикуем событие успеха
            event = PaymentSucceeded(
                payment_id=payment_id,
                trip_id=payment.trip_id,
                payer_id=payment.payer_id,
                payee_id=payment.payee_id,
                amount=payment.amount,
                currency=payment.currency,
                platform_commission=payment.platform_commission,
                driver_payout=payment.driver_payout,
                telegram_payment_charge_id=result.telegram_payment_charge_id,
            )
            await self.event_bus.publish("payment.succeeded", event.model_dump())
        else:
            # Обновляем статус на FAILED
            payment.status = PaymentStatus.FAILED
            await self._update_payment(payment)
            
            # Публикуем событие ошибки
            event = PaymentFailed(
                payment_id=payment_id,
                trip_id=payment.trip_id,
                payer_id=payment.payer_id,
                error_code="payment_failed",
                error_message="Telegram Stars payment failed",
            )
            await self.event_bus.publish("payment.failed", event.model_dump())
        
        return payment
    
    # === ВОЗВРАТЫ ===
    
    async def request_refund(
        self,
        payment_id: str,
        reason: str | None = None,
        requested_by: int = 0,
    ) -> str:
        """
        Запросить возврат средств.
        
        Возвращает refund_id.
        """
        payment = await self.get_payment(payment_id)
        if not payment:
            raise ValueError(f"Платёж {payment_id} не найден")
        
        if payment.status != PaymentStatus.SUCCEEDED:
            raise ValueError(f"Нельзя вернуть платёж со статусом {payment.status}")
        
        refund_id = str(uuid.uuid4())
        
        # Публикуем событие запроса на возврат
        event = RefundRequested(
            refund_id=refund_id,
            payment_id=payment_id,
            trip_id=payment.trip_id,
            amount=payment.amount,
            currency=payment.currency,
            reason=reason,
            requested_by=requested_by,
        )
        await self.event_bus.publish("refund.requested", event.model_dump())
        
        return refund_id
    
    async def complete_refund(
        self,
        refund_id: str,
        payment_id: str,
        telegram_refund_id: str | None = None,
    ) -> None:
        """
        Завершить возврат средств.
        
        Вызывается после успешного refundStarPayment в Telegram.
        """
        payment = await self.get_payment(payment_id)
        if not payment:
            raise ValueError(f"Платёж {payment_id} не найден")
        
        # Обновляем статус
        payment.status = PaymentStatus.REFUNDED
        await self._update_payment(payment)
        
        # Списываем с баланса водителя
        await self._debit_driver_balance(
            driver_id=payment.payee_id,
            amount_stars=payment.amount_stars or 0,
            reason=f"refund_{refund_id}",
        )
        
        # Публикуем событие завершения возврата
        event = RefundCompleted(
            refund_id=refund_id,
            payment_id=payment_id,
            amount=payment.amount,
            currency=payment.currency,
            telegram_refund_id=telegram_refund_id,
        )
        await self.event_bus.publish("refund.completed", event.model_dump())
    
    # === БАЛАНСЫ ===
    
    async def get_driver_balance(self, driver_id: int) -> dict:
        """
        Получить баланс водителя.
        
        Возвращает:
        - total_earned: общий заработок (Stars)
        - available: доступно для вывода
        - pending: ожидает подтверждения
        - withdrawn: выведено
        """
        # Пытаемся из кэша
        cache_key = f"driver_balance:{driver_id}"
        cached = await self.redis.get(cache_key)
        if cached:
            return cached
        
        # Из БД
        balance = await self._get_driver_balance_from_db(driver_id)
        
        # Кэшируем на 5 минут
        await self.redis.set(cache_key, balance, ttl=300)
        
        return balance
    
    async def get_payment(self, payment_id: str) -> PaymentDTO | None:
        """Получить платёж по ID."""
        # Пытаемся из кэша
        cache_key = f"payment:{payment_id}"
        cached = await self.redis.get(cache_key)
        if cached:
            return PaymentDTO(**cached)
        
        # Из БД
        payment = await self._get_payment_from_db(payment_id)
        if payment:
            await self.redis.set(cache_key, payment.model_dump(), ttl=3600)
        
        return payment
    
    async def get_payments_by_trip(self, trip_id: str) -> list[PaymentDTO]:
        """Получить все платежи по поездке."""
        return await self._get_payments_by_trip_from_db(trip_id)
    
    async def get_payments_by_user(
        self,
        user_id: int,
        role: str = "payer",  # payer или payee
        limit: int = 50,
        offset: int = 0,
    ) -> list[PaymentDTO]:
        """Получить платежи пользователя."""
        return await self._get_payments_by_user_from_db(user_id, role, limit, offset)
    
    # === КОНВЕРТАЦИЯ ===
    
    def _convert_to_stars(self, amount_eur: float) -> int:
        """
        Конвертировать EUR в Telegram Stars.
        
        1 Star ≈ 0.013 USD
        Округляем вверх для безопасности.
        """
        # EUR → USD (примерный курс 1.1)
        amount_usd = amount_eur * 1.1
        # USD → Stars
        stars = amount_usd / self.stars_to_usd_rate
        return int(stars + 0.5)  # Округление до ближайшего целого
    
    def _convert_from_stars(self, stars: int) -> float:
        """Конвертировать Stars в EUR."""
        amount_usd = stars * self.stars_to_usd_rate
        return round(amount_usd / 1.1, 2)  # USD → EUR
    
    # === ПРИВАТНЫЕ МЕТОДЫ (ЗАГЛУШКИ ДЛЯ БД) ===
    
    async def _save_payment(self, payment: PaymentDTO) -> None:
        """Сохранить платёж в БД."""
        # TODO: Реализовать SQL INSERT
        pass
    
    async def _update_payment(self, payment: PaymentDTO) -> None:
        """Обновить платёж в БД."""
        # TODO: Реализовать SQL UPDATE
        # Инвалидируем кэш
        await self.redis.delete(f"payment:{payment.id}")
    
    async def _get_payment_from_db(self, payment_id: str) -> PaymentDTO | None:
        """Получить платёж из БД."""
        # TODO: Реализовать SQL SELECT
        return None
    
    async def _get_payments_by_trip_from_db(self, trip_id: str) -> list[PaymentDTO]:
        """Получить платежи по поездке из БД."""
        # TODO: Реализовать SQL SELECT
        return []
    
    async def _get_payments_by_user_from_db(
        self,
        user_id: int,
        role: str,
        limit: int,
        offset: int,
    ) -> list[PaymentDTO]:
        """Получить платежи пользователя из БД."""
        # TODO: Реализовать SQL SELECT
        return []
    
    async def _credit_driver_balance(
        self,
        driver_id: int,
        amount_stars: int,
        payment_id: str,
    ) -> None:
        """Начислить баланс водителю."""
        # TODO: Реализовать SQL UPDATE + INSERT в историю
        # Инвалидируем кэш
        await self.redis.delete(f"driver_balance:{driver_id}")
    
    async def _debit_driver_balance(
        self,
        driver_id: int,
        amount_stars: int,
        reason: str,
    ) -> None:
        """Списать с баланса водителя."""
        # TODO: Реализовать SQL UPDATE + INSERT в историю
        # Инвалидируем кэш
        await self.redis.delete(f"driver_balance:{driver_id}")
    
    async def _get_driver_balance_from_db(self, driver_id: int) -> dict:
        """Получить баланс водителя из БД."""
        # TODO: Реализовать SQL SELECT
        return {
            "driver_id": driver_id,
            "total_earned": 0,
            "available": 0,
            "pending": 0,
            "withdrawn": 0,
        }


class WithdrawalService:
    """
    Сервис вывода средств водителями.
    
    Поддержка вывода Stars (через Telegram или конвертация).
    """
    
    def __init__(
        self,
        db: "DatabaseManager",
        redis: "RedisClient",
        event_bus: "EventBus",
        payment_service: PaymentService,
    ) -> None:
        self.db = db
        self.redis = redis
        self.event_bus = event_bus
        self.payment_service = payment_service
        
        self.withdrawal_min_stars: int = 500
    
    async def request_withdrawal(
        self,
        driver_id: int,
        amount_stars: int,
        method: str = "telegram",  # telegram, bank
    ) -> dict:
        """
        Запросить вывод средств.
        
        Проверяет:
        - Достаточный баланс
        - Минимальная сумма вывода
        - Нет активных заявок
        """
        balance = await self.payment_service.get_driver_balance(driver_id)
        
        if balance["available"] < amount_stars:
            raise ValueError(
                f"Недостаточно средств. Доступно: {balance['available']} Stars"
            )
        
        if amount_stars < self.withdrawal_min_stars:
            raise ValueError(
                f"Минимальная сумма вывода: {self.withdrawal_min_stars} Stars"
            )
        
        withdrawal_id = str(uuid.uuid4())
        
        # TODO: Сохранить заявку в БД
        # TODO: Опубликовать событие withdrawal.requested
        
        return {
            "withdrawal_id": withdrawal_id,
            "driver_id": driver_id,
            "amount_stars": amount_stars,
            "amount_eur": self.payment_service._convert_from_stars(amount_stars),
            "method": method,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
    
    async def get_withdrawals(
        self,
        driver_id: int,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Получить историю выводов."""
        # TODO: Реализовать SQL SELECT
        return []
