# src/infra/__init__.py
"""
Инфраструктурный слой.
Работа с внешними сервисами: PostgreSQL, Redis, RabbitMQ.
"""

from src.infra.database import DatabaseManager, get_db
from src.infra.redis_client import RedisClient, get_redis
from src.infra.event_bus import EventBus, get_event_bus

__all__ = [
    "DatabaseManager",
    "get_db",
    "RedisClient",
    "get_redis",
    "EventBus",
    "get_event_bus",
]
