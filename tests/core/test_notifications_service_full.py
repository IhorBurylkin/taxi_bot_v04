import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.notifications.service import NotificationService, NotificationData
from src.infra.event_bus import EventTypes, DomainEvent

@pytest.fixture
def mock_event_bus():
    return AsyncMock()

@pytest.fixture
def mock_get_text():
    with patch("src.core.notifications.service.get_text") as mock:
        mock.side_effect = lambda key, lang, **kwargs: f"[{lang}] {key} {kwargs}"
        yield mock

@pytest.fixture
def mock_settings():
    with patch("src.config.settings") as mock:
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
def service(mock_event_bus, mock_settings):
    return NotificationService(mock_event_bus)

@pytest.mark.asyncio
async def test_send_notification_success(service, mock_event_bus, mock_get_text):
    data = NotificationData(
        user_id=123,
        message_key="TEST_KEY",
        language="en",
        kwargs={"param": "value"}
    )
    
    result = await service.send_notification(data)
    
    assert result is True
    mock_get_text.assert_called_once_with("TEST_KEY", "en", param="value")
    mock_event_bus.publish.assert_called_once()
    
    event = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event, DomainEvent)
    assert event.event_type == EventTypes.NOTIFICATION_SEND
    assert event.payload["user_id"] == 123
    assert event.payload["text"] == "[en] TEST_KEY {'param': 'value'}"

@pytest.mark.asyncio
async def test_send_notification_error(service, mock_event_bus, mock_get_text):
    mock_event_bus.publish.side_effect = Exception("Bus error")
    
    data = NotificationData(user_id=123, message_key="TEST_KEY")
    result = await service.send_notification(data)
    
    assert result is False

@pytest.mark.asyncio
async def test_notify_order_created(service, mock_event_bus, mock_get_text):
    await service.notify_order_created(123, "ru")
    
    mock_get_text.assert_called_with("ORDER_CREATED", "ru")
    mock_event_bus.publish.assert_called_once()

@pytest.mark.asyncio
async def test_notify_driver_found(service, mock_event_bus, mock_get_text):
    await service.notify_driver_found(123, "Driver Name", "Car Info", "ru")
    
    mock_get_text.assert_called_with("ORDER_ACCEPTED", "ru")
    mock_event_bus.publish.assert_called_once()

@pytest.mark.asyncio
async def test_notify_new_order(service, mock_event_bus, mock_get_text):
    await service.notify_new_order(
        driver_id=456,
        pickup="A",
        destination="B",
        fare=100.0,
        currency="RUB",
        language="en"
    )
    
    mock_get_text.assert_called_with(
        "NEW_ORDER_NOTIFICATION",
        "en",
        pickup="A",
        destination="B",
        fare=100.0,
        currency="RUB"
    )
    mock_event_bus.publish.assert_called_once()

@pytest.mark.asyncio
async def test_notify_driver_arrived(service, mock_event_bus, mock_get_text):
    await service.notify_driver_arrived(123, "ru")
    
    mock_get_text.assert_called_with("DRIVER_ARRIVED", "ru")
    mock_event_bus.publish.assert_called_once()

@pytest.mark.asyncio
async def test_notify_ride_started(service, mock_event_bus, mock_get_text):
    await service.notify_ride_started(123, "ru")
    
    mock_get_text.assert_called_with("RIDE_STARTED", "ru")
    mock_event_bus.publish.assert_called_once()

@pytest.mark.asyncio
async def test_notify_order_completed(service, mock_event_bus, mock_get_text):
    await service.notify_order_completed(
        user_id=123,
        fare=150.0,
        currency="RUB",
        distance_km=5.0,
        duration_min=10,
        language="ru"
    )
    
    mock_get_text.assert_called_with(
        "FARE_DETAILS",
        "ru",
        fare=150.0,
        currency="RUB",
        distance=5.0,
        duration=10
    )
    mock_event_bus.publish.assert_called_once()

@pytest.mark.asyncio
async def test_notify_order_cancelled(service, mock_event_bus, mock_get_text):
    await service.notify_order_cancelled(123, "ru")
    
    mock_get_text.assert_called_with("ORDER_CANCELLED", "ru")
    mock_event_bus.publish.assert_called_once()

@pytest.mark.asyncio
async def test_notify_no_drivers(service, mock_event_bus, mock_get_text):
    await service.notify_no_drivers(123, "ru")
    
    mock_get_text.assert_called_with("NO_DRIVERS_AVAILABLE", "ru")
    mock_event_bus.publish.assert_called_once()
