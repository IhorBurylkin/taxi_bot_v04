# src/services/payments/dependencies.py
"""
Dependency Injection для Payments Service.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infra.database import DatabaseManager
    from src.infra.redis_client import RedisClient
    from src.infra.event_bus import EventBus
    from src.services.payments.service import PaymentService, WithdrawalService


# Синглтоны для инфраструктуры
_db: "DatabaseManager | None" = None
_redis: "RedisClient | None" = None
_event_bus: "EventBus | None" = None

# Синглтоны для сервисов
_payment_service: "PaymentService | None" = None
_withdrawal_service: "WithdrawalService | None" = None


async def init_dependencies(
    db: "DatabaseManager",
    redis: "RedisClient",
    event_bus: "EventBus",
) -> None:
    """Инициализировать зависимости при старте приложения."""
    global _db, _redis, _event_bus
    _db = db
    _redis = redis
    _event_bus = event_bus


def get_db() -> "DatabaseManager":
    """Получить менеджер базы данных."""
    if _db is None:
        raise RuntimeError("База данных не инициализирована. Вызовите init_dependencies()")
    return _db


def get_redis() -> "RedisClient":
    """Получить клиент Redis."""
    if _redis is None:
        raise RuntimeError("Redis не инициализирован. Вызовите init_dependencies()")
    return _redis


def get_event_bus() -> "EventBus":
    """Получить шину событий."""
    if _event_bus is None:
        raise RuntimeError("EventBus не инициализирован. Вызовите init_dependencies()")
    return _event_bus


def get_payment_service() -> "PaymentService":
    """Получить сервис платежей."""
    global _payment_service
    
    if _payment_service is None:
        from src.services.payments.service import PaymentService
        _payment_service = PaymentService(
            db=get_db(),
            redis=get_redis(),
            event_bus=get_event_bus(),
        )
    
    return _payment_service


def get_withdrawal_service() -> "WithdrawalService":
    """Получить сервис выводов."""
    global _withdrawal_service
    
    if _withdrawal_service is None:
        from src.services.payments.service import WithdrawalService
        _withdrawal_service = WithdrawalService(
            db=get_db(),
            redis=get_redis(),
            event_bus=get_event_bus(),
            payment_service=get_payment_service(),
        )
    
    return _withdrawal_service


async def cleanup_dependencies() -> None:
    """Очистить ресурсы при остановке приложения."""
    global _payment_service, _withdrawal_service
    _payment_service = None
    _withdrawal_service = None
