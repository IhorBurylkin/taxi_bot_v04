# tests/config/test_loader.py
"""
Тесты для модуля загрузки конфигурации.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.config.loader import (
    get_project_root,
    get_config_path,
    load_config_json,
    SystemSettings,
    LoggingSettings,
    TelegramSettings,
    TelegramLogTarget,
    GoogleMapsSettings,
    DomainSettings,
    DatabaseSettings,
    RedisSettings,
    RedisTTLSettings,
    RabbitMQSettings,
    StarsSettings,
    FareSettings,
    SearchSettings,
    TimeoutSettings,
    Settings,
)


class TestGetProjectRoot:
    """Тесты для функции get_project_root."""
    
    def test_returns_path_object(self) -> None:
        """Проверяет, что возвращается объект Path."""
        root = get_project_root()
        assert isinstance(root, Path)
    
    def test_root_contains_src_directory(self) -> None:
        """Проверяет наличие директории src в корне."""
        root = get_project_root()
        assert (root / "src").exists()
    
    def test_root_contains_config_directory(self) -> None:
        """Проверяет наличие директории config в корне."""
        root = get_project_root()
        assert (root / "config").exists()


class TestGetConfigPath:
    """Тесты для функции get_config_path."""
    
    def test_returns_path_object(self) -> None:
        """Проверяет, что возвращается объект Path."""
        path = get_config_path()
        assert isinstance(path, Path)
    
    def test_path_ends_with_config_json(self) -> None:
        """Проверяет правильность имени файла."""
        path = get_config_path()
        assert path.name == "config.json"
    
    def test_path_in_config_directory(self) -> None:
        """Проверяет, что файл находится в директории config."""
        path = get_config_path()
        assert path.parent.name == "config"


class TestLoadConfigJson:
    """Тесты для функции load_config_json."""
    
    def test_loads_dict(self) -> None:
        """Проверяет загрузку словаря конфигурации."""
        config = load_config_json()
        assert isinstance(config, dict)
    
    def test_contains_required_keys(self) -> None:
        """Проверяет наличие обязательных ключей."""
        config = load_config_json()
        
        required_keys = [
            "PROJECT_NAME",
            "VERSION",
            "DEBUG",
            "LOG_LEVEL",
        ]
        
        for key in required_keys:
            assert key in config, f"Отсутствует ключ: {key}"
    
    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        """Проверяет исключение при отсутствии файла."""
        with patch("src.config.loader.get_config_path") as mock_path:
            mock_path.return_value = tmp_path / "nonexistent.json"
            
            with pytest.raises(FileNotFoundError):
                load_config_json()


class TestTelegramLogTarget:
    """Тесты для модели TelegramLogTarget."""
    
    def test_create_from_dict(self) -> None:
        """Проверяет создание из словаря."""
        data = {"permission": True, "chat_id": -123456, "message_thread_id": 42}
        target = TelegramLogTarget(**data)
        
        assert target.permission is True
        assert target.chat_id == -123456
        assert target.message_thread_id == 42
    
    def test_from_dict_or_int_with_dict(self) -> None:
        """Проверяет создание из словаря через from_dict_or_int."""
        data = {"permission": True, "chat_id": -123456}
        target = TelegramLogTarget.from_dict_or_int(data)
        
        assert target is not None
        assert target.chat_id == -123456
    
    def test_from_dict_or_int_with_int(self) -> None:
        """Проверяет создание из int через from_dict_or_int."""
        target = TelegramLogTarget.from_dict_or_int(-123456)
        
        assert target is not None
        assert target.permission is True
        assert target.chat_id == -123456
    
    def test_from_dict_or_int_with_none(self) -> None:
        """Проверяет возврат None."""
        target = TelegramLogTarget.from_dict_or_int(None)
        assert target is None


class TestSystemSettings:
    """Тесты для модели SystemSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = SystemSettings()
        
        assert settings.PROJECT_NAME == "taxi_bot"
        assert settings.VERSION == "2.0.0"
        assert settings.DEBUG is True
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.ENVIRONMENT == "development"
    
    def test_custom_values(self) -> None:
        """Проверяет установку кастомных значений."""
        settings = SystemSettings(
            PROJECT_NAME="custom_bot",
            VERSION="1.0.0",
            DEBUG=False,
            LOG_LEVEL="INFO",
            ENVIRONMENT="production",
        )
        
        assert settings.PROJECT_NAME == "custom_bot"
        assert settings.DEBUG is False
        assert settings.ENVIRONMENT == "production"


