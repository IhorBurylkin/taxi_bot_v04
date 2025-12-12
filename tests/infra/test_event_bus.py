# tests/infra/test_event_bus.py
"""
Тесты для шины событий.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

from src.infra.event_bus import DomainEvent, EventTypes, EventBus


class TestDomainEvent:
    """Тесты для DomainEvent."""
    
    def test_create_event(self) -> None:
        """Проверяет создание события."""
        event = DomainEvent(
            event_type=EventTypes.ORDER_CREATED,
            payload={"order_id": "123", "passenger_id": 456},
        )
        
        assert event.event_type == "order.created"
        assert event.payload["order_id"] == "123"
        assert event.event_id is not None
        assert event.timestamp is not None
    
    def test_event_defaults(self) -> None:
        """Проверяет значения по умолчанию."""
        event = DomainEvent()
        
        assert event.event_type == ""
        assert event.payload == {}
        assert event.event_id is not None  # UUID генерируется автоматически
        assert "Z" in event.timestamp  # ISO формат с UTC
    
    def test_to_json(self) -> None:
        """Проверяет сериализацию в JSON."""
        event = DomainEvent(
            event_id="test-id",
            event_type=EventTypes.ORDER_CREATED,
            timestamp="2024-01-15T12:00:00Z",
            payload={"order_id": "123"},
        )
        
        json_str = event.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["event_id"] == "test-id"
        assert parsed["event_type"] == "order.created"
        assert parsed["timestamp"] == "2024-01-15T12:00:00Z"
        assert parsed["payload"]["order_id"] == "123"
    
    def test_from_json(self) -> None:
        """Проверяет десериализацию из JSON."""
        json_str = json.dumps({
            "event_id": "test-id",
            "event_type": "order.created",
            "timestamp": "2024-01-15T12:00:00Z",
            "payload": {"order_id": "123"},
        })
        
        event = DomainEvent.from_json(json_str)
        
        assert event.event_id == "test-id"
        assert event.event_type == "order.created"
        assert event.payload["order_id"] == "123"
    
    def test_from_json_partial(self) -> None:
        """Проверяет десериализацию неполного JSON."""
        json_str = json.dumps({"event_type": "test"})
        
        event = DomainEvent.from_json(json_str)
        
        assert event.event_type == "test"
        assert event.payload == {}


class TestEventTypes:
    """Тесты для констант типов событий."""
    
    def test_order_events(self) -> None:
        """Проверяет типы событий заказов."""
        assert EventTypes.ORDER_CREATED == "order.created"
        assert EventTypes.ORDER_ACCEPTED == "order.accepted"
        assert EventTypes.ORDER_CANCELLED == "order.cancelled"
        assert EventTypes.ORDER_COMPLETED == "order.completed"
        assert EventTypes.ORDER_EXPIRED == "order.expired"
    
    def test_driver_events(self) -> None:
        """Проверяет типы событий водителей."""
        assert EventTypes.DRIVER_ONLINE == "driver.online"
        assert EventTypes.DRIVER_OFFLINE == "driver.offline"
        assert EventTypes.DRIVER_LOCATION_UPDATED == "driver.location_updated"
    
    def test_notification_events(self) -> None:
        """Проверяет типы событий уведомлений."""
        assert EventTypes.NOTIFICATION_SEND == "notification.send"
    
    def test_payment_events(self) -> None:
        """Проверяет типы событий платежей."""
        assert EventTypes.PAYMENT_COMPLETED == "payment.completed"
        assert EventTypes.PAYMENT_FAILED == "payment.failed"


class TestEventBus:
    """Тесты для EventBus."""
    
    @pytest.fixture
    def event_bus(self) -> EventBus:
        """Создаёт экземпляр EventBus для тестов."""
        # Сбрасываем синглтон для каждого теста
        EventBus._instance = None
        bus = EventBus()
        bus._handlers = {}
        bus._queues = {}
        return bus
    
    def test_singleton(self) -> None:
        """Проверяет паттерн Singleton."""
        EventBus._instance = None
        
        bus1 = EventBus()
        bus2 = EventBus()
        
        assert bus1 is bus2
    
    def test_is_connected_false(self, event_bus: EventBus) -> None:
        """Проверяет is_connected когда не подключено."""
        event_bus._connection = None
        
        assert event_bus.is_connected is False
    
    def test_is_connected_closed(self, event_bus: EventBus) -> None:
        """Проверяет is_connected когда соединение закрыто."""
        mock_connection = MagicMock()
        mock_connection.is_closed = True
        event_bus._connection = mock_connection
        
        assert event_bus.is_connected is False
    
    def test_is_connected_true(self, event_bus: EventBus) -> None:
        """Проверяет is_connected когда подключено."""
        mock_connection = MagicMock()
        mock_connection.is_closed = False
        event_bus._connection = mock_connection
        event_bus._channel = MagicMock()
        
        assert event_bus.is_connected is True
    
    @pytest.mark.asyncio
    async def test_connect(self, event_bus: EventBus) -> None:
        """Проверяет подключение к RabbitMQ."""
        mock_connection = MagicMock()
        mock_connection.is_closed = False
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()
        
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_channel.set_qos = AsyncMock()
        
        with patch("aio_pika.connect_robust", new_callable=AsyncMock, return_value=mock_connection):
            await event_bus.connect(
                url="amqp://guest:guest@localhost/",
                exchange_name="test.events",
                prefetch_count=5,
            )
        
        assert event_bus._connection is not None
        assert event_bus._channel is not None
        assert event_bus._exchange is not None
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self, event_bus: EventBus) -> None:
        """Проверяет, что повторное подключение пропускается."""
        mock_connection = MagicMock()
        mock_connection.is_closed = False
        event_bus._connection = mock_connection
        
        with patch("aio_pika.connect_robust") as mock_connect:
            await event_bus.connect(url="amqp://localhost/")
        
        mock_connect.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, event_bus: EventBus) -> None:
        """Проверяет отключение от RabbitMQ."""
        mock_connection = AsyncMock()
        event_bus._connection = mock_connection
        event_bus._channel = MagicMock()
        event_bus._exchange = MagicMock()
        event_bus._queues = {"test": MagicMock()}
        
        await event_bus.disconnect()
        
        mock_connection.close.assert_called_once()
        assert event_bus._connection is None
        assert event_bus._channel is None
        assert event_bus._exchange is None
        assert event_bus._queues == {}
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, event_bus: EventBus) -> None:
        """Проверяет отключение, когда соединение не установлено."""
        event_bus._connection = None
        
        # Не должно вызывать исключений
        await event_bus.disconnect()
    
    @pytest.mark.asyncio
    async def test_publish(self, event_bus: EventBus) -> None:
        """Проверяет публикацию события."""
        mock_connection = MagicMock()
        mock_connection.is_closed = False
        mock_exchange = AsyncMock()
        
        event_bus._connection = mock_connection
        event_bus._exchange = mock_exchange
        
        event = DomainEvent(
            event_type=EventTypes.ORDER_CREATED,
            payload={"order_id": "123"},
        )
        
        await event_bus.publish(event)
        
        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args
        assert call_args[1]["routing_key"] == "order.created"
    
    @pytest.mark.asyncio
    async def test_publish_not_connected(self, event_bus: EventBus) -> None:
        """Проверяет публикацию при отсутствии соединения."""
        event_bus._connection = None
        event_bus._exchange = None
        
        event = DomainEvent(event_type=EventTypes.ORDER_CREATED)
        
        # Должно бросить RuntimeError
        with pytest.raises(RuntimeError, match="нет соединения с RabbitMQ"):
            await event_bus.publish(event)
    
    @pytest.mark.asyncio
    async def test_subscribe(self, event_bus: EventBus) -> None:
        """Проверяет подписку на события."""
        mock_connection = MagicMock()
        mock_connection.is_closed = False
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        mock_exchange = MagicMock()
        
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
        mock_queue.bind = AsyncMock()
        mock_queue.consume = AsyncMock()
        
        event_bus._connection = mock_connection  # Добавляем connection для is_connected
        event_bus._channel = mock_channel
        event_bus._exchange = mock_exchange
        
        async def handler(event: DomainEvent) -> None:
            pass
        
        await event_bus.subscribe(
            event_type=EventTypes.ORDER_CREATED,
            handler=handler,
            queue_name="test_queue",
        )
        
        # Проверяем, что очередь была создана и привязана
        mock_channel.declare_queue.assert_called()
        mock_queue.bind.assert_called()
    
    def test_register_handler(self, event_bus: EventBus) -> None:
        """Проверяет регистрацию обработчика."""
        async def handler(event: DomainEvent) -> None:
            pass
        
        event_bus._handlers = {}
        
        # Регистрируем обработчик напрямую
        event_type = EventTypes.ORDER_CREATED
        if event_type not in event_bus._handlers:
            event_bus._handlers[event_type] = []
        event_bus._handlers[event_type].append(handler)
        
        assert EventTypes.ORDER_CREATED in event_bus._handlers
        assert handler in event_bus._handlers[EventTypes.ORDER_CREATED]
