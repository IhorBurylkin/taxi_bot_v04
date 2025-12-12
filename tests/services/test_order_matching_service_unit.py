import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.order_matching_service.utils import GeoUtils
from src.services.order_matching_service.consumer import OrderMatchingConsumer

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def mock_event_bus():
    return AsyncMock()

@pytest.mark.asyncio
async def test_geo_utils_find_drivers(mock_redis):
    utils = GeoUtils(mock_redis)
    
    # Mock georadius response: list of (member, distance)
    mock_redis.georadius.return_value = [("101", 1.5), ("102", 3.0)]
    
    drivers = await utils.find_drivers_in_radius(10.0, 20.0)
    
    assert len(drivers) == 2
    assert drivers[0] == (101, 1.5)
    assert drivers[1] == (102, 3.0)
    mock_redis.georadius.assert_called_once()

@pytest.mark.asyncio
async def test_consumer_handle_trip_created(mock_event_bus, mock_redis):
    geo_utils = GeoUtils(mock_redis)
    consumer = OrderMatchingConsumer(mock_event_bus, geo_utils)
    
    # Mock finding drivers
    mock_redis.georadius.return_value = [("101", 1.5)]
    
    event_data = {
        "trip_id": "uuid-123",
        "pickup_lat": 10.0,
        "pickup_lon": 20.0
    }
    
    await consumer.handle_trip_created(event_data)
    
    # Verify georadius called
    mock_redis.georadius.assert_called_once()
    
    # Verify logic flow (logs would be checked in integration tests, here we check no exceptions)
