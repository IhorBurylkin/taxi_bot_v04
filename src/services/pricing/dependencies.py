# src/services/pricing/dependencies.py
"""
Зависимости для Pricing Service.
"""

from __future__ import annotations

from typing import Optional

from src.infra.database import DatabaseManager
from src.infra.redis_client import RedisClient


_db: Optional[DatabaseManager] = None
_redis: Optional[RedisClient] = None
_pricing_service: Optional["PricingService"] = None


async def init_dependencies() -> None:
    """Инициализация всех зависимостей сервиса."""
    global _db, _redis, _pricing_service
    
    from src.common.logger import log_info
    from src.common.constants import TypeMsg
    from src.services.pricing.service import PricingService
    
    _db = DatabaseManager()
    await _db.connect()
    await log_info("PostgreSQL подключён", type_msg=TypeMsg.DEBUG)
    
    _redis = RedisClient()
    await _redis.connect()
    await log_info("Redis подключён", type_msg=TypeMsg.DEBUG)
    
    _pricing_service = PricingService(_db, _redis)
    
    await log_info("Pricing Service инициализирован", type_msg=TypeMsg.INFO)


async def close_dependencies() -> None:
    """Закрытие всех ресурсов."""
    global _db, _redis
    
    from src.common.logger import log_info
    from src.common.constants import TypeMsg
    
    if _redis:
        await _redis.disconnect()
        await log_info("Redis отключён", type_msg=TypeMsg.DEBUG)
    
    if _db:
        await _db.disconnect()
        await log_info("PostgreSQL отключён", type_msg=TypeMsg.DEBUG)


async def get_db() -> DatabaseManager:
    if _db is None:
        raise RuntimeError("DatabaseManager не инициализирован")
    return _db


async def get_redis() -> RedisClient:
    if _redis is None:
        raise RuntimeError("RedisClient не инициализирован")
    return _redis


async def get_pricing_service() -> "PricingService":
    if _pricing_service is None:
        raise RuntimeError("PricingService не инициализирован")
    return _pricing_service
