# src/services/users/dependencies.py
"""
Зависимости для Users Service.
Инициализация и управление ресурсами.
"""

from __future__ import annotations

from typing import Optional

from src.infra.database import DatabaseManager
from src.infra.redis_client import RedisClient
from src.infra.event_bus import EventBus


# Глобальные экземпляры ресурсов
_db: Optional[DatabaseManager] = None
_redis: Optional[RedisClient] = None
_event_bus: Optional[EventBus] = None

# Сервисы
_user_service: Optional["UserService"] = None
_driver_service: Optional["DriverService"] = None


async def init_dependencies() -> None:
    """Инициализация всех зависимостей сервиса."""
    global _db, _redis, _event_bus, _user_service, _driver_service
    
    from src.common.logger import log_info
    from src.common.constants import TypeMsg
    from src.services.users.service import UserService, DriverService
    
    # Инициализация инфраструктуры
    _db = DatabaseManager()
    await _db.connect()
    await log_info("PostgreSQL подключён", type_msg=TypeMsg.DEBUG)
    
    _redis = RedisClient()
    await _redis.connect()
    await log_info("Redis подключён", type_msg=TypeMsg.DEBUG)
    
    _event_bus = EventBus()
    await _event_bus.connect()
    await log_info("RabbitMQ подключён", type_msg=TypeMsg.DEBUG)
    
    # Инициализация сервисов
    _user_service = UserService(_db, _redis, _event_bus)
    _driver_service = DriverService(_db, _redis, _event_bus)
    
    await log_info("Users Service инициализирован", type_msg=TypeMsg.INFO)


async def close_dependencies() -> None:
    """Закрытие всех ресурсов."""
    global _db, _redis, _event_bus
    
    from src.common.logger import log_info
    from src.common.constants import TypeMsg
    
    if _event_bus:
        await _event_bus.close()
        await log_info("RabbitMQ отключён", type_msg=TypeMsg.DEBUG)
    
    if _redis:
        await _redis.close()
        await log_info("Redis отключён", type_msg=TypeMsg.DEBUG)
    
    if _db:
        await _db.close()
        await log_info("PostgreSQL отключён", type_msg=TypeMsg.DEBUG)


async def get_db() -> DatabaseManager:
    """Получение экземпляра DatabaseManager."""
    if _db is None:
        raise RuntimeError("DatabaseManager не инициализирован")
    return _db


async def get_redis() -> RedisClient:
    """Получение экземпляра RedisClient."""
    if _redis is None:
        raise RuntimeError("RedisClient не инициализирован")
    return _redis


async def get_event_bus() -> EventBus:
    """Получение экземпляра EventBus."""
    if _event_bus is None:
        raise RuntimeError("EventBus не инициализирован")
    return _event_bus


async def get_user_service() -> "UserService":
    """Получение экземпляра UserService."""
    if _user_service is None:
        raise RuntimeError("UserService не инициализирован")
    return _user_service


async def get_driver_service() -> "DriverService":
    """Получение экземпляра DriverService."""
    if _driver_service is None:
        raise RuntimeError("DriverService не инициализирован")
    return _driver_service
