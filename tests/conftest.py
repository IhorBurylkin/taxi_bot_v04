# tests/conftest.py
"""
Общие фикстуры и настройки для тестов.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

# Устанавливаем переменные окружения перед импортом модулей
os.environ.setdefault("BOT_TOKEN", "test_bot_token")
os.environ.setdefault("ADMIN_BOT_TOKEN", "test_admin_token")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("REDIS_PASSWORD", "")
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test_api_key")


# =============================================================================
# ФИКСТУРЫ КОНФИГУРАЦИИ
# =============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Корневая директория проекта."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def config_path(project_root: Path) -> Path:
    """Путь к файлу конфигурации."""
    return project_root / "config" / "config.json"


@pytest.fixture(scope="session")
def lang_dict_path(project_root: Path) -> Path:
    """Путь к файлу локализации."""
    return project_root / "config" / "lang_dict.json"


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Мок конфигурации для тестов."""
    return {
        "PROJECT_NAME": "taxi_bot_test",
        "VERSION": "1.0.0-test",
        "DEBUG": True,
        "LOG_LEVEL": "DEBUG",
        "ENVIRONMENT": "test",
        "LOG_TO_FILE": False,
        "LOG_FILE_PATH": "logs/test.log",
        "LOG_TO_TELEGRAM": False,
        "LOG_FORMAT": "colored",
        "BOT_TOKEN": "test_bot_token",
        "ADMIN_BOT_TOKEN": "test_admin_token",
        "USE_WEBHOOK": False,
        "WEBHOOK_HOST": "https://test.example.com",
        "WEBHOOK_PATH": "/webhook",
        "WEBAPP_HOST": "0.0.0.0",
        "WEBAPP_PORT": 8000,
        "GOOGLE_MAPS_API_KEY": "test_api_key",
        "GEOCODING_LANGUAGE": "ru",
        "DOMAIN": "test.example.com",
        "DEFAULT_LANGUAGE": "ru",
        "SUPPORTED_LANGUAGES": ["ru", "uk", "en", "de"],
        "SUPPORTED_CITIES": ["Kyiv", "Hamburg"],
        "DEFAULT_CITY": "Kyiv",
        "TIMEZONE": "Europe/Kyiv",
        "DB_HOST": "localhost",
        "DB_PORT": 5432,
        "DB_NAME": "taxi_bot_test",
        "DB_USER": "postgres",
        "DB_PASSWORD": "test_password",
        "DB_MIN_POOL_SIZE": 2,
        "DB_MAX_POOL_SIZE": 5,
        "DB_COMMAND_TIMEOUT": 30,
        "DB_RETRY_ATTEMPTS": 2,
        "DB_RETRY_DELAY": 0.5,
        "REDIS_HOST": "localhost",
        "REDIS_PORT": 6379,
        "REDIS_DB": 1,
        "REDIS_PASSWORD": "",
        "REDIS_NAMESPACE": "taxi_test",
        "REDIS_MAX_CONNECTIONS": 10,
        "PROFILE_TTL": 60,
        "ORDER_TTL": 3600,
        "DRIVER_LOCATION_TTL": 30,
        "LAST_SEEN_TTL": 60,
        "NOTIFIED_DRIVERS_TTL": 3600,
        "SESSION_TTL": 600,
        "RABBITMQ_HOST": "localhost",
        "RABBITMQ_PORT": 5672,
        "RABBITMQ_USER": "guest",
        "RABBITMQ_PASSWORD": "guest",
        "RABBITMQ_VHOST": "/",
        "RABBITMQ_EXCHANGE": "taxi.test",
        "RABBITMQ_PREFETCH_COUNT": 5,
        "STARS_TO_USD_RATE": 0.013,
        "MIN_BALANCE_STARS": 100,
        "PLATFORM_COMMISSION_PERCENT": 15.0,
        "DRIVER_BONUS_PERCENT": 5.0,
        "WITHDRAWAL_MIN_STARS": 500,
        "BASE_FARE": 50.0,
        "FARE_PER_KM": 12.0,
        "FARE_PER_MINUTE": 3.0,
        "PICKUP_FARE": 30.0,
        "WAITING_FARE_PER_MINUTE": 5.0,
        "MIN_FARE": 80.0,
        "SURGE_MULTIPLIER_MAX": 3.0,
        "CURRENCY": "UAH",
        "SEARCH_RADIUS_MIN_KM": 1.0,
        "SEARCH_RADIUS_MAX_KM": 10.0,
        "SEARCH_RADIUS_STEP_KM": 1.0,
        "MAX_DRIVERS_TO_NOTIFY": 10,
        "DRIVER_RESPONSE_TIMEOUT": 30,
        "SEARCH_RETRY_INTERVAL": 5,
        "MAX_SEARCH_RETRIES": 3,
        "ORDER_TIMEOUT": 300,
        "DRIVER_ARRIVAL_TIMEOUT": 900,
        "RIDE_IDLE_TIMEOUT": 3600,
        "LOCATION_UPDATE_INTERVAL": 10,
        "AUTOSAVE_INTERVAL": 15,
        "HEALTH_CHECK_INTERVAL": 30,
    }


