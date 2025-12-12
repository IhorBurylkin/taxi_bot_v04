# src/core/billing/service.py
"""
Сервис биллинга.
Работа с оплатой, Telegram Stars, балансами водителей.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.common.constants import PaymentStatus, PaymentMethod, TypeMsg
from src.common.logger import log_info, log_error
from src.infra.database import DatabaseManager
from src.infra.redis_client import RedisClient
from src.infra.event_bus import EventBus, DomainEvent, EventTypes


@dataclass
class PaymentResult:
    """Результат операции оплаты."""
    success: bool
    transaction_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class BalanceInfo:
    """Информация о балансе."""
    stars: int
    usd_equivalent: float
    can_withdraw: bool
    min_withdrawal: int


class BillingService:
    """
    Сервис биллинга.
    
    Реализует:
    - Обработку оплаты заказов
    - Работу с Telegram Stars
    - Управление балансами водителей
    - Начисление комиссий
    """
    
    def __init__(
        self,
        db: DatabaseManager,
        redis: RedisClient,
        event_bus: EventBus,
    ) -> None:
        """
        Инициализация сервиса.
        
        Args:
            db: Менеджер базы данных
            redis: Клиент Redis
            event_bus: Шина событий
        """
        self._db = db
        self._redis = redis
        self._event_bus = event_bus
    
    async def process_order_payment(
        self,
        order_id: str,
        driver_id: int,
        amount: float,
        payment_method: PaymentMethod,
    ) -> PaymentResult:
        """
        Обрабатывает оплату заказа.
        
        Args:
            order_id: ID заказа
            driver_id: ID водителя
            amount: Сумма к оплате
            payment_method: Способ оплаты
            
        Returns:
            Результат операции
        """
        try:
            from src.config import settings
            
            # Рассчитываем комиссию
            commission_percent = settings.stars.PLATFORM_COMMISSION_PERCENT
            commission = round(amount * commission_percent / 100, 2)
            driver_earnings = amount - commission
            
            # Записываем транзакцию
            transaction_id = await self._record_transaction(
                order_id=order_id,
                driver_id=driver_id,
                amount=amount,
                commission=commission,
                earnings=driver_earnings,
                payment_method=payment_method,
            )
            
            if transaction_id is None:
                return PaymentResult(
                    success=False,
                    error_message="Не удалось записать транзакцию",
                )
            
            # Обновляем баланс водителя (если оплата не наличными)
            if payment_method != PaymentMethod.CASH:
                await self._update_driver_balance(driver_id, driver_earnings)
            
            # Публикуем событие
            try:
                await self._event_bus.publish(DomainEvent(
                    event_type=EventTypes.PAYMENT_COMPLETED,
                    payload={
                        "order_id": order_id,
                        "driver_id": driver_id,
                        "amount": amount,
                        "commission": commission,
                        "driver_earnings": driver_earnings,
                        "payment_method": payment_method.value,
                    },
                ))
            except Exception as pub_error:
                await log_error(f"Не удалось опубликовать PAYMENT_COMPLETED: {pub_error}")
            
            await log_info(
                f"Платёж обработан: заказ {order_id}, сумма {amount}, водитель {driver_id}",
                type_msg=TypeMsg.INFO,
            )
            
            return PaymentResult(
                success=True,
                transaction_id=transaction_id,
            )
        except Exception as e:
            await log_error(f"Ошибка обработки платежа: {e}")
            
            try:
                await self._event_bus.publish(DomainEvent(
                    event_type=EventTypes.PAYMENT_FAILED,
                    payload={
                        "order_id": order_id,
                        "driver_id": driver_id,
                        "error": str(e),
                    },
                ))
            except Exception as pub_error:
                await log_error(f"Не удалось опубликовать событие PAYMENT_FAILED: {pub_error}")
            
            return PaymentResult(
                success=False,
                error_message=str(e),
            )
    
    async def get_driver_balance(self, driver_id: int) -> BalanceInfo:
        """
        Получает баланс водителя.
        
        Args:
            driver_id: ID водителя
            
        Returns:
            Информация о балансе
        """
        from src.config import settings
        
        try:
            row = await self._db.fetchrow(
                "SELECT balance_stars FROM driver_profiles WHERE user_id = $1",
                driver_id,
            )
            
            stars = row["balance_stars"] if row else 0
            usd = round(stars * settings.stars.STARS_TO_USD_RATE, 2)
            min_withdrawal = settings.stars.WITHDRAWAL_MIN_STARS
            
            return BalanceInfo(
                stars=stars,
                usd_equivalent=usd,
                can_withdraw=stars >= min_withdrawal,
                min_withdrawal=min_withdrawal,
            )
        except Exception as e:
            await log_error(f"Ошибка получения баланса водителя {driver_id}: {e}")
            return BalanceInfo(
                stars=0,
                usd_equivalent=0.0,
                can_withdraw=False,
                min_withdrawal=500,
            )
    
    async def add_stars_to_balance(
        self,
        driver_id: int,
        stars: int,
        reason: str = "order_payment",
    ) -> bool:
        """
        Добавляет Stars к балансу водителя.
        
        Args:
            driver_id: ID водителя
            stars: Количество Stars
            reason: Причина начисления
            
        Returns:
            True если успешно
        """
        try:
            await self._db.execute(
                """
                UPDATE driver_profiles
                SET balance_stars = balance_stars + $2,
                    total_earnings = total_earnings + $3,
                    updated_at = $4
                WHERE user_id = $1
                """,
                driver_id,
                stars,
                float(stars),  # Добавляем к общему заработку
                datetime.now(timezone.utc),
            )
            
            await log_info(
                f"Начислено {stars} Stars водителю {driver_id} ({reason})",
                type_msg=TypeMsg.DEBUG,
            )
            
            return True
        except Exception as e:
            await log_error(f"Ошибка начисления Stars водителю {driver_id}: {e}")
            return False
    
    async def withdraw_stars(
        self,
        driver_id: int,
        stars: int,
    ) -> PaymentResult:
        """
        Выводит Stars с баланса водителя.
        
        Args:
            driver_id: ID водителя
            stars: Количество Stars для вывода
            
        Returns:
            Результат операции
        """
        from src.config import settings
        
        try:
            # Проверяем минимальную сумму
            if stars < settings.stars.WITHDRAWAL_MIN_STARS:
                return PaymentResult(
                    success=False,
                    error_message=f"Минимальная сумма вывода: {settings.stars.WITHDRAWAL_MIN_STARS} Stars",
                )
            
            # Проверяем баланс
            balance = await self.get_driver_balance(driver_id)
            if balance.stars < stars:
                return PaymentResult(
                    success=False,
                    error_message="Недостаточно средств на балансе",
                )
            
            # Списываем с баланса
            await self._db.execute(
                """
                UPDATE driver_profiles
                SET balance_stars = balance_stars - $2,
                    updated_at = $3
                WHERE user_id = $1
                """,
                driver_id,
                stars,
                datetime.now(timezone.utc),
            )
            
            await log_info(
                f"Вывод {stars} Stars водителем {driver_id}",
                type_msg=TypeMsg.INFO,
            )
            
            return PaymentResult(success=True)
        except Exception as e:
            await log_error(f"Ошибка вывода Stars водителя {driver_id}: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e),
            )
    
    async def _record_transaction(
        self,
        order_id: str,
        driver_id: int,
        amount: float,
        commission: float,
        earnings: float,
        payment_method: PaymentMethod,
    ) -> Optional[str]:
        """Записывает транзакцию в БД."""
        from uuid import uuid4
        
        try:
            transaction_id = str(uuid4())
            
            await self._db.execute(
                """
                INSERT INTO transactions (
                    id, order_id, driver_id, amount, commission, earnings,
                    payment_method, status, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                transaction_id,
                order_id,
                driver_id,
                amount,
                commission,
                earnings,
                payment_method.value,
                PaymentStatus.COMPLETED.value,
                datetime.now(timezone.utc),
            )
            
            return transaction_id
        except Exception as e:
            await log_error(f"Ошибка записи транзакции: {e}")
            return None
    
    async def _update_driver_balance(
        self,
        driver_id: int,
        amount: float,
    ) -> bool:
        """Обновляет баланс водителя."""
        try:
            await self._db.execute(
                """
                UPDATE driver_profiles
                SET total_earnings = total_earnings + $2,
                    updated_at = $3
                WHERE user_id = $1
                """,
                driver_id,
                amount,
                datetime.now(timezone.utc),
            )
            return True
        except Exception as e:
            await log_error(f"Ошибка обновления баланса водителя {driver_id}: {e}")
            return False
