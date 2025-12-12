# src/web/views/health.py
"""
Health-check эндпоинт и страница статуса системы.
"""

from __future__ import annotations

from nicegui import ui
from fastapi import Response

from src.web.app import app
from src.infra.database import get_db
from src.infra.redis_client import get_redis
from src.infra.event_bus import get_event_bus


@ui.page("/status")
async def status_page() -> None:
    """Страница статуса системы."""
    ui.label("🔧 Статус системы").classes("text-2xl font-bold mb-4")
    
    with ui.column().classes("gap-2"):
        # Проверка PostgreSQL
        db = get_db()
        db_status = await _check_db(db)
        _status_row("PostgreSQL", db_status)
        
        # Проверка Redis
        redis = get_redis()
        redis_status = await _check_redis(redis)
        _status_row("Redis", redis_status)
        
        # Проверка RabbitMQ
        event_bus = get_event_bus()
        rmq_status = await _check_rmq(event_bus)
        _status_row("RabbitMQ", rmq_status)


def _status_row(service: str, is_ok: bool) -> None:
    """Строка статуса сервиса."""
    icon = "✅" if is_ok else "❌"
    color = "text-green-600" if is_ok else "text-red-600"
    status_text = "OK" if is_ok else "DOWN"
    
    with ui.row().classes("items-center gap-2"):
        ui.label(f"{icon} {service}:").classes("font-semibold")
        ui.label(status_text).classes(color)


async def _check_db(db) -> bool:
    """Проверяет подключение к PostgreSQL."""
    try:
        result = await db.fetchval("SELECT 1")
        return result == 1
    except Exception:
        return False


async def _check_redis(redis) -> bool:
    """Проверяет подключение к Redis."""
    try:
        await redis.ping()
        return True
    except Exception:
        return False


async def _check_rmq(event_bus) -> bool:
    """Проверяет подключение к RabbitMQ."""
    try:
        return event_bus.is_connected()
    except Exception:
        return False


# REST API эндпоинт для health-check
@app.get("/health")
async def health_check() -> dict:
    """
    REST API health-check.
    
    Returns:
        dict: Статус всех сервисов
    """
    db = get_db()
    redis = get_redis()
    event_bus = get_event_bus()
    
    db_ok = await _check_db(db)
    redis_ok = await _check_redis(redis)
    rmq_ok = await _check_rmq(event_bus)
    
    all_ok = db_ok and redis_ok and rmq_ok
    
    return {
        "status": "healthy" if all_ok else "unhealthy",
        "services": {
            "postgres": "ok" if db_ok else "down",
            "redis": "ok" if redis_ok else "down",
            "rabbitmq": "ok" if rmq_ok else "down",
        },
    }
