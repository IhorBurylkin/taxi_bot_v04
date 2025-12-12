import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.core.orders.service import OrderService, FareCalculator
from src.core.orders.models import Order, OrderCreateDTO, FareCalculationDTO
from src.common.constants import OrderStatus, PaymentMethod
from src.infra.event_bus import EventTypes

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get_model = AsyncMock(return_value=None)
    redis.set_model = AsyncMock()
    redis.delete = AsyncMock()
    return redis

@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.get_active_by_passenger = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update_status = AsyncMock(return_value=True)
    repo.assign_driver = AsyncMock(return_value=True)
    return repo

@pytest.fixture
def service(mock_db, mock_redis, mock_event_bus, mock_repo):
    # Patch OrderRepository to return our mock
    with patch("src.core.orders.service.OrderRepository", return_value=mock_repo):
        service = OrderService(mock_db, mock_redis, mock_event_bus)
        return service

@pytest.fixture
def sample_order():
    return Order(
        id="test-order-id",
        passenger_id=123,
        pickup_address="A",
        pickup_latitude=1.0,
        pickup_longitude=1.0,
        destination_address="B",
        destination_latitude=2.0,
        destination_longitude=2.0,
        distance_km=5.0,
        duration_minutes=10,
        estimated_fare=200.0,
        status=OrderStatus.CREATED,
        payment_method=PaymentMethod.CASH,
        created_at=datetime.now(timezone.utc)
    )

@pytest.mark.asyncio
async def test_create_order_success(service, mock_repo, mock_redis, mock_event_bus):
    dto = OrderCreateDTO(
        passenger_id=123,
        pickup_address="A",
        pickup_latitude=1.0,
        pickup_longitude=1.0,
        destination_address="B",
        destination_latitude=2.0,
        destination_longitude=2.0,
        payment_method=PaymentMethod.CASH
    )
    
    mock_repo.create.return_value = Order(
        id="new-order",
        passenger_id=123,
        pickup_address="A",
        pickup_latitude=1.0,
        pickup_longitude=1.0,
        destination_address="B",
        destination_latitude=2.0,
        destination_longitude=2.0,
        distance_km=5.0,
        duration_minutes=10,
        estimated_fare=150.0,
        status=OrderStatus.CREATED,
        payment_method=PaymentMethod.CASH,
        created_at=datetime.now(timezone.utc)
    )
    
    # Mock calculate_fare
    with patch.object(service, 'calculate_fare') as mock_calc:
        mock_calc.return_value = FareCalculationDTO(
            distance_km=5.0,
            duration_minutes=10,
            base_fare=50,
            distance_fare=50,
            time_fare=50,
            pickup_fare=0,
            surge_multiplier=1.0,
            total_fare=150.0,
            currency="RUB"
        )
        
        result = await service.create_order(dto, 5.0, 10)
        
        assert result is not None
        assert result.id == "new-order"
        mock_repo.create.assert_called_once()
        mock_redis.set_model.assert_called_once()
        mock_event_bus.publish.assert_called_once()
        assert mock_event_bus.publish.call_args[0][0].event_type == EventTypes.ORDER_CREATED

@pytest.mark.asyncio
async def test_create_order_existing_active(service, mock_repo):
    mock_repo.get_active_by_passenger.return_value = MagicMock(id="existing")
    
    dto = OrderCreateDTO(
        passenger_id=123,
        pickup_address="A",
        pickup_latitude=1.0,
        pickup_longitude=1.0,
        destination_address="B",
        destination_latitude=2.0,
        destination_longitude=2.0,
        payment_method=PaymentMethod.CASH
    )
    
    result = await service.create_order(dto, 5.0, 10)
    
    assert result is None
    mock_repo.create.assert_not_called()

@pytest.mark.asyncio
async def test_start_search(service, mock_repo, mock_redis):
    result = await service.start_search("order-1")
    
    assert result is True
    mock_repo.update_status.assert_called_with("order-1", OrderStatus.SEARCHING)
    mock_redis.delete.assert_called_with("order:order-1")

@pytest.mark.asyncio
async def test_accept_order_success(service, mock_repo, mock_redis, mock_event_bus, sample_order):
    mock_repo.get_by_id.return_value = sample_order
    
    result = await service.accept_order("test-order-id", 456)
    
    assert result is True
    mock_repo.assign_driver.assert_called_with("test-order-id", 456)
    mock_redis.delete.assert_called_with("order:test-order-id")
    mock_event_bus.publish.assert_called_once()
    assert mock_event_bus.publish.call_args[0][0].event_type == EventTypes.ORDER_ACCEPTED

@pytest.mark.asyncio
async def test_accept_order_not_found(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    
    result = await service.accept_order("unknown", 456)
    
    assert result is False
    mock_repo.assign_driver.assert_not_called()

@pytest.mark.asyncio
async def test_accept_order_invalid_status(service, mock_repo, sample_order):
    sample_order.status = OrderStatus.IN_PROGRESS
    mock_repo.get_by_id.return_value = sample_order
    
    result = await service.accept_order("test-order-id", 456)
    
    assert result is False
    mock_repo.assign_driver.assert_not_called()

@pytest.mark.asyncio
async def test_driver_arrived(service, mock_repo, mock_redis):
    result = await service.driver_arrived("order-1")
    
    assert result is True
    mock_repo.update_status.assert_called()
    assert mock_repo.update_status.call_args[0][1] == OrderStatus.DRIVER_ARRIVED
    mock_redis.delete.assert_called_with("order:order-1")

@pytest.mark.asyncio
async def test_start_ride(service, mock_repo, mock_redis):
    result = await service.start_ride("order-1")
    
    assert result is True
    mock_repo.update_status.assert_called()
    assert mock_repo.update_status.call_args[0][1] == OrderStatus.IN_PROGRESS
    mock_redis.delete.assert_called_with("order:order-1")

@pytest.mark.asyncio
async def test_complete_order(service, mock_repo, mock_redis, mock_event_bus, sample_order):
    sample_order.driver_id = 456
    mock_repo.get_by_id.return_value = sample_order
    
    result = await service.complete_order("test-order-id", final_fare=250.0)
    
    assert result is True
    mock_repo.update_status.assert_called()
    assert mock_repo.update_status.call_args[0][1] == OrderStatus.COMPLETED
    assert mock_repo.update_status.call_args[1]["final_fare"] == 250.0
    
    mock_redis.delete.assert_called_with("order:test-order-id")
    mock_event_bus.publish.assert_called_once()
    assert mock_event_bus.publish.call_args[0][0].event_type == EventTypes.ORDER_COMPLETED

@pytest.mark.asyncio
async def test_cancel_order_success(service, mock_repo, mock_redis, mock_event_bus, sample_order):
    sample_order.driver_id = 456
    mock_repo.get_by_id.return_value = sample_order
    
    result = await service.cancel_order("test-order-id", cancelled_by="passenger")
    
    assert result is True
    mock_repo.update_status.assert_called()
    assert mock_repo.update_status.call_args[0][1] == OrderStatus.CANCELLED
    
    mock_redis.delete.assert_called_with("order:test-order-id")
    mock_event_bus.publish.assert_called_once()
    assert mock_event_bus.publish.call_args[0][0].event_type == EventTypes.ORDER_CANCELLED

@pytest.mark.asyncio
async def test_cancel_order_not_active(service, mock_repo, sample_order):
    sample_order.status = OrderStatus.COMPLETED
    mock_repo.get_by_id.return_value = sample_order
    
    result = await service.cancel_order("test-order-id")
    
    assert result is False
    mock_repo.update_status.assert_not_called()
