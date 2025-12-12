import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.worker.base import BaseWorker
from src.infra.event_bus import DomainEvent

class TestWorker(BaseWorker):
    @property
    def name(self) -> str:
        return "TestWorker"
    
    @property
    def subscriptions(self) -> list[str]:
        return ["TEST_EVENT"]
    
    async def handle_event(self, event: DomainEvent) -> None:
        pass

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
    return TestWorker(mock_event_bus, mock_db, mock_redis)

@pytest.mark.asyncio
async def test_start(worker, mock_event_bus):
    await worker.start()
    
    assert worker._running is True
    mock_event_bus.subscribe.assert_called_once()
    assert mock_event_bus.subscribe.call_args[1]["event_type"] == "TEST_EVENT"

@pytest.mark.asyncio
async def test_stop(worker):
    worker._running = True
    await worker.stop()
    
    assert worker._running is False

@pytest.mark.asyncio
async def test_on_event_success(worker):
    worker._running = True
    worker.handle_event = AsyncMock()
    
    event = DomainEvent(event_type="TEST_EVENT", payload={})
    await worker._on_event(event)
    
    worker.handle_event.assert_called_once_with(event)

@pytest.mark.asyncio
async def test_on_event_error(worker):
    worker._running = True
    worker.handle_event = AsyncMock(side_effect=Exception("Worker error"))
    
    event = DomainEvent(event_type="TEST_EVENT", payload={})
    # Should not raise exception, but log it
    with patch("src.common.logger.log_error", new_callable=AsyncMock):
        await worker._on_event(event)
    
    worker.handle_event.assert_called_once()

@pytest.mark.asyncio
async def test_on_event_not_running(worker):
    worker._running = False
    worker.handle_event = AsyncMock()
    
    event = DomainEvent(event_type="TEST_EVENT", payload={})
    await worker._on_event(event)
    
    worker.handle_event.assert_not_called()
