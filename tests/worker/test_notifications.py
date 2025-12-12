import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.worker.notifications import NotificationWorker
from src.infra.event_bus import DomainEvent, EventTypes

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
    return MagicMock()

@pytest.fixture
def worker(mock_event_bus, mock_db, mock_redis):
    return NotificationWorker(
        event_bus=mock_event_bus,
        db=mock_db,
        redis=mock_redis
    )

@pytest.mark.asyncio
async def test_worker_initialization(worker):
    assert worker.name == "NotificationWorker"
    assert EventTypes.DRIVER_ORDER_OFFERED in worker.subscriptions
    assert EventTypes.ORDER_ACCEPTED in worker.subscriptions

@pytest.mark.asyncio
async def test_start_stop(worker):
    with patch("src.worker.notifications.Bot") as MockBot:
        mock_bot_instance = MockBot.return_value
        mock_bot_instance.session.close = AsyncMock()
        
        await worker.start()
        assert worker._bot is not None
        
        await worker.stop()
        mock_bot_instance.session.close.assert_called_once()

@pytest.mark.asyncio
async def test_handle_event_driver_order_offered(worker):
    worker._send_message = AsyncMock(return_value=True)
    
    event = DomainEvent(
        event_type=EventTypes.DRIVER_ORDER_OFFERED,
        payload={
            "driver_id": 101,
            "order_id": 1,
            "distance": 1.5
        }
    )
    
    await worker.handle_event(event)
    
    worker._send_message.assert_called_once()
    args = worker._send_message.call_args[0]
    assert args[0] == 101
    assert "Новый заказ" in args[1]
    assert "1.5 км" in args[1]

@pytest.mark.asyncio
async def test_handle_event_order_accepted(worker):
    worker._send_message = AsyncMock(return_value=True)
    
    event = DomainEvent(
        event_type=EventTypes.ORDER_ACCEPTED,
        payload={
            "passenger_id": 202,
            "driver_name": "Ivan",
            "car_info": "White Toyota",
            "eta": 7
        }
    )
    
    await worker.handle_event(event)
    
    worker._send_message.assert_called_once()
    args = worker._send_message.call_args[0]
    assert args[0] == 202
    assert "Заказ принят" in args[1]
    assert "Ivan" in args[1]
    assert "White Toyota" in args[1]
    assert "7 мин" in args[1]

@pytest.mark.asyncio
async def test_handle_event_order_cancelled(worker):
    worker._send_message = AsyncMock(return_value=True)
    
    event = DomainEvent(
        event_type=EventTypes.ORDER_CANCELLED,
        payload={
            "notify_users": [101, 202],
            "reason": "Driver cancelled"
        }
    )
    
    await worker.handle_event(event)
    
    assert worker._send_message.call_count == 2
    # Check calls
    calls = worker._send_message.call_args_list
    assert calls[0][0][0] == 101
    assert calls[1][0][0] == 202
    assert "Заказ отменён" in calls[0][0][1]
    assert "Driver cancelled" in calls[0][0][1]

@pytest.mark.asyncio
async def test_handle_event_order_completed(worker):
    worker._send_message = AsyncMock(return_value=True)
    
    event = DomainEvent(
        event_type=EventTypes.ORDER_COMPLETED,
        payload={
            "passenger_id": 202,
            "driver_id": 101,
            "fare": 500
        }
    )
    
    await worker.handle_event(event)
    
    assert worker._send_message.call_count == 2
    
    # We can't guarantee order of calls, so we check if both were called
    call_args = [c[0] for c in worker._send_message.call_args_list]
    ids = [args[0] for args in call_args]
    assert 202 in ids
    assert 101 in ids
    
    for args in call_args:
        if args[0] == 202:
            assert "Поездка завершена" in args[1]
            assert "500 ₽" in args[1]
        elif args[0] == 101:
            assert "Поездка завершена" in args[1]
            assert "500 ₽" in args[1]

@pytest.mark.asyncio
async def test_handle_event_driver_arrived(worker):
    worker._send_message = AsyncMock(return_value=True)
    
    event = DomainEvent(
        event_type=EventTypes.DRIVER_ARRIVED,
        payload={
            "passenger_id": 202
        }
    )
    
    await worker.handle_event(event)
    
    worker._send_message.assert_called_once()
    args = worker._send_message.call_args[0]
    assert args[0] == 202
    assert "Водитель прибыл" in args[1]

@pytest.mark.asyncio
async def test_handle_event_ride_started(worker):
    worker._send_message = AsyncMock(return_value=True)
    
    event = DomainEvent(
        event_type=EventTypes.RIDE_STARTED,
        payload={
            "passenger_id": 202,
            "destination": "Center"
        }
    )
    
    await worker.handle_event(event)
    
    worker._send_message.assert_called_once()
    args = worker._send_message.call_args[0]
    assert args[0] == 202
    assert "Поездка началась" in args[1]
    assert "Center" in args[1]


