import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.worker.matching import MatchingWorker
from src.infra.event_bus import DomainEvent, EventTypes
from src.common.constants import TypeMsg
from src.core.matching.service import DriverCandidate

@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.sadd = AsyncMock()
    return redis

@pytest.fixture
def worker(mock_event_bus, mock_db, mock_redis):
    return MatchingWorker(
        event_bus=mock_event_bus,
        db=mock_db,
        redis=mock_redis
    )

@pytest.mark.asyncio
async def test_worker_initialization(worker):
    assert worker.name == "MatchingWorker"
    assert EventTypes.ORDER_CREATED in worker.subscriptions
    assert EventTypes.ORDER_DRIVER_DECLINED in worker.subscriptions

@pytest.mark.asyncio
async def test_handle_order_created_success(worker, mock_event_bus):
    # Mock MatchingService
    with patch("src.worker.matching.MatchingService") as MockMatchingService:
        mock_service = MockMatchingService.return_value
        # Mock find_drivers_incrementally to return list of DriverCandidate
        mock_service.find_drivers_incrementally = AsyncMock(return_value=[
            DriverCandidate(driver_id=101, distance_km=0.5),
            DriverCandidate(driver_id=102, distance_km=1.2),
            DriverCandidate(driver_id=103, distance_km=2.0)
        ])
        
        event = DomainEvent(
            event_type=EventTypes.ORDER_CREATED,
            payload={
                "order_id": 1,
                "pickup_lat": 55.75,
                "pickup_lon": 37.61
            }
        )
        
        await worker.handle_event(event)
        
        # Check if find_drivers_incrementally was called
        mock_service.find_drivers_incrementally.assert_called_once_with(
            latitude=55.75,
            longitude=37.61,
        )
        
        # Check if events were published for each driver
        assert mock_event_bus.publish.call_count == 3
        
        # Verify payload of published events
        calls = mock_event_bus.publish.call_args_list
        
        # Driver 101
        assert calls[0][0][0].event_type == EventTypes.DRIVER_ORDER_OFFERED
        assert calls[0][0][0].payload["driver_id"] == 101
        assert calls[0][0][0].payload["order_id"] == 1
        
        # Driver 102
        assert calls[1][0][0].event_type == EventTypes.DRIVER_ORDER_OFFERED
        assert calls[1][0][0].payload["driver_id"] == 102

@pytest.mark.asyncio
async def test_handle_order_created_no_drivers(worker, mock_event_bus):
    with patch("src.worker.matching.MatchingService") as MockMatchingService:
        mock_service = MockMatchingService.return_value
        mock_service.find_drivers_incrementally = AsyncMock(return_value=[])
        
        event = DomainEvent(
            event_type=EventTypes.ORDER_CREATED,
            payload={
                "order_id": 1,
                "pickup_lat": 55.75,
                "pickup_lon": 37.61
            }
        )
        
        await worker.handle_event(event)
        
        mock_service.find_drivers_incrementally.assert_called_once()
        mock_event_bus.publish.assert_not_called()

@pytest.mark.asyncio
async def test_handle_order_created_incomplete_data(worker, mock_event_bus):
    event = DomainEvent(
        event_type=EventTypes.ORDER_CREATED,
        payload={
            "order_id": 1,
            # Missing lat/lon
        }
    )
    
    with patch("src.worker.matching.log_error", new_callable=AsyncMock) as mock_log_error:
        await worker.handle_event(event)
        mock_log_error.assert_called_once()
        mock_event_bus.publish.assert_not_called()

@pytest.mark.asyncio
async def test_handle_driver_declined(worker):
    # Currently _handle_driver_declined is empty/not implemented fully in the provided snippet
    # But we can test that it doesn't crash
    event = DomainEvent(
        event_type=EventTypes.ORDER_DRIVER_DECLINED,
        payload={
            "order_id": 1,
            "driver_id": 101
        }
    )
    
    await worker.handle_event(event)
