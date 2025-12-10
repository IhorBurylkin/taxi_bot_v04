# src/infra/event_bus.py
"""
Шина событий на базе RabbitMQ.
Реализует паттерн Pub/Sub для асинхронной коммуникации между модулями.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import uuid4

import aio_pika
from aio_pika import Message, ExchangeType
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractExchange, AbstractQueue

from src.common.logger import get_logger, log_error, log_info
from src.common.constants import TypeMsg

logger = get_logger("event_bus")


# =============================================================================
# ДОМЕННЫЕ СОБЫТИЯ
# =============================================================================

@dataclass
class DomainEvent:
    """Базовый класс для доменных событий."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    payload: dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Сериализует событие в JSON."""
        return json.dumps({
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }, ensure_ascii=False, default=str)
    
    @classmethod
    def from_json(cls, data: str) -> DomainEvent:
        """Десериализует событие из JSON."""
        parsed = json.loads(data)
        return cls(
            event_id=parsed.get("event_id", str(uuid4())),
            event_type=parsed.get("event_type", ""),
            timestamp=parsed.get("timestamp", ""),
            payload=parsed.get("payload", {}),
        )


# Типы событий
class EventTypes:
    """Константы типов событий."""
    # Заказы
    ORDER_CREATED = "order.created"
    ORDER_ACCEPTED = "order.accepted"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_COMPLETED = "order.completed"
    ORDER_EXPIRED = "order.expired"
    
    # Водители
    DRIVER_ONLINE = "driver.online"
    DRIVER_OFFLINE = "driver.offline"
    DRIVER_LOCATION_UPDATED = "driver.location_updated"
    
    # Уведомления
    NOTIFICATION_SEND = "notification.send"
    
    # Биллинг
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"


