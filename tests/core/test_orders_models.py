# tests/core/test_orders_models.py
"""
Тесты для моделей заказов.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from src.common.constants import OrderStatus, PaymentMethod, PaymentStatus
from src.core.orders.models import (
    Order,
    OrderCreateDTO,
    OrderAcceptDTO,
    FareCalculationDTO,
)


class TestOrder:
    """Тесты для модели Order."""
    
    def test_create_order(self, sample_order_data: dict) -> None:
        """Проверяет создание заказа."""
        order = Order(**sample_order_data)
        
        assert order.id == sample_order_data["id"]
        assert order.passenger_id == sample_order_data["passenger_id"]
        assert order.pickup_address == sample_order_data["pickup_address"]
        assert order.destination_address == sample_order_data["destination_address"]
    
    def test_order_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        order = Order(
            passenger_id=123,
            pickup_address="Адрес подачи",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Адрес назначения",
            destination_latitude=50.40,
            destination_longitude=30.50,
        )
        
        # Проверяем, что ID генерируется автоматически (UUID)
        assert order.id is not None
        try:
            UUID(order.id)
            is_valid_uuid = True
        except ValueError:
            is_valid_uuid = False
        assert is_valid_uuid
        
        assert order.driver_id is None
        assert order.status == OrderStatus.CREATED
        assert order.payment_method == PaymentMethod.CASH
        assert order.payment_status == PaymentStatus.PENDING
        assert order.surge_multiplier == 1.0
        assert order.distance_km == 0.0
        assert order.duration_minutes == 0
        assert order.estimated_fare == 0.0
    
    def test_order_is_active_created(self) -> None:
        """Проверяет is_active для статуса CREATED."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            status=OrderStatus.CREATED,
        )
        
        assert order.is_active is True
    
    def test_order_is_active_searching(self) -> None:
        """Проверяет is_active для статуса SEARCHING."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            status=OrderStatus.SEARCHING,
        )
        
        assert order.is_active is True
    
    def test_order_is_active_in_progress(self) -> None:
        """Проверяет is_active для статуса IN_PROGRESS."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            status=OrderStatus.IN_PROGRESS,
        )
        
        assert order.is_active is True
    
    def test_order_is_not_active_completed(self) -> None:
        """Проверяет is_active для статуса COMPLETED."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            status=OrderStatus.COMPLETED,
        )
        
        assert order.is_active is False
    
    def test_order_is_not_active_cancelled(self) -> None:
        """Проверяет is_active для статуса CANCELLED."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            status=OrderStatus.CANCELLED,
        )
        
        assert order.is_active is False
    
    def test_order_is_completed(self) -> None:
        """Проверяет свойство is_completed."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            status=OrderStatus.COMPLETED,
        )
        
        assert order.is_completed is True
        assert order.is_cancelled is False
    
    def test_order_is_cancelled(self) -> None:
        """Проверяет свойство is_cancelled."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            status=OrderStatus.CANCELLED,
        )
        
        assert order.is_cancelled is True
        assert order.is_completed is False
    
    def test_order_fare_returns_estimated(self) -> None:
        """Проверяет, что fare возвращает расчётную стоимость."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            estimated_fare=250.0,
            final_fare=None,
        )
        
        assert order.fare == 250.0
    
    def test_order_fare_returns_final(self) -> None:
        """Проверяет, что fare возвращает итоговую стоимость."""
        order = Order(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
            estimated_fare=250.0,
            final_fare=300.0,
        )
        
        assert order.fare == 300.0
    
    def test_order_distance_validation(self) -> None:
        """Проверяет валидацию расстояния."""
        with pytest.raises(ValueError):
            Order(
                passenger_id=123,
                pickup_address="А",
                pickup_latitude=50.45,
                pickup_longitude=30.52,
                destination_address="Б",
                destination_latitude=50.40,
                destination_longitude=30.50,
                distance_km=-5.0,  # Отрицательное значение
            )
    
    def test_order_duration_validation(self) -> None:
        """Проверяет валидацию времени поездки."""
        with pytest.raises(ValueError):
            Order(
                passenger_id=123,
                pickup_address="А",
                pickup_latitude=50.45,
                pickup_longitude=30.52,
                destination_address="Б",
                destination_latitude=50.40,
                destination_longitude=30.50,
                duration_minutes=-10,  # Отрицательное значение
            )
    
    def test_order_surge_validation(self) -> None:
        """Проверяет валидацию коэффициента спроса."""
        with pytest.raises(ValueError):
            Order(
                passenger_id=123,
                pickup_address="А",
                pickup_latitude=50.45,
                pickup_longitude=30.52,
                destination_address="Б",
                destination_latitude=50.40,
                destination_longitude=30.50,
                surge_multiplier=0.5,  # Меньше 1.0
            )
    
    def test_order_payment_methods(self) -> None:
        """Проверяет разные способы оплаты."""
        for method in PaymentMethod:
            order = Order(
                passenger_id=123,
                pickup_address="А",
                pickup_latitude=50.45,
                pickup_longitude=30.52,
                destination_address="Б",
                destination_latitude=50.40,
                destination_longitude=30.50,
                payment_method=method,
            )
            assert order.payment_method == method


class TestOrderCreateDTO:
    """Тесты для DTO создания заказа."""
    
    def test_create_dto(self) -> None:
        """Проверяет создание DTO."""
        dto = OrderCreateDTO(
            passenger_id=123,
            pickup_address="ул. Крещатик, 1",
            pickup_latitude=50.4501,
            pickup_longitude=30.5234,
            destination_address="Аэропорт",
            destination_latitude=50.3450,
            destination_longitude=30.8940,
            payment_method=PaymentMethod.CARD,
            passenger_comment="Вызовите, когда приедете",
        )
        
        assert dto.passenger_id == 123
        assert dto.pickup_address == "ул. Крещатик, 1"
        assert dto.payment_method == PaymentMethod.CARD
        assert dto.passenger_comment == "Вызовите, когда приедете"
    
    def test_dto_defaults(self) -> None:
        """Проверяет значения по умолчанию в DTO."""
        dto = OrderCreateDTO(
            passenger_id=123,
            pickup_address="А",
            pickup_latitude=50.45,
            pickup_longitude=30.52,
            destination_address="Б",
            destination_latitude=50.40,
            destination_longitude=30.50,
        )
        
        assert dto.payment_method == PaymentMethod.CASH
        assert dto.passenger_comment is None


class TestOrderAcceptDTO:
    """Тесты для DTO принятия заказа."""
    
    def test_create_dto(self) -> None:
        """Проверяет создание DTO."""
        dto = OrderAcceptDTO(
            order_id="order-uuid-123",
            driver_id=456,
        )
        
        assert dto.order_id == "order-uuid-123"
        assert dto.driver_id == 456


class TestFareCalculationDTO:
    """Тесты для DTO расчёта стоимости."""
    
    def test_create_dto(self) -> None:
        """Проверяет создание DTO."""
        dto = FareCalculationDTO(
            distance_km=15.5,
            duration_minutes=25,
            base_fare=50.0,
            distance_fare=186.0,
            time_fare=75.0,
            pickup_fare=30.0,
            surge_multiplier=1.2,
            total_fare=410.0,
            currency="UAH",
        )
        
        assert dto.distance_km == 15.5
        assert dto.duration_minutes == 25
        assert dto.base_fare == 50.0
        assert dto.distance_fare == 186.0
        assert dto.time_fare == 75.0
        assert dto.pickup_fare == 30.0
        assert dto.surge_multiplier == 1.2
        assert dto.total_fare == 410.0
        assert dto.currency == "UAH"
    
    def test_dto_fare_components(self) -> None:
        """Проверяет компоненты расчёта стоимости."""
        dto = FareCalculationDTO(
            distance_km=10.0,
            duration_minutes=20,
            base_fare=50.0,
            distance_fare=120.0,  # 10 * 12
            time_fare=60.0,       # 20 * 3
            pickup_fare=30.0,
            surge_multiplier=1.0,
            total_fare=260.0,     # 50 + 120 + 60 + 30
            currency="UAH",
        )
        
        # Проверяем, что сумма компонентов соответствует total
        components_sum = (
            dto.base_fare
            + dto.distance_fare
            + dto.time_fare
            + dto.pickup_fare
        ) * dto.surge_multiplier
        
        assert dto.total_fare == components_sum
