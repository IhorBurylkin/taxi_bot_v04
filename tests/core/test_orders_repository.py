# tests/core/test_orders_repository.py
"""
Тесты для репозитория заказов.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict
import uuid

import pytest

from src.common.constants import OrderStatus, PaymentMethod, PaymentStatus
from src.core.orders.models import Order, OrderCreateDTO
from src.core.orders.repository import OrderRepository


@pytest.fixture
def mock_db() -> MagicMock:
    """Создаёт мок DatabaseManager."""
    db = MagicMock()
    db.fetchrow = AsyncMock()
    db.fetch = AsyncMock()
    db.execute = AsyncMock()
    db.transaction = MagicMock()
    return db


@pytest.fixture
def order_repository(mock_db: MagicMock) -> OrderRepository:
    """Создаёт экземпляр OrderRepository с моком БД."""
    return OrderRepository(db=mock_db)


@pytest.fixture
def sample_order_row() -> Dict[str, Any]:
    """Создаёт примерные данные заказа из БД."""
    return {
        "id": str(uuid.uuid4()),
        "passenger_id": 123456,
        "driver_id": None,
        "pickup_address": "ул. Пушкина, 10",
        "pickup_latitude": 50.4501,
        "pickup_longitude": 30.5234,
        "destination_address": "ул. Лермонтова, 20",
        "destination_latitude": 50.4601,
        "destination_longitude": 30.5334,
        "distance_km": 5.5,
        "duration_minutes": 15,
        "estimated_fare": 150.0,
        "final_fare": None,
        "surge_multiplier": 1.0,
        "status": OrderStatus.CREATED.value,
        "payment_method": PaymentMethod.CASH.value,
        "payment_status": PaymentStatus.PENDING.value,
        "created_at": datetime.now(),
        "accepted_at": None,
        "arrived_at": None,
        "started_at": None,
        "completed_at": None,
        "cancelled_at": None,
        "passenger_comment": None,
        "driver_rating": None,
        "passenger_rating": None,
    }


class TestOrderRepository:
    """Тесты для OrderRepository."""
    
    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
        sample_order_row: Dict[str, Any],
    ) -> None:
        """Проверяет успешное получение заказа по ID."""
        # Arrange
        order_id = sample_order_row["id"]
        mock_db.fetchrow.return_value = sample_order_row
        
        # Act
        order = await order_repository.get_by_id(order_id)
        
        # Assert
        assert order is not None
        assert order.id == order_id
        assert order.passenger_id == sample_order_row["passenger_id"]
        assert order.status == OrderStatus.CREATED
        mock_db.fetchrow.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет получение несуществующего заказа."""
        # Arrange
        order_id = str(uuid.uuid4())
        mock_db.fetchrow.return_value = None
        
        # Act
        order = await order_repository.get_by_id(order_id)
        
        # Assert
        assert order is None
        mock_db.fetchrow.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_id_error(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет обработку ошибки при получении заказа."""
        # Arrange
        order_id = str(uuid.uuid4())
        mock_db.fetchrow.side_effect = Exception("Database error")
        
        # Act
        with patch("src.core.orders.repository.log_error", new_callable=AsyncMock):
            order = await order_repository.get_by_id(order_id)
        
        # Assert
        assert order is None
    
    @pytest.mark.asyncio
    async def test_get_active_by_passenger_success(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
        sample_order_row: Dict[str, Any],
    ) -> None:
        """Проверяет получение активного заказа пассажира."""
        # Arrange
        passenger_id = sample_order_row["passenger_id"]
        sample_order_row["status"] = OrderStatus.SEARCHING.value
        mock_db.fetchrow.return_value = sample_order_row
        
        # Act
        order = await order_repository.get_active_by_passenger(passenger_id)
        
        # Assert
        assert order is not None
        assert order.passenger_id == passenger_id
        assert order.status == OrderStatus.SEARCHING
        mock_db.fetchrow.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_active_by_passenger_not_found(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет отсутствие активного заказа пассажира."""
        # Arrange
        passenger_id = 123456
        mock_db.fetchrow.return_value = None
        
        # Act
        order = await order_repository.get_active_by_passenger(passenger_id)
        
        # Assert
        assert order is None
    
    @pytest.mark.asyncio
    async def test_get_active_by_driver_success(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
        sample_order_row: Dict[str, Any],
    ) -> None:
        """Проверяет получение активного заказа водителя."""
        # Arrange
        driver_id = 789012
        sample_order_row["driver_id"] = driver_id
        sample_order_row["status"] = OrderStatus.ACCEPTED.value
        mock_db.fetchrow.return_value = sample_order_row
        
        # Act
        order = await order_repository.get_active_by_driver(driver_id)
        
        # Assert
        assert order is not None
        assert order.driver_id == driver_id
        assert order.status == OrderStatus.ACCEPTED
        mock_db.fetchrow.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_active_by_driver_not_found(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет отсутствие активного заказа водителя."""
        # Arrange
        driver_id = 789012
        mock_db.fetchrow.return_value = None
        
        # Act
        order = await order_repository.get_active_by_driver(driver_id)
        
        # Assert
        assert order is None
    
    @pytest.mark.asyncio
    async def test_create_success(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
        sample_order_row: Dict[str, Any],
    ) -> None:
        """Проверяет успешное создание заказа."""
        # Arrange
        order = Order(
            id=sample_order_row["id"],
            passenger_id=sample_order_row["passenger_id"],
            pickup_address=sample_order_row["pickup_address"],
            pickup_latitude=sample_order_row["pickup_latitude"],
            pickup_longitude=sample_order_row["pickup_longitude"],
            destination_address=sample_order_row["destination_address"],
            destination_latitude=sample_order_row["destination_latitude"],
            destination_longitude=sample_order_row["destination_longitude"],
            distance_km=sample_order_row["distance_km"],
            duration_minutes=sample_order_row["duration_minutes"],
            estimated_fare=sample_order_row["estimated_fare"],
            surge_multiplier=sample_order_row["surge_multiplier"],
            status=OrderStatus.CREATED,
            payment_method=PaymentMethod.CASH,
            payment_status=PaymentStatus.PENDING,
            created_at=sample_order_row["created_at"],
        )
        
        mock_db.fetchrow.return_value = sample_order_row
        
        # Act
        with patch("src.core.orders.repository.log_info", new_callable=AsyncMock):
            created_order = await order_repository.create(order)
        
        # Assert
        assert created_order is not None
        assert created_order.id == order.id
        assert created_order.passenger_id == order.passenger_id
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_error(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
        sample_order_row: Dict[str, Any],
    ) -> None:
        """Проверяет обработку ошибки при создании заказа."""
        # Arrange
        order = Order(
            id=sample_order_row["id"],
            passenger_id=sample_order_row["passenger_id"],
            pickup_address=sample_order_row["pickup_address"],
            pickup_latitude=sample_order_row["pickup_latitude"],
            pickup_longitude=sample_order_row["pickup_longitude"],
            destination_address=sample_order_row["destination_address"],
            destination_latitude=sample_order_row["destination_latitude"],
            destination_longitude=sample_order_row["destination_longitude"],
            distance_km=sample_order_row["distance_km"],
            duration_minutes=sample_order_row["duration_minutes"],
            estimated_fare=sample_order_row["estimated_fare"],
            status=OrderStatus.CREATED,
            payment_method=PaymentMethod.CASH,
            payment_status=PaymentStatus.PENDING,
        )
        
        mock_db.execute.side_effect = Exception("Database error")
        
        # Act
        with patch("src.core.orders.repository.log_error", new_callable=AsyncMock):
            created_order = await order_repository.create(order)
        
        # Assert
        assert created_order is None
    
    @pytest.mark.asyncio
    async def test_update_status_success(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
        sample_order_row: Dict[str, Any],
    ) -> None:
        """Проверяет успешное обновление статуса заказа."""
        # Arrange
        order_id = sample_order_row["id"]
        new_status = OrderStatus.SEARCHING
        
        # Act
        with patch("src.core.orders.repository.log_info", new_callable=AsyncMock):
            result = await order_repository.update_status(order_id, new_status)
        
        # Assert
        assert result is True
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_status_error(
        self,
        order_repository: OrderRepository,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет обработку ошибки при обновлении статуса."""
        # Arrange
        order_id = str(uuid.uuid4())
        new_status = OrderStatus.SEARCHING
        mock_db.execute.side_effect = Exception("Database error")
        
        # Act
        with patch("src.core.orders.repository.log_error", new_callable=AsyncMock):
            result = await order_repository.update_status(order_id, new_status)
        
        # Assert
        assert result is False
