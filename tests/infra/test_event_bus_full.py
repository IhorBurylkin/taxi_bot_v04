import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

from src.infra.event_bus import EventBus, DomainEvent, get_event_bus, init_event_bus, close_event_bus

@pytest.fixture
def mock_aio_pika():
    with patch("src.infra.event_bus.aio_pika.connect_robust") as mock:
        connection_mock = AsyncMock()
        # Ensure is_closed is False so is_connected returns True
        connection_mock.is_closed = False
        
        channel_mock = AsyncMock()
        exchange_mock = AsyncMock()
        queue_mock = AsyncMock()
        
        mock.return_value = connection_mock
        connection_mock.channel.return_value = channel_mock
        channel_mock.declare_exchange.return_value = exchange_mock
        channel_mock.declare_queue.return_value = queue_mock
        
        yield mock

@pytest.fixture
def event_bus(mock_aio_pika):
    # Reset singleton
    EventBus._instance = None
    EventBus._connection = None
    EventBus._channel = None
    EventBus._exchange = None
    
    bus = EventBus()
    # Manually set components to avoid needing to call connect() in every test
    bus._connection = mock_aio_pika.return_value
    bus._channel = mock_aio_pika.return_value.channel.return_value
    bus._exchange = mock_aio_pika.return_value.channel.return_value.declare_exchange.return_value
    
    return bus

@pytest.fixture
def mock_settings():
    with patch("src.config.settings") as mock:
        mock.rabbitmq.url = "amqp://guest:guest@localhost:5672/"
        mock.rabbitmq.RABBITMQ_EXCHANGE = "taxi.events"
        mock.rabbitmq.RABBITMQ_PREFETCH_COUNT = 10
        mock.rabbitmq.RABBITMQ_HOST = "localhost"
        mock.rabbitmq.RABBITMQ_PORT = 5672
        
        # Fix logger issue
        mock.logging.LOG_LEVEL = "DEBUG"
        mock.logging.LOG_FORMAT = "colored"
        mock.logging.LOG_TO_FILE = False
        mock.logging.LOG_FILE_PATH = "logs/app.log"
        mock.logging.LOG_MAX_BYTES = 10485760
        mock.logging.LOG_BACKUP_COUNT = 5
        mock.system.ENVIRONMENT = "development"
        
        yield mock

def test_domain_event():
    event = DomainEvent(
        event_type="test.event",
        payload={"key": "value"}
    )
    
    json_str = event.to_json()
    assert "test.event" in json_str
    assert "key" in json_str
    
    parsed = DomainEvent.from_json(json_str)
    assert parsed.event_type == event.event_type
    assert parsed.payload == event.payload
    assert parsed.event_id == event.event_id
    assert parsed.timestamp == event.timestamp

@pytest.mark.asyncio
async def test_singleton():
    EventBus._instance = None
    bus1 = EventBus()
    bus2 = EventBus()
    assert bus1 is bus2
    assert get_event_bus() is bus1

@pytest.mark.asyncio
async def test_connect(mock_aio_pika, mock_settings):
    EventBus._instance = None
    bus = EventBus()
    
    await bus.connect()
    
    mock_aio_pika.assert_called_once_with("amqp://guest:guest@localhost:5672/")
    bus._connection.channel.assert_called_once()
    bus._channel.set_qos.assert_called_once_with(prefetch_count=10)
    bus._channel.declare_exchange.assert_called_once()

@pytest.mark.asyncio
async def test_connect_already_connected(mock_aio_pika):
    EventBus._instance = None
    bus = EventBus()
    bus._connection = AsyncMock()
    bus._connection.is_closed = False
    
    await bus.connect()
    mock_aio_pika.assert_not_called()

@pytest.mark.asyncio
async def test_disconnect(event_bus, mock_settings):
    connection_mock = event_bus._connection
    
    await event_bus.disconnect()
    
    connection_mock.close.assert_called_once()
    assert event_bus._connection is None
    assert event_bus._channel is None
    assert event_bus._exchange is None

@pytest.mark.asyncio
async def test_publish(event_bus):
    event = DomainEvent(event_type="test.event", payload={"k": "v"})
    
    await event_bus.publish(event)
    
    event_bus._exchange.publish.assert_called_once()
    call_args = event_bus._exchange.publish.call_args
    assert call_args[1]["routing_key"] == "test.event"
    message = call_args[0][0]
    assert json.loads(message.body.decode())["payload"] == {"k": "v"}

@pytest.mark.asyncio
async def test_publish_not_connected(event_bus):
    event_bus._connection = None
    event = DomainEvent(event_type="test.event")
    
    # Должно бросить RuntimeError
    with pytest.raises(RuntimeError, match="нет соединения с RabbitMQ"):
        await event_bus.publish(event)

@pytest.mark.asyncio
async def test_subscribe(event_bus):
    handler = AsyncMock()
    
    await event_bus.subscribe("test.event", handler)
    
    event_bus._channel.declare_queue.assert_called_once()
    queue = event_bus._channel.declare_queue.return_value
    queue.bind.assert_called_once_with(event_bus._exchange, routing_key="test.event")
    queue.consume.assert_called_once()

@pytest.mark.asyncio
async def test_subscribe_not_connected(event_bus):
    event_bus._connection = None
    handler = AsyncMock()
    
    # Должно бросить RuntimeError
    with pytest.raises(RuntimeError, match="нет соединения с RabbitMQ"):
        await event_bus.subscribe("test.event", handler)

@pytest.mark.asyncio
async def test_consumer_processing(event_bus):
    handler = AsyncMock()
    event_bus._handlers["test.event"] = [handler]
    
    consumer = event_bus._make_consumer("test.event")
    
    # Mock incoming message
    message = MagicMock()
    message.process.return_value.__aenter__.return_value = None
    message.process.return_value.__aexit__.return_value = None
    
    event = DomainEvent(event_type="test.event", payload={"k": "v"})
    message.body = event.to_json().encode()
    
    await consumer(message)
    
    handler.assert_called_once()
    called_event = handler.call_args[0][0]
    assert called_event.event_type == "test.event"
    assert called_event.payload == {"k": "v"}

@pytest.mark.asyncio
async def test_consumer_error_handling(event_bus):
    handler = AsyncMock()
    handler.side_effect = Exception("Handler error")
    event_bus._handlers["test.event"] = [handler]
    
    consumer = event_bus._make_consumer("test.event")
    
    message = MagicMock()
    message.process.return_value.__aenter__.return_value = None
    message.process.return_value.__aexit__.return_value = None
    
    event = DomainEvent(event_type="test.event")
    message.body = event.to_json().encode()
    
    # Should not raise exception
    await consumer(message)
    
    handler.assert_called_once()

@pytest.mark.asyncio
async def test_health_check(event_bus):
    # Success
    event_bus._connection.is_closed = False
    assert await event_bus.health_check() is True
    
    # Fail
    event_bus._connection = None
    assert await event_bus.health_check() is False

@pytest.mark.asyncio
async def test_init_close_event_bus(mock_aio_pika, mock_settings):
    EventBus._instance = None
    
    await init_event_bus()
    mock_aio_pika.assert_called()
    
    await close_event_bus()
    mock_aio_pika.return_value.close.assert_called()
