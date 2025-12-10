# tests/core/test_billing_service.py
"""
Тесты для сервиса биллинга.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.common.constants import PaymentMethod, PaymentStatus
from src.core.billing.service import (
    PaymentResult,
    BalanceInfo,
    BillingService,
)
from src.infra.event_bus import EventTypes


class TestPaymentResult:
    """Тесты для dataclass PaymentResult."""
    
    def test_create_success_result(self) -> None:
        """Проверяет создание успешного результата."""
        result = PaymentResult(
            success=True,
            transaction_id="txn_123456",
        )
        
        assert result.success is True
        assert result.transaction_id == "txn_123456"
        assert result.error_message is None
    
    def test_create_failure_result(self) -> None:
        """Проверяет создание неуспешного результата."""
        result = PaymentResult(
            success=False,
            error_message="Недостаточно средств",
        )
        
        assert result.success is False
        assert result.transaction_id is None
        assert result.error_message == "Недостаточно средств"


class TestBalanceInfo:
    """Тесты для dataclass BalanceInfo."""
    
    def test_create_balance_info(self) -> None:
        """Проверяет создание информации о балансе."""
        info = BalanceInfo(
            stars=1000,
            usd_equivalent=13.0,
            can_withdraw=True,
            min_withdrawal=500,
        )
        
        assert info.stars == 1000
        assert info.usd_equivalent == 13.0
        assert info.can_withdraw is True
        assert info.min_withdrawal == 500
    
    def test_can_withdraw_false(self) -> None:
        """Проверяет случай, когда вывод недоступен."""
        info = BalanceInfo(
            stars=100,
            usd_equivalent=1.3,
            can_withdraw=False,
            min_withdrawal=500,
        )
        
        assert info.can_withdraw is False


class TestBillingService:
    """Тесты для сервиса биллинга."""
    
    @pytest.fixture
    def billing_service(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_event_bus: AsyncMock,
    ) -> BillingService:
        """Создаёт сервис с моками."""
        return BillingService(
            db=mock_db,
            redis=mock_redis,
            event_bus=mock_event_bus,
        )
    
    @pytest.mark.asyncio
    async def test_process_order_payment_success(
        self,
        billing_service: BillingService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет успешную обработку платежа."""
        with patch.object(
            billing_service, '_record_transaction',
            new_callable=AsyncMock,
            return_value="txn_123"
        ):
            with patch.object(
                billing_service, '_update_driver_balance',
                new_callable=AsyncMock,
            ):
                with patch("src.common.logger.log_info", new_callable=AsyncMock):
                    result = await billing_service.process_order_payment(
                        order_id="order-123",
                        driver_id=456,
                        amount=100.0,
                        payment_method=PaymentMethod.CARD,
                    )
        
        assert result.success is True
        assert result.transaction_id == "txn_123"
        # Проверяем, что событие было опубликовано
        mock_event_bus.publish.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_order_payment_cash_no_balance_update(
        self,
        billing_service: BillingService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет, что при оплате наличными баланс не обновляется."""
        with patch.object(
            billing_service, '_record_transaction',
            new_callable=AsyncMock,
            return_value="txn_123"
        ):
            mock_update = AsyncMock()
            with patch.object(
                billing_service, '_update_driver_balance',
                mock_update,
            ):
                with patch("src.common.logger.log_info", new_callable=AsyncMock):
                    result = await billing_service.process_order_payment(
                        order_id="order-123",
                        driver_id=456,
                        amount=100.0,
                        payment_method=PaymentMethod.CASH,  # Наличные
                    )
        
        assert result.success is True
        # При оплате наличными баланс не должен обновляться
        mock_update.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_order_payment_transaction_failed(
        self,
        billing_service: BillingService,
    ) -> None:
        """Проверяет обработку ошибки при записи транзакции."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.stars.PLATFORM_COMMISSION_PERCENT = 15.0
            
            with patch.object(
                billing_service, '_record_transaction',
                new_callable=AsyncMock,
                return_value=None  # Ошибка записи
            ):
                result = await billing_service.process_order_payment(
                    order_id="order-123",
                    driver_id=456,
                    amount=100.0,
                    payment_method=PaymentMethod.CARD,
                )
        
        assert result.success is False
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_process_order_payment_exception(
        self,
        billing_service: BillingService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет обработку исключения."""
        with patch.object(
            billing_service, '_record_transaction',
            new_callable=AsyncMock,
            side_effect=Exception("Database error")
        ):
            with patch("src.common.logger.log_error", new_callable=AsyncMock):
                result = await billing_service.process_order_payment(
                    order_id="order-123",
                    driver_id=456,
                    amount=100.0,
                    payment_method=PaymentMethod.CARD,
                )
        
        assert result.success is False
        assert "Database error" in result.error_message
        # Проверяем, что событие об ошибке было опубликовано
        mock_event_bus.publish.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_driver_balance_success(
        self,
        billing_service: BillingService,
        mock_db: AsyncMock,
    ) -> None:
        """Проверяет получение баланса водителя."""
        mock_db.fetchrow.return_value = {"balance_stars": 1000}
        
        with patch("src.config.settings") as mock_settings:
            mock_settings.stars.STARS_TO_USD_RATE = 0.013
            mock_settings.stars.WITHDRAWAL_MIN_STARS = 500
            
            result = await billing_service.get_driver_balance(123)
        
        assert result.stars == 1000
        assert result.usd_equivalent == 13.0
        assert result.can_withdraw is True
        assert result.min_withdrawal == 500
    
    @pytest.mark.asyncio
    async def test_get_driver_balance_no_profile(
        self,
        billing_service: BillingService,
        mock_db: AsyncMock,
    ) -> None:
        """Проверяет получение баланса при отсутствии профиля."""
        mock_db.fetchrow.return_value = None
        
        with patch("src.config.settings") as mock_settings:
            mock_settings.stars.STARS_TO_USD_RATE = 0.013
            mock_settings.stars.WITHDRAWAL_MIN_STARS = 500
            
            result = await billing_service.get_driver_balance(999)
        
        assert result.stars == 0
        assert result.can_withdraw is False
    
    @pytest.mark.asyncio
    async def test_get_driver_balance_exception(
        self,
        billing_service: BillingService,
        mock_db: AsyncMock,
    ) -> None:
        """Проверяет обработку исключения при получении баланса."""
        mock_db.fetchrow.side_effect = Exception("Database error")
        
        result = await billing_service.get_driver_balance(123)
        
        assert result.stars == 0
        assert result.usd_equivalent == 0.0
        assert result.can_withdraw is False
    
    @pytest.mark.asyncio
    async def test_commission_calculation(
        self,
        billing_service: BillingService,
    ) -> None:
        """Проверяет расчёт комиссии."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.stars.PLATFORM_COMMISSION_PERCENT = 15.0
            
            # Мокаем внутренние методы
            with patch.object(
                billing_service, '_record_transaction',
                new_callable=AsyncMock,
                return_value="txn_123"
            ) as mock_record:
                with patch.object(
                    billing_service, '_update_driver_balance',
                    new_callable=AsyncMock,
                ):
                    await billing_service.process_order_payment(
                        order_id="order-123",
                        driver_id=456,
                        amount=100.0,
                        payment_method=PaymentMethod.CARD,
                    )
        
        # Проверяем, что _record_transaction был вызван с правильными параметрами
        call_kwargs = mock_record.call_args[1]
        assert call_kwargs["amount"] == 100.0
        assert call_kwargs["commission"] == 15.0  # 15% от 100
        assert call_kwargs["earnings"] == 85.0    # 100 - 15
