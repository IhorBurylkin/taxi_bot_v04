import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from src.worker.runner import run_workers

@pytest.fixture
def mock_infra():
    with patch("src.worker.runner.init_db", new_callable=AsyncMock) as mock_init_db, \
         patch("src.worker.runner.close_db", new_callable=AsyncMock) as mock_close_db, \
         patch("src.worker.runner.init_redis", new_callable=AsyncMock) as mock_init_redis, \
         patch("src.worker.runner.close_redis", new_callable=AsyncMock) as mock_close_redis, \
         patch("src.worker.runner.init_event_bus", new_callable=AsyncMock) as mock_init_event_bus, \
         patch("src.worker.runner.close_event_bus", new_callable=AsyncMock) as mock_close_event_bus:
        yield {
            "init_db": mock_init_db,
            "close_db": mock_close_db,
            "init_redis": mock_init_redis,
            "close_redis": mock_close_redis,
            "init_event_bus": mock_init_event_bus,
            "close_event_bus": mock_close_event_bus
        }

@pytest.fixture
def mock_workers():
    with patch("src.worker.runner.MatchingWorker") as MockMatching:
        
        matching_instance = MockMatching.return_value
        matching_instance.start = AsyncMock()
        matching_instance.stop = AsyncMock()
        
        yield {
            "matching": matching_instance,
        }

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

@pytest.mark.asyncio
async def test_run_workers_success(mock_infra, mock_workers, mock_settings):
    # Mock asyncio.sleep to raise CancelledError immediately to exit loop
    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await run_workers()
    
    # Check init
    mock_infra["init_db"].assert_called_once()
    mock_infra["init_redis"].assert_called_once()
    mock_infra["init_event_bus"].assert_called_once()
    
    # Check start
    mock_workers["matching"].start.assert_called_once()
    
    # Check stop
    mock_workers["matching"].stop.assert_called_once()
    
    # Check close
    mock_infra["close_db"].assert_called_once()
    mock_infra["close_redis"].assert_called_once()
    mock_infra["close_event_bus"].assert_called_once()

@pytest.mark.asyncio
async def test_run_workers_error(mock_infra, mock_workers, mock_settings):
    # Mock init_db to raise exception
    mock_infra["init_db"].side_effect = Exception("Init error")
    
    with pytest.raises(Exception, match="Init error"):
        await run_workers()
    
    # Should NOT try to close everything because it crashed before creating workers/try-finally block?
    # Wait, run_workers does NOT have a global try/finally. The try/finally is only around the worker loop.
    # So if init fails, it just crashes.
    
    mock_infra["close_db"].assert_not_called()