@pytest.fixture
def mock_lang_dict() -> dict[str, dict[str, str]]:
    """Мок словаря локализации для тестов."""
    return {
        "WELCOME": {
            "ru": "Добро пожаловать!",
            "uk": "Ласкаво просимо!",
            "en": "Welcome!",
            "de": "Willkommen!",
        },
        "ERROR": {
            "ru": "Произошла ошибка",
            "uk": "Сталася помилка",
            "en": "An error occurred",
            "de": "Ein Fehler ist aufgetreten",
        },
        "ORDER_CREATED": {
            "ru": "Ваш заказ создан!",
            "uk": "Ваше замовлення створено!",
            "en": "Your order has been created!",
            "de": "Ihre Bestellung wurde erstellt!",
        },
        "GREETING": {
            "ru": "Привет, {name}!",
            "uk": "Привіт, {name}!",
            "en": "Hello, {name}!",
            "de": "Hallo, {name}!",
        },
    }


# =============================================================================
# ФИКСТУРЫ ИНФРАСТРУКТУРЫ (МОКИ)
# =============================================================================

@pytest.fixture
def mock_db() -> AsyncMock:
    """Мок менеджера базы данных."""
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.execute = AsyncMock(return_value="INSERT 0 1")
    db.fetchval = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Мок клиента Redis."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    redis.get_model = AsyncMock(return_value=None)
    redis.set_model = AsyncMock(return_value=True)
    redis.geoadd = AsyncMock(return_value=1)
    redis.georadius = AsyncMock(return_value=[])
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock(return_value=True)
    redis.sadd = AsyncMock(return_value=1)
    redis.sismember = AsyncMock(return_value=False)
    return redis


@pytest.fixture
def mock_event_bus() -> AsyncMock:
    """Мок шины событий."""
    event_bus = AsyncMock()
    event_bus.publish = AsyncMock(return_value=None)
    event_bus.subscribe = AsyncMock(return_value=None)
    event_bus.is_connected = True
    return event_bus


# =============================================================================
# ФИКСТУРЫ МОДЕЛЕЙ
# =============================================================================

@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Пример данных пользователя."""
    return {
        "id": 123456789,
        "username": "test_user",
        "first_name": "Тест",
        "last_name": "Пользователь",
        "phone": "+380501234567",
        "language": "ru",
        "role": "passenger",
        "rating": 4.5,
        "trips_count": 10,
        "is_blocked": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_driver_data() -> dict[str, Any]:
    """Пример данных водителя."""
    return {
        "user_id": 987654321,
        "car_brand": "Toyota",
        "car_model": "Camry",
        "car_color": "Белый",
        "car_plate": "АА1234ВВ",
        "car_year": 2020,
        "license_number": "ABC123456",
        "license_expiry": datetime(2027, 12, 31),
        "status": "online",
        "is_verified": True,
        "completed_orders": 100,
        "cancelled_orders": 5,
        "total_earnings": 50000.0,
        "last_latitude": 50.4501,
        "last_longitude": 30.5234,
        "last_seen": datetime.now(timezone.utc),
        "balance_stars": 1000,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_order_data() -> dict[str, Any]:
    """Пример данных заказа."""
    return {
        "id": "test-order-uuid-123",
        "passenger_id": 123456789,
        "driver_id": None,
        "pickup_address": "ул. Крещатик, 1",
        "pickup_latitude": 50.4501,
        "pickup_longitude": 30.5234,
        "destination_address": "Аэропорт Борисполь",
        "destination_latitude": 50.3450,
        "destination_longitude": 30.8940,
        "distance_km": 35.5,
        "duration_minutes": 45,
        "estimated_fare": 500.0,
        "final_fare": None,
        "surge_multiplier": 1.0,
        "status": "created",
        "payment_method": "cash",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc),
        "passenger_comment": "Вызовите, когда приедете",
    }


# =============================================================================
# УТИЛИТЫ
# =============================================================================

@pytest.fixture
def temp_config_file(tmp_path: Path, mock_config: dict[str, Any]) -> Path:
    """Создаёт временный файл конфигурации."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(mock_config, ensure_ascii=False, indent=2))
    return config_file


@pytest.fixture
def temp_lang_dict_file(tmp_path: Path, mock_lang_dict: dict[str, dict[str, str]]) -> Path:
    """Создаёт временный файл локализации."""
    lang_file = tmp_path / "lang_dict.json"
    lang_file.write_text(json.dumps(mock_lang_dict, ensure_ascii=False, indent=2))
    return lang_file