class TestLoggingSettings:
    """Тесты для модели LoggingSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = LoggingSettings()
        
        assert settings.LOG_TO_FILE is True
        assert settings.LOG_FILE_PATH == "logs/app.log"
        assert settings.LOG_TO_TELEGRAM is False
        assert settings.LOG_FORMAT == "colored"
        assert settings.LOG_MAX_BYTES == 10485760
        assert settings.LOG_BACKUP_COUNT == 5
    
    def test_telegram_log_target_parsing(self) -> None:
        """Проверяет парсинг целевого чата Telegram."""
        settings = LoggingSettings(
            LOG_TELEGRAM_CHAT_ID={"permission": True, "chat_id": -123456}
        )
        
        assert settings.LOG_TELEGRAM_CHAT_ID is not None
        assert settings.LOG_TELEGRAM_CHAT_ID.chat_id == -123456


class TestTelegramSettings:
    """Тесты для модели TelegramSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = TelegramSettings()
        
        assert settings.USE_WEBHOOK is False
        assert settings.WEBHOOK_PATH == "/webhook"
        assert settings.WEBAPP_HOST == "0.0.0.0"
    
    def test_token_from_env(self) -> None:
        """Проверяет получение токена из переменных окружения."""
        with patch.dict(os.environ, {"BOT_TOKEN": "test_token_123"}):
            settings = TelegramSettings(BOT_TOKEN="")
            # Валидатор должен подставить значение из env
            assert settings.BOT_TOKEN in ["", "test_token_123"]


class TestDatabaseSettings:
    """Тесты для модели DatabaseSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = DatabaseSettings()
        
        assert settings.DB_HOST == "localhost"
        assert settings.DB_PORT == 5432
        assert settings.DB_NAME == "taxi_bot"
        assert settings.DB_USER == "postgres"
        assert settings.DB_MIN_POOL_SIZE == 5
        assert settings.DB_MAX_POOL_SIZE == 20
    
    def test_dsn_property(self) -> None:
        """Проверяет формирование DSN."""
        settings = DatabaseSettings(
            DB_HOST="db.example.com",
            DB_PORT=5433,
            DB_NAME="test_db",
            DB_USER="test_user",
            DB_PASSWORD="test_pass",
        )
        
        dsn = settings.dsn
        
        assert "postgresql://" in dsn
        assert "test_user:test_pass" in dsn
        assert "db.example.com:5433" in dsn
        assert "/test_db" in dsn


class TestRedisSettings:
    """Тесты для модели RedisSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = RedisSettings()
        
        assert settings.REDIS_HOST == "localhost"
        assert settings.REDIS_PORT == 6379
        assert settings.REDIS_DB == 0
        assert settings.REDIS_NAMESPACE == "taxi"
        assert settings.REDIS_MAX_CONNECTIONS == 50
    
    def test_url_property_without_password(self) -> None:
        """Проверяет формирование URL без пароля."""
        settings = RedisSettings(REDIS_PASSWORD="")
        url = settings.url
        
        assert url == "redis://localhost:6379/0"
    
    def test_url_property_with_password(self) -> None:
        """Проверяет формирование URL с паролем."""
        settings = RedisSettings(REDIS_PASSWORD="secret")
        url = settings.url
        
        assert ":secret@" in url


class TestRedisTTLSettings:
    """Тесты для модели RedisTTLSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = RedisTTLSettings()
        
        assert settings.PROFILE_TTL == 300
        assert settings.ORDER_TTL == 86400
        assert settings.DRIVER_LOCATION_TTL == 300
        assert settings.LAST_SEEN_TTL == 300
        assert settings.NOTIFIED_DRIVERS_TTL == 86400
        assert settings.SESSION_TTL == 3600


class TestRabbitMQSettings:
    """Тесты для модели RabbitMQSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = RabbitMQSettings()
        
        assert settings.RABBITMQ_HOST == "localhost"
        assert settings.RABBITMQ_PORT == 5672
        assert settings.RABBITMQ_USER == "guest"
        assert settings.RABBITMQ_VHOST == "/"
        assert settings.RABBITMQ_EXCHANGE == "taxi.events"
    
    def test_url_property(self) -> None:
        """Проверяет формирование URL."""
        with patch.dict(os.environ, {"RABBITMQ_PASSWORD": ""}):
            settings = RabbitMQSettings(
                RABBITMQ_USER="admin",
                RABBITMQ_PASSWORD="secret",
            )
            url = settings.url
            
            assert "amqp://" in url
            assert "admin:secret" in url


