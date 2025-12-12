import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.worker.matching import MatchingWorker
from src.infra.event_bus import DomainEvent, EventTypes
from src.core.matching.service import DriverCandidate

@pytest.fixture
def mock_event_bus():
    return AsyncMock()

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def mock_settings():
    with patch("src.config.settings") as mock:
        mock.logging.LOG_LEVEL = "DEBUG"
        mock.logging.LOG_FORMAT = "colored"
        mock.logging.LOG_TO_FILE = False
        mock.logging.LOG_FILE_PATH = "logs/app.log"
        mock.logging.LOG_MAX_BYTES = 10485760
        mock.logging.LOG_BACKUP_COUNT = 5
        mock.system.ENVIRONMENT = "development"
        yield mock

@pytest.fixture
def worker(mock_event_bus, mock_db, mock_redis, mock_settings):
    return MatchingWorker(mock_event_bus, mock_db, mock_redis)

@pytest.mark.asyncio
async def test_handle_order_created_success(worker, mock_event_bus):
    # Mock MatchingService
    with patch("src.worker.matching.MatchingService") as MockService:
        service_instance = MockService.return_value
        service_instance.find_drivers_incrementally = AsyncMock(return_value=[
            DriverCandidate(driver_id=1, distance_km=0.5),
            DriverCandidate(driver_id=2, distance_km=1.0)
        ])
        
        event = DomainEvent(
            event_type=EventTypes.ORDER_CREATED,
            payload={
                "order_id": "order1",
                "pickup_lat": 10.0,
                "pickup_lon": 20.0
            }
        )
        
        await worker.handle_event(event)
        
        service_instance.find_drivers_incrementally.assert_called_once_with(
            latitude=10.0,
            longitude=20.0
        )
        
        assert mock_event_bus.publish.call_count == 2
        
        # Check first call
        call1 = mock_event_bus.publish.call_args_list[0][0][0]
        assert call1.event_type == EventTypes.DRIVER_ORDER_OFFERED
        assert call1.payload["driver_id"] == 1
        
        # Check second call
        call2 = mock_event_bus.publish.call_args_list[1][0][0]
        assert call2.event_type == EventTypes.DRIVER_ORDER_OFFERED
        assert call2.payload["driver_id"] == 2

@pytest.mark.asyncio
async def test_handle_order_created_no_drivers(worker, mock_event_bus):
    with patch("src.worker.matching.MatchingService") as MockService:
        service_instance = MockService.return_value
        service_instance.find_drivers_incrementally = AsyncMock(return_value=[])
        
        event = DomainEvent(
            event_type=EventTypes.ORDER_CREATED,
            payload={
                "order_id": "order1",
                "pickup_lat": 10.0,
                "pickup_lon": 20.0
            }
        )
        
        await worker.handle_event(event)
        
        mock_event_bus.publish.assert_not_called()

@pytest.mark.asyncio
async def test_handle_order_created_incomplete_payload(worker, mock_event_bus):
    event = DomainEvent(
        event_type=EventTypes.ORDER_CREATED,
        payload={
            "order_id": "order1"
            # Missing lat/lon
        }
    )
    
    await worker.handle_event(event)
    
    mock_event_bus.publish.assert_not_called()

@pytest.mark.asyncio
async def test_handle_driver_declined(worker, mock_redis):
    event = DomainEvent(
        event_type=EventTypes.ORDER_DRIVER_DECLINED,
        payload={
            "order_id": "order1",
            "driver_id": 123
        }
    )
    
    await worker.handle_event(event)
    
    mock_redis.sadd.assert_called_once_with(
        "order:order1:declined_drivers",
        "123"
    )
