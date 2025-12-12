import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.matching.service import MatchingService, DriverCandidate

@pytest.fixture
def mock_settings():
    with patch("src.config.settings") as mock:
        mock.search.SEARCH_RADIUS_MIN_KM = 1.0
        mock.search.SEARCH_RADIUS_MAX_KM = 5.0
        mock.search.SEARCH_RADIUS_STEP_KM = 1.0
        mock.search.MAX_DRIVERS_TO_NOTIFY = 3
        
        mock.redis_ttl.NOTIFIED_DRIVERS_TTL = 3600
        
        # Logger
        mock.logging.LOG_LEVEL = "DEBUG"
        mock.logging.LOG_FORMAT = "colored"
        mock.logging.LOG_TO_FILE = False
        mock.logging.LOG_FILE_PATH = "logs/app.log"
        mock.logging.LOG_MAX_BYTES = 10485760
        mock.logging.LOG_BACKUP_COUNT = 5
        mock.system.ENVIRONMENT = "development"
        
        yield mock

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def matching_service(mock_redis, mock_db, mock_settings):
    return MatchingService(mock_redis, mock_db)

@pytest.mark.asyncio
async def test_find_nearby_drivers_success(matching_service, mock_redis):
    # Mock georadius results: [(driver_id, distance)]
    mock_redis.georadius.return_value = [("1", 0.5), ("2", 1.2)]
    
    # Mock last_seen
    mock_redis.get.side_effect = [
        datetime(2023, 1, 1, 12, 0, 0).isoformat(), # driver 1
        None # driver 2
    ]
    
    results = await matching_service.find_nearby_drivers(10.0, 20.0, radius_km=2.0)
    
    assert len(results) == 2
    assert results[0].driver_id == 1
    assert results[0].distance_km == 0.5
    assert results[0].last_seen == datetime(2023, 1, 1, 12, 0, 0)
    
    assert results[1].driver_id == 2
    assert results[1].distance_km == 1.2
    assert results[1].last_seen is None
    
    mock_redis.georadius.assert_called_once()

@pytest.mark.asyncio
async def test_find_nearby_drivers_empty(matching_service, mock_redis):
    mock_redis.georadius.return_value = []
    
    results = await matching_service.find_nearby_drivers(10.0, 20.0)
    assert len(results) == 0

@pytest.mark.asyncio
async def test_find_drivers_incrementally_first_try(matching_service, mock_redis):
    # First call returns results >= MAX_DRIVERS_TO_NOTIFY (3)
    mock_redis.georadius.return_value = [("1", 0.5), ("2", 0.6), ("3", 0.7)]
    mock_redis.get.return_value = None
    
    results = await matching_service.find_drivers_incrementally(10.0, 20.0)
    
    assert len(results) == 3
    # Should be called with min radius (1.0) and stop because we found enough
    assert mock_redis.georadius.call_count == 1
    assert mock_redis.georadius.call_args[0][3] == 1.0

@pytest.mark.asyncio
async def test_find_drivers_incrementally_step(matching_service, mock_redis):
    # First call (radius 1.0) returns empty
    # Second call (radius 2.0) returns results >= MAX_DRIVERS_TO_NOTIFY (3)
    mock_redis.georadius.side_effect = [
        [],
        [("1", 1.5), ("2", 1.6), ("3", 1.7)]
    ]
    mock_redis.get.return_value = None
    
    results = await matching_service.find_drivers_incrementally(10.0, 20.0)
    
    assert len(results) == 3
    assert mock_redis.georadius.call_count == 2
    assert mock_redis.georadius.call_args_list[0][0][3] == 1.0
    assert mock_redis.georadius.call_args_list[1][0][3] == 2.0

@pytest.mark.asyncio
async def test_filter_available_drivers(matching_service, mock_redis):
    candidates = [
        DriverCandidate(driver_id=1, distance_km=0.5),
        DriverCandidate(driver_id=2, distance_km=0.6),
        DriverCandidate(driver_id=3, distance_km=0.7),
    ]
    
    # Driver 1: Notified (exists)
    # Driver 2: Rejected (exists)
    # Driver 3: Available (not exists)
    
    async def exists_side_effect(key):
        if "notified:1" in key: return True
        if "rejected:1" in key: return False # Should not be checked if notified is true, but logic checks notified then rejected
        
        if "notified:2" in key: return False
        if "rejected:2" in key: return True
        
        if "notified:3" in key: return False
        if "rejected:3" in key: return False
        return False
        
    mock_redis.exists.side_effect = exists_side_effect
    
    filtered = await matching_service.filter_available_drivers(candidates, "order1")
    
    assert len(filtered) == 1
    assert filtered[0].driver_id == 3

@pytest.mark.asyncio
async def test_mark_driver_notified(matching_service, mock_redis):
    await matching_service.mark_driver_notified("order1", 1)
    mock_redis.set.assert_called_once()
    assert "order:order1:notified:1" in mock_redis.set.call_args[0][0]

@pytest.mark.asyncio
async def test_mark_driver_rejected(matching_service, mock_redis):
    await matching_service.mark_driver_rejected("order1", 1)
    mock_redis.set.assert_called_once()
    assert "order:order1:rejected:1" in mock_redis.set.call_args[0][0]

@pytest.mark.asyncio
async def test_get_best_candidate(matching_service, mock_redis):
    # Mock find_drivers_incrementally
    matching_service.find_drivers_incrementally = AsyncMock(return_value=[
        DriverCandidate(driver_id=1, distance_km=0.5),
        DriverCandidate(driver_id=2, distance_km=0.6)
    ])
    
    # Mock filter_available_drivers
    matching_service.filter_available_drivers = AsyncMock(return_value=[
        DriverCandidate(driver_id=1, distance_km=0.5)
    ])
    
    result = await matching_service.get_best_candidate(10.0, 20.0, "order1")
    
    assert result is not None
    assert result.driver_id == 1
    matching_service.find_drivers_incrementally.assert_called_once()
    matching_service.filter_available_drivers.assert_called_once()

@pytest.mark.asyncio
async def test_get_best_candidate_none(matching_service):
    matching_service.find_drivers_incrementally = AsyncMock(return_value=[])
    matching_service.filter_available_drivers = AsyncMock(return_value=[])
    
    result = await matching_service.get_best_candidate(10.0, 20.0, "order1")
    assert result is None