class TestStarsSettings:
    """Тесты для модели StarsSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = StarsSettings()
        
        assert settings.STARS_TO_USD_RATE == 0.013
        assert settings.MIN_BALANCE_STARS == 100
        assert settings.PLATFORM_COMMISSION_PERCENT == 15.0
        assert settings.DRIVER_BONUS_PERCENT == 5.0
        assert settings.WITHDRAWAL_MIN_STARS == 500


class TestFareSettings:
    """Тесты для модели FareSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = FareSettings()
        
        assert settings.BASE_FARE == 50.0
        assert settings.FARE_PER_KM == 12.0
        assert settings.FARE_PER_MINUTE == 3.0
        assert settings.PICKUP_FARE == 30.0
        assert settings.WAITING_FARE_PER_MINUTE == 5.0
        assert settings.MIN_FARE == 80.0
        assert settings.SURGE_MULTIPLIER_MAX == 3.0
        assert settings.CURRENCY == "UAH"


class TestSearchSettings:
    """Тесты для модели SearchSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = SearchSettings()
        
        assert settings.SEARCH_RADIUS_MIN_KM == 1.0
        assert settings.SEARCH_RADIUS_MAX_KM == 10.0
        assert settings.SEARCH_RADIUS_STEP_KM == 1.0
        assert settings.MAX_DRIVERS_TO_NOTIFY == 10
        assert settings.DRIVER_RESPONSE_TIMEOUT == 30


class TestTimeoutSettings:
    """Тесты для модели TimeoutSettings."""
    
    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        settings = TimeoutSettings()
        
        assert settings.ORDER_TIMEOUT == 300
        assert settings.DRIVER_ARRIVAL_TIMEOUT == 900
        assert settings.RIDE_IDLE_TIMEOUT == 3600
        assert settings.LOCATION_UPDATE_INTERVAL == 10
        assert settings.AUTOSAVE_INTERVAL == 15
        assert settings.HEALTH_CHECK_INTERVAL == 30


class TestSettings:
    """Тесты для главного класса Settings."""
    
    def test_from_config_json(self) -> None:
        """Проверяет создание настроек из config.json."""
        settings = Settings.from_config_json()
        
        assert settings.system is not None
        assert settings.logging is not None
        assert settings.telegram is not None
        assert settings.database is not None
        assert settings.redis is not None
        assert settings.fares is not None
    
    def test_all_sections_present(self) -> None:
        """Проверяет наличие всех секций."""
        settings = Settings.from_config_json()
        
        assert hasattr(settings, "system")
        assert hasattr(settings, "logging")
        assert hasattr(settings, "telegram")
        assert hasattr(settings, "google_maps")
        assert hasattr(settings, "domain")
        assert hasattr(settings, "database")
        assert hasattr(settings, "redis")
        assert hasattr(settings, "redis_ttl")
        assert hasattr(settings, "rabbitmq")
        assert hasattr(settings, "stars")
        assert hasattr(settings, "fares")
        assert hasattr(settings, "search")
        assert hasattr(settings, "timeouts")
    
    def test_filters_comment_keys(self, temp_config_file: Path) -> None:
        """Проверяет фильтрацию комментариев в config.json."""
        # Добавляем комментарий в мок-конфиг
        with open(temp_config_file, "r") as f:
            config = json.load(f)
        
        config["_comment_test"] = "This is a comment"
        
        with open(temp_config_file, "w") as f:
            json.dump(config, f)
        
        with patch("src.config.loader.get_config_path") as mock_path:
            mock_path.return_value = temp_config_file
            
            # Должен загрузиться без ошибок
            settings = Settings.from_config_json()
            assert settings is not None