# Тип обработчика событий
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """
    Шина событий на базе RabbitMQ.
    
    Реализует:
    - Публикацию событий в exchange
    - Подписку на события через очереди
    - Автоматическое переподключение
    """
    
    _instance: EventBus | None = None
    _connection: AbstractConnection | None = None
    _channel: AbstractChannel | None = None
    _exchange: AbstractExchange | None = None
    _handlers: dict[str, list[EventHandler]]
    
    def __new__(cls) -> EventBus:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Инициализация (вызывается только один раз благодаря Singleton)."""
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._connection = None
        self._channel = None
        self._exchange = None
        self._handlers = {}
        self._exchange_name = "taxi.events"
        self._queues: dict[str, AbstractQueue] = {}
    
    @property
    def is_connected(self) -> bool:
        """Проверяет, активно ли соединение."""
        return self._connection is not None and not self._connection.is_closed
    
    async def connect(
        self,
        url: str | None = None,
        exchange_name: str | None = None,
        prefetch_count: int = 10,
    ) -> None:
        """
        Подключается к RabbitMQ.
        
        Args:
            url: URL RabbitMQ (если None, берётся из конфига)
            exchange_name: Имя exchange
            prefetch_count: Количество сообщений для prefetch
        """
        if self.is_connected:
            return
        
        # Получаем URL из конфига, если не передан
        if url is None:
            from src.config import settings
            url = settings.rabbitmq.url
            exchange_name = settings.rabbitmq.RABBITMQ_EXCHANGE
            prefetch_count = settings.rabbitmq.RABBITMQ_PREFETCH_COUNT
        
        if exchange_name:
            self._exchange_name = exchange_name
        
        await log_info("Подключение к RabbitMQ...", type_msg=TypeMsg.INFO)
        
        # Подключаемся
        self._connection = await aio_pika.connect_robust(url)
        self._channel = await self._connection.channel()
        
        # Настраиваем prefetch
        await self._channel.set_qos(prefetch_count=prefetch_count)
        
        # Создаём exchange (topic для гибкой маршрутизации)
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )
        
        await log_info("Подключение к RabbitMQ установлено", type_msg=TypeMsg.INFO)
    
    async def disconnect(self) -> None:
        """Закрывает соединение с RabbitMQ."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._channel = None
            self._exchange = None
            self._queues = {}
            await log_info("Соединение с RabbitMQ закрыто", type_msg=TypeMsg.INFO)
    
    async def publish(self, event: DomainEvent) -> None:
        """
        Публикует событие в exchange.
        
        Args:
            event: Доменное событие
        """
        if not self.is_connected or self._exchange is None:
            await log_error("Не удалось опубликовать событие: нет соединения с RabbitMQ")
            return
        
        try:
            message = Message(
                body=event.to_json().encode(),
                content_type="application/json",
                message_id=event.event_id,
                timestamp=datetime.utcnow(),
            )
            
            # Используем event_type как routing_key
            await self._exchange.publish(
                message,
                routing_key=event.event_type,
            )
            
            await log_info(
                f"Событие опубликовано: {event.event_type}",
                type_msg=TypeMsg.DEBUG,
            )
        except Exception as e:
            await log_error(f"Ошибка публикации события: {e}")
    
    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        queue_name: str | None = None,
    ) -> None:
        """
        Подписывается на события определённого типа.
        
        Args:
            event_type: Тип события (routing_key pattern)
            handler: Асинхронный обработчик события
            queue_name: Имя очереди (если None, генерируется автоматически)
        """
        if not self.is_connected or self._channel is None or self._exchange is None:
            await log_error("Не удалось подписаться: нет соединения с RabbitMQ")
            return
        
        # Регистрируем обработчик
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        
        # Создаём или получаем очередь
        if queue_name is None:
            queue_name = f"taxi.{event_type.replace('.', '_')}"
        
        if queue_name not in self._queues:
            queue = await self._channel.declare_queue(
                queue_name,
                durable=True,
            )
            
            # Привязываем очередь к exchange с routing_key
            await queue.bind(self._exchange, routing_key=event_type)
            
            self._queues[queue_name] = queue
            
            # Запускаем consumer
            await queue.consume(self._make_consumer(event_type))
        
        await log_info(
            f"Подписка на события: {event_type}",
            type_msg=TypeMsg.DEBUG,
        )
    
    def _make_consumer(self, event_type: str) -> Callable:
        """Создаёт consumer для обработки сообщений."""
        async def consumer(message: aio_pika.IncomingMessage) -> None:
            async with message.process():
                try:
                    event = DomainEvent.from_json(message.body.decode())
                    
                    # Вызываем все зарегистрированные обработчики
                    handlers = self._handlers.get(event_type, [])
                    for handler in handlers:
                        try:
                            await handler(event)
                        except Exception as e:
                            await log_error(f"Ошибка в обработчике {handler.__name__}: {e}")
                    
                except Exception as e:
                    await log_error(f"Ошибка обработки сообщения: {e}")
        
        return consumer
    
    async def health_check(self) -> bool:
        """
        Проверяет здоровье подключения к RabbitMQ.
        
        Returns:
            True если подключение работает
        """
        try:
            return self.is_connected
        except Exception as e:
            await log_error(f"Health check RabbitMQ failed: {e}")
            return False


# Глобальный экземпляр
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """
    Возвращает глобальный экземпляр EventBus.
    
    Returns:
        EventBus
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def init_event_bus() -> None:
    """
    Инициализирует подключение к RabbitMQ.
    Использует настройки из конфигурации.
    """
    from src.config import settings
    
    event_bus = get_event_bus()
    await event_bus.connect(
        url=settings.rabbitmq.url,
        exchange_name=settings.rabbitmq.RABBITMQ_EXCHANGE,
        prefetch_count=settings.rabbitmq.RABBITMQ_PREFETCH_COUNT,
    )
    await log_info(f"RabbitMQ подключён: {settings.rabbitmq.RABBITMQ_HOST}:{settings.rabbitmq.RABBITMQ_PORT}", type_msg=TypeMsg.INFO)


async def close_event_bus() -> None:
    """
    Закрывает подключение к RabbitMQ.
    """
    event_bus = get_event_bus()
    await event_bus.disconnect()
    await log_info("RabbitMQ отключён", type_msg=TypeMsg.INFO)
