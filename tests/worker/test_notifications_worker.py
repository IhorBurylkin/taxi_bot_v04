import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.worker.notifications import NotificationWorker
from src.infra.event_bus import DomainEvent, EventTypes

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
        mock.telegram.BOT_TOKEN = "test_token"
        mock.logging.LOG_LEVEL = "DEBUG"
        mock.logging.LOG_FORMAT = "colored"
        mock.logging.LOG_TO_FILE = False
        mock.logging.LOG_FILE_PATH = "logs/app.log"
        mock.logging.LOG_MAX_BYTES = 10485760
        mock.logging.LOG_BACKUP_COUNT = 5
        mock.system.ENVIRONMENT = "development"
        yield mock

@pytest.fixture
def mock_bot():
    with patch("src.worker.notifications.Bot") as MockBot:
        bot_instance = MockBot.return_value
        bot_instance.send_message = AsyncMock()
        bot_instance.session.close = AsyncMock()
        yield bot_instance

@pytest.fixture
def worker(mock_event_bus, mock_db, mock_redis, mock_settings, mock_bot):
    return NotificationWorker(mock_event_bus, mock_db, mock_redis)

@pytest.mark.asyncio
async def test_start_stop(worker, mock_bot):
    await worker.start()
    assert worker._bot is not None
    
    await worker.stop()
    mock_bot.session.close.assert_called_once()

@pytest.mark.asyncio
async def test_notify_driver_new_order(worker, mock_bot):
    worker._bot = mock_bot
    event = DomainEvent(
        event_type=EventTypes.DRIVER_ORDER_OFFERED,
        payload={
            "driver_id": 123,
            "order_id": "order1",
            "distance": 1.5
        }
    )
    
    await worker.handle_event(event)
    
    mock_bot.send_message.assert_called_once()
    args = mock_bot.send_message.call_args[1]
    assert args["chat_id"] == 123
    assert "1.5 км" in args["text"]

@pytest.mark.asyncio
async def test_notify_order_accepted(worker, mock_bot):
    worker._bot = mock_bot
    event = DomainEvent(
        event_type=EventTypes.ORDER_ACCEPTED,
        payload={
            "passenger_id": 456,
            "driver_name": "John",
            "car_info": "Toyota",
            "eta": 5
        }
    )
    
    await worker.handle_event(event)
    
    mock_bot.send_message.assert_called_once()
    args = mock_bot.send_message.call_args[1]
    assert args["chat_id"] == 456
    assert "John" in args["text"]

@pytest.mark.asyncio
async def test_notify_order_cancelled(worker, mock_bot):
    worker._bot = mock_bot
    event = DomainEvent(
        event_type=EventTypes.ORDER_CANCELLED,
        payload={
            "notify_users": [123, 456],
            "reason": "Test reason"
        }
    )
    
    await worker.handle_event(event)
    
    assert mock_bot.send_message.call_count == 2

@pytest.mark.asyncio
async def test_notify_order_completed(worker, mock_bot):
    worker._bot = mock_bot
    event = DomainEvent(
        event_type=EventTypes.ORDER_COMPLETED,
        payload={
            "passenger_id": 456,
            "driver_id": 123,
            "fare": 200.0
        }
    )
    
    await worker.handle_event(event)
    
    assert mock_bot.send_message.call_count == 2

@pytest.mark.asyncio
async def test_notify_driver_arrived(worker, mock_bot):
    worker._bot = mock_bot
    event = DomainEvent(
        event_type=EventTypes.DRIVER_ARRIVED,
        payload={
            "passenger_id": 456
        }
    )
    
    await worker.handle_event(event)
    
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[1]["chat_id"] == 456

@pytest.mark.asyncio
async def test_notify_ride_started(worker, mock_bot):
    worker._bot = mock_bot
    event = DomainEvent(
        event_type=EventTypes.RIDE_STARTED,
        payload={
            "passenger_id": 456,
            "destination": "Home"
        }
    )
    
    await worker.handle_event(event)
    
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[1]["chat_id"] == 456
