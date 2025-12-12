# src/services/miniapp_bff/dependencies.py
"""
Dependency Injection для MiniApp BFF.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infra.redis_client import RedisClient
    from src.services.miniapp_bff.service import MiniAppService


# Синглтоны
_redis: "RedisClient | None" = None
_miniapp_service: "MiniAppService | None" = None
_bot_token: str = ""


async def init_dependencies(
    redis: "RedisClient",
    bot_token: str,
    users_service_url: str = "http://localhost:8084",
    trips_service_url: str = "http://localhost:8085",
    pricing_service_url: str = "http://localhost:8086",
    payments_service_url: str = "http://localhost:8087",
) -> None:
    """Инициализировать зависимости при старте приложения."""
    global _redis, _bot_token, _miniapp_service
    _redis = redis
    _bot_token = bot_token
    
    from src.services.miniapp_bff.service import MiniAppService
    _miniapp_service = MiniAppService(
        redis=redis,
        users_service_url=users_service_url,
        trips_service_url=trips_service_url,
        pricing_service_url=pricing_service_url,
        payments_service_url=payments_service_url,
    )


def get_redis() -> "RedisClient":
    """Получить клиент Redis."""
    if _redis is None:
        raise RuntimeError("Redis не инициализирован. Вызовите init_dependencies()")
    return _redis


def get_bot_token() -> str:
    """Получить токен бота для валидации initData."""
    if not _bot_token:
        raise RuntimeError("Bot token не установлен. Вызовите init_dependencies()")
    return _bot_token


def get_miniapp_service() -> "MiniAppService":
    """Получить сервис MiniApp."""
    if _miniapp_service is None:
        raise RuntimeError("MiniAppService не инициализирован. Вызовите init_dependencies()")
    return _miniapp_service


async def cleanup_dependencies() -> None:
    """Очистить ресурсы при остановке приложения."""
    global _miniapp_service
    if _miniapp_service:
        await _miniapp_service.close()
        _miniapp_service = None
