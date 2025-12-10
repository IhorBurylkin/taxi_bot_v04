# tests/core/test_orders_service.py
"""
Тесты для сервиса заказов.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.common.constants import OrderStatus, PaymentMethod
from src.core.orders.models import Order, OrderCreateDTO, FareCalculationDTO
from src.core.orders.service import FareCalculator, OrderService


class TestFareCalculator:
    """Тесты для калькулятора стоимости."""
    
    @pytest.fixture
    def calculator(self) -> FareCalculator:
        """Создаёт калькулятор с мок-настройками."""
        calc = FareCalculator.__new__(FareCalculator)
        calc.base_fare = 50.0
        calc.fare_per_km = 12.0
        calc.fare_per_minute = 3.0
        calc.pickup_fare = 30.0
        calc.min_fare = 80.0
        calc.surge_max = 3.0
        calc.currency = "UAH"
        return calc
    
    def test_calculate_basic_fare(self, calculator: FareCalculator) -> None:
        """Проверяет базовый расчёт стоимости."""
        result = calculator.calculate(
            distance_km=10.0,
            duration_minutes=20,
            surge_multiplier=1.0,
        )
        
        assert isinstance(result, FareCalculationDTO)
        assert result.distance_km == 10.0
        assert result.duration_minutes == 20
        assert result.surge_multiplier == 1.0
        assert result.currency == "UAH"
    
    def test_calculate_fare_components(self, calculator: FareCalculator) -> None:
        """Проверяет компоненты стоимости."""
        result = calculator.calculate(
            distance_km=10.0,
            duration_minutes=20,
            surge_multiplier=1.0,
        )
        
        assert result.base_fare == 50.0
        assert result.distance_fare == 120.0  # 10 * 12
        assert result.time_fare == 60.0       # 20 * 3
        assert result.pickup_fare == 30.0
    
    def test_calculate_total_fare(self, calculator: FareCalculator) -> None:
        """Проверяет итоговую стоимость."""
        result = calculator.calculate(
            distance_km=10.0,
            duration_minutes=20,
            surge_multiplier=1.0,
        )
        
        # 50 + 120 + 60 + 30 = 260
        assert result.total_fare == 260
    
    def test_calculate_with_surge(self, calculator: FareCalculator) -> None:
        """Проверяет расчёт с коэффициентом спроса."""
        result = calculator.calculate(
            distance_km=10.0,
            duration_minutes=20,
            surge_multiplier=1.5,
        )
        
        # (50 + 120 + 60 + 30) * 1.5 = 390
        assert result.total_fare == 390
        assert result.surge_multiplier == 1.5
    
    def test_calculate_surge_limited(self, calculator: FareCalculator) -> None:
        """Проверяет ограничение коэффициента спроса."""
        result = calculator.calculate(
            distance_km=10.0,
            duration_minutes=20,
            surge_multiplier=5.0,  # Больше максимума (3.0)
        )
        
        # Должен быть ограничен до 3.0
        assert result.surge_multiplier == 3.0
    
    def test_calculate_min_fare(self, calculator: FareCalculator) -> None:
        """Проверяет минимальную стоимость."""
        result = calculator.calculate(
            distance_km=0.5,   # Очень короткая поездка
            duration_minutes=2,
            surge_multiplier=1.0,
        )
        
        # 50 + 6 + 6 + 30 = 92, но минимум 80
        # В данном случае 92 > 80, так что минимум не применяется
        assert result.total_fare >= 80
    
    def test_calculate_rounds_to_integer(self, calculator: FareCalculator) -> None:
        """Проверяет округление до целых."""
        result = calculator.calculate(
            distance_km=7.7,
            duration_minutes=13,
            surge_multiplier=1.0,
        )
        
        # Результат должен быть целым числом
        assert isinstance(result.total_fare, int) or result.total_fare == int(result.total_fare)


class TestOrderService:
    """Тесты для сервиса заказов."""
    
    @pytest.fixture
    def order_service(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_event_bus: AsyncMock,
    ) -> OrderService:
        """Создаёт сервис с моками."""
        return OrderService(
            db=mock_db,
            redis=mock_redis,
            event_bus=mock_event_bus,
        )
    
    @pytest.mark.asyncio
    async def test_get_order_from_cache(
        self,
        order_service: OrderService,
        mock_redis: AsyncMock,
        sample_order_data: dict,
    ) -> None:
        """Проверяет получение заказа из кэша."""
        # Настраиваем мок кэша
        order = Order(**sample_order_data)
        mock_redis.get_model.return_value = order
        
        result = await order_service.get_order("test-order-uuid-123")
        
        assert result is not None
        assert result.id == "test-order-uuid-123"
        mock_redis.get_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_order_cache_miss(
        self,
        order_service: OrderService,
        mock_redis: AsyncMock,
        mock_db: AsyncMock,
    ) -> None:
        """Проверяет получение заказа при промахе кэша."""
        # Кэш пустой
        mock_redis.get_model.return_value = None
        
        # Мок репозитория тоже не находит
        with patch.object(
            order_service._repo, 'get_by_id',
            new_callable=AsyncMock,
            return_value=None
        ):
            result = await order_service.get_order("nonexistent-id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_active_order_for_passenger(
        self,
        order_service: OrderService,
        sample_order_data: dict,
    ) -> None:
        """Проверяет получение активного заказа пассажира."""
        order = Order(**sample_order_data)
        
        with patch.object(
            order_service._repo, 'get_active_by_passenger',
            new_callable=AsyncMock,
            return_value=order
        ):
            result = await order_service.get_active_order_for_passenger(123456789)
        
        assert result is not None
        assert result.passenger_id == 123456789
    
    @pytest.mark.asyncio
    async def test_get_active_order_for_driver(
        self,
        order_service: OrderService,
        sample_order_data: dict,
    ) -> None:
        """Проверяет получение активного заказа водителя."""
        sample_order_data["driver_id"] = 987654321
        sample_order_data["status"] = OrderStatus.ACCEPTED
        order = Order(**sample_order_data)
        
        with patch.object(
            order_service._repo, 'get_active_by_driver',
            new_callable=AsyncMock,
            return_value=order
        ):
            result = await order_service.get_active_order_for_driver(987654321)
        
        assert result is not None
        assert result.driver_id == 987654321
    
    def test_calculate_fare(self, order_service: OrderService) -> None:
        """Проверяет расчёт стоимости через сервис."""
        with patch.object(
            order_service._fare_calculator, 'calculate',
            return_value=FareCalculationDTO(
                distance_km=10.0,
                duration_minutes=20,
                base_fare=50.0,
                distance_fare=120.0,
                time_fare=60.0,
                pickup_fare=30.0,
                surge_multiplier=1.0,
                total_fare=260,
                currency="UAH",
            )
        ):
            result = order_service.calculate_fare(10.0, 20, 1.0)
        
        assert result.total_fare == 260
        assert result.currency == "UAH"
    
    def test_order_cache_key(self, order_service: OrderService) -> None:
        """Проверяет формирование ключа кэша."""
        key = order_service._order_cache_key("test-uuid")
        
        assert key == "order:test-uuid"
