# src/config/loader.py
"""
Загрузчик конфигурации проекта.
Единственный источник истины — config/config.json.
Секретные данные переопределяются из переменных окружения.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


# =============================================================================
# ОПРЕДЕЛЕНИЕ ПУТЕЙ
# =============================================================================

def get_project_root() -> Path:
    """Возвращает корневую директорию проекта."""
    return Path(__file__).parent.parent.parent


def get_config_path() -> Path:
    """Возвращает путь к файлу конфигурации."""
    return get_project_root() / "config" / "config.json"


def load_config_json() -> dict[str, Any]:
    """Загружает config.json и возвращает словарь."""
    config_path = get_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# PYDANTIC МОДЕЛИ КОНФИГУРАЦИИ
# =============================================================================

class SystemSettings(BaseModel):
    """Системные настройки."""
    PROJECT_NAME: str = "taxi_bot"
    VERSION: str = "2.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    ENVIRONMENT: str = "development"
    RUN_TESTS_ON_STARTUP: bool = False
    RUN_DEV_MODE: bool = True
    COMPONENT_MODE: str = "all"


class DeploymentSettings(BaseModel):
    """Настройки развертывания компонентов."""
    # Устаревшие компоненты (обратная совместимость)
    WEB_ADMIN_INSTANCES_COUNT: int = 1
    WEB_ADMIN_PORT: int = 8081
    WEB_CLIENT_INSTANCES_COUNT: int = 1
    WEB_CLIENT_PORT: int = 8082
    NOTIFICATIONS_INSTANCES_COUNT: int = 1
    NOTIFICATIONS_PORT: int = 8083
    BOT_INSTANCES_COUNT: int = 1
    BOT_WEBAPP_PORT: int = 8000
    WORKER_INSTANCES_COUNT: int = 1
    MATCHING_WORKER_INSTANCES_COUNT: int = 1
    NGINX_PORT: int = 8080
    
    # Новые микросервисы (v0.5.0)
    USERS_SERVICE_HOST: str = "users_service"
    USERS_SERVICE_PORT: int = 8084
    USERS_SERVICE_INSTANCES_COUNT: int = 1
    TRIP_SERVICE_HOST: str = "trip_service"
    TRIP_SERVICE_PORT: int = 8085
    TRIP_SERVICE_INSTANCES_COUNT: int = 1
    PRICING_SERVICE_HOST: str = "pricing_service"
    PRICING_SERVICE_PORT: int = 8086
    PRICING_SERVICE_INSTANCES_COUNT: int = 1
    PAYMENTS_SERVICE_HOST: str = "payments_service"
    PAYMENTS_SERVICE_PORT: int = 8087
    PAYMENTS_SERVICE_INSTANCES_COUNT: int = 1
    MINIAPP_BFF_HOST: str = "miniapp_bff"
    MINIAPP_BFF_PORT: int = 8088
    MINIAPP_BFF_INSTANCES_COUNT: int = 1
    REALTIME_WS_GATEWAY_HOST: str = "realtime_ws_gateway"
    REALTIME_WS_GATEWAY_PORT: int = 8089
    REALTIME_WS_GATEWAY_INSTANCES_COUNT: int = 1
    REALTIME_LOCATION_INGEST_HOST: str = "realtime_location_ingest"
    REALTIME_LOCATION_INGEST_PORT: int = 8090
    REALTIME_LOCATION_INGEST_INSTANCES_COUNT: int = 1
    ORDER_MATCHING_SERVICE_HOST: str = "order_matching_service"
    ORDER_MATCHING_SERVICE_PORT: int = 8091
    ORDER_MATCHING_SERVICE_INSTANCES_COUNT: int = 1


class TelegramLogTarget(BaseModel):
    """Настройки целевого чата для логирования в Telegram."""
    permission: bool = False
    chat_id: int
    message_thread_id: int | None = None

    @classmethod
    def from_dict_or_int(cls, value: dict | int | None) -> "TelegramLogTarget | None":
        """Создает объект из словаря или int (обратная совместимость)."""
        if value is None:
            return None
        if isinstance(value, dict):
            return cls(**value)
        if isinstance(value, int):
            return cls(permission=True, chat_id=value)
        return None


class LoggingSettings(BaseModel):
    """Настройки логирования."""
    LOG_LEVEL: str = "DEBUG"
    LOG_TO_FILE: bool = True
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_TO_TELEGRAM: bool = False
    LOG_TELEGRAM_CHAT_ID: TelegramLogTarget | None = None
    LOG_TELEGRAM_NEW_USERS_CHAT_ID: TelegramLogTarget | None = None
    LOG_TELEGRAM_ADMINS_CHAT_ID: TelegramLogTarget | None = None
    LOG_TELEGRAM_PAYMENTS_CHAT_ID: TelegramLogTarget | None = None
    LOG_TELEGRAM_ORDERS_CHAT_ID: TelegramLogTarget | None = None
    LOG_TELEGRAM_SUPPORT_CHAT_ID: TelegramLogTarget | None = None
    LOG_TELEGRAM_SERVER_LOGS_CHAT_ID: TelegramLogTarget | None = None
    LOG_FORMAT: str = "colored"
    LOG_MAX_BYTES: int = 10485760
    LOG_BACKUP_COUNT: int = 5

    @field_validator(
        "LOG_TELEGRAM_CHAT_ID",
        "LOG_TELEGRAM_NEW_USERS_CHAT_ID",
        "LOG_TELEGRAM_ADMINS_CHAT_ID",
        "LOG_TELEGRAM_PAYMENTS_CHAT_ID",
        "LOG_TELEGRAM_ORDERS_CHAT_ID",
        "LOG_TELEGRAM_SUPPORT_CHAT_ID",
        "LOG_TELEGRAM_SERVER_LOGS_CHAT_ID",
        mode="before"
    )
    @classmethod
    def parse_telegram_target(cls, v: dict | int | None) -> TelegramLogTarget | None:
        """Парсит значение как TelegramLogTarget."""
        return TelegramLogTarget.from_dict_or_int(v)


class TelegramSettings(BaseModel):
    """Настройки Telegram API."""
    BOT_TOKEN: str = ""
    ADMIN_BOT_TOKEN: str = ""
    USE_WEBHOOK: bool = False
    WEBHOOK_HOST: str = "https://example.com"
    WEBHOOK_PATH: str = "/webhook"
    WEBHOOK_URL_MAIN: str | None = None
    WEBHOOK_URL_LOGGER: str | None = None
    WEBHOOK_SECRET: str | None = None
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8000

    @field_validator("BOT_TOKEN", "ADMIN_BOT_TOKEN", mode="before")
    @classmethod
    def get_from_env(cls, v: str, info) -> str:
        """Получает токен из переменных окружения, если не задан."""
        if not v:
            env_key = info.field_name
            return os.getenv(env_key, "")
        return v

    @model_validator(mode='after')
    def compute_webhook_urls(self) -> "TelegramSettings":
        """Вычисляет URL вебхуков, если они не заданы."""
        if not self.WEBHOOK_URL_MAIN and self.BOT_TOKEN and self.WEBHOOK_HOST:
            self.WEBHOOK_URL_MAIN = f"{self.WEBHOOK_HOST}{self.WEBHOOK_PATH}/{self.BOT_TOKEN}"
        
        if not self.WEBHOOK_URL_LOGGER and self.ADMIN_BOT_TOKEN and self.WEBHOOK_HOST:
            self.WEBHOOK_URL_LOGGER = f"{self.WEBHOOK_HOST}{self.WEBHOOK_PATH}/{self.ADMIN_BOT_TOKEN}"
            
        return self


class GoogleMapsSettings(BaseModel):
    """Настройки Google Maps API."""
    GOOGLE_MAPS_API_KEY: str = ""
    GEOCODING_LANGUAGE: str = "ru"

    @field_validator("GOOGLE_MAPS_API_KEY", mode="before")
    @classmethod
    def get_from_env(cls, v: str) -> str:
        """Получает API ключ из переменных окружения."""
        if not v:
            return os.getenv("GOOGLE_MAPS_API_KEY", "")
        return v


class DomainSettings(BaseModel):
    """Настройки домена и локализации."""
    DOMAIN: str = "taxi.example.com"
    DEFAULT_LANGUAGE: str = "ru"
    SUPPORTED_LANGUAGES: list[str] = Field(default_factory=lambda: ["ru", "uk", "en", "de"])
    SUPPORTED_CITIES: list[str] = Field(default_factory=lambda: ["Kyiv"])
    DEFAULT_CITY: str = "Kyiv"
    TIMEZONE: str = "Europe/Kyiv"


class DatabaseSettings(BaseModel):
    """Настройки PostgreSQL."""
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "taxi_bot"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    DB_MIN_POOL_SIZE: int = 5
    DB_MAX_POOL_SIZE: int = 20
    DB_COMMAND_TIMEOUT: int = 60
    DB_RETRY_ATTEMPTS: int = 3
    DB_RETRY_DELAY: float = 1.0

    @field_validator("DB_PASSWORD", mode="before")
    @classmethod
    def get_from_env(cls, v: str) -> str:
        """Получает пароль из переменных окружения."""
        if not v:
            return os.getenv("DB_PASSWORD", "")
        return v

    @property
    def dsn(self) -> str:
        """Возвращает DSN для подключения к PostgreSQL."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


class RedisSettings(BaseModel):
    """Настройки Redis."""
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_NAMESPACE: str = "taxi"
    REDIS_MAX_CONNECTIONS: int = 50

    @field_validator("REDIS_PASSWORD", mode="before")
    @classmethod
    def get_from_env(cls, v: str) -> str:
        """Получает пароль из переменных окружения."""
        if not v:
            return os.getenv("REDIS_PASSWORD", "")
        return v

    @property
    def url(self) -> str:
        """Возвращает URL для подключения к Redis."""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


class RedisTTLSettings(BaseModel):
    """Настройки TTL кэша."""
    PROFILE_TTL: int = 300
    ORDER_TTL: int = 86400
    DRIVER_LOCATION_TTL: int = 300
    LAST_SEEN_TTL: int = 300
    NOTIFIED_DRIVERS_TTL: int = 86400
    SESSION_TTL: int = 3600


class RabbitMQSettings(BaseModel):
    """Настройки RabbitMQ."""
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"
    RABBITMQ_EXCHANGE: str = "taxi.events"
    RABBITMQ_PREFETCH_COUNT: int = 10

    @field_validator("RABBITMQ_PASSWORD", mode="before")
    @classmethod
    def get_from_env(cls, v: str) -> str:
        """Получает пароль из переменных окружения."""
        env_pass = os.getenv("RABBITMQ_PASSWORD", "")
        if env_pass:
            return env_pass
        return v

    @property
    def url(self) -> str:
        """Возвращает URL для подключения к RabbitMQ."""
        return (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}{self.RABBITMQ_VHOST}"
        )


class StarsSettings(BaseModel):
    """Настройки Stars и оплаты."""
    STARS_TO_USD_RATE: float = 0.013
    MIN_BALANCE_STARS: int = 100
    PLATFORM_COMMISSION_PERCENT: float = 15.0
    DRIVER_BONUS_PERCENT: float = 5.0
    WITHDRAWAL_MIN_STARS: int = 500


class FareSettings(BaseModel):
    """Настройки тарифов."""
    BASE_FARE: float = 10.0
    FARE_PER_KM: float = 1.0
    FARE_PER_MINUTE: float = 3.0
    PICKUP_FARE: float = 30.0
    WAITING_FARE_PER_MINUTE: float = 0.25
    MIN_FARE: float = 10.0
    SURGE_MULTIPLIER_MAX: float = 3.0
    CURRENCY: str = "EUR"


class SearchSettings(BaseModel):
    """Настройки поиска водителей."""
    DRIVER_SEARCH_RADIUS_KM: float = 5.0
    SEARCH_RADIUS_MIN_KM: float = 1.0
    SEARCH_RADIUS_MAX_KM: float = 10.0
    SEARCH_RADIUS_STEP_KM: float = 1.0
    MAX_DRIVERS_TO_NOTIFY: int = 10
    DRIVER_RESPONSE_TIMEOUT: int = 30
    SEARCH_RETRY_INTERVAL: int = 5
    MAX_SEARCH_RETRIES: int = 3


class TimeoutSettings(BaseModel):
    """Настройки таймаутов и интервалов."""
    ORDER_TIMEOUT: int = 300
    DRIVER_ARRIVAL_TIMEOUT: int = 900
    RIDE_IDLE_TIMEOUT: int = 3600
    LOCATION_UPDATE_INTERVAL: int = 10
    AUTOSAVE_INTERVAL: int = 15
    HEALTH_CHECK_INTERVAL: int = 30


# =============================================================================
# ГЛАВНЫЙ КЛАСС НАСТРОЕК
# =============================================================================

class Settings(BaseSettings):
    """
    Главный класс настроек приложения.
    Агрегирует все секции конфигурации.
    """
    system: SystemSettings = Field(default_factory=SystemSettings)
    deployment: DeploymentSettings = Field(default_factory=DeploymentSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    google_maps: GoogleMapsSettings = Field(default_factory=GoogleMapsSettings)
    domain: DomainSettings = Field(default_factory=DomainSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    redis_ttl: RedisTTLSettings = Field(default_factory=RedisTTLSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    stars: StarsSettings = Field(default_factory=StarsSettings)
    fares: FareSettings = Field(default_factory=FareSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    timeouts: TimeoutSettings = Field(default_factory=TimeoutSettings)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @classmethod
    def from_config_json(cls) -> "Settings":
        """
        Создаёт объект Settings из config.json.
        Секреты переопределяются из переменных окружения.
        """
        config_data = load_config_json()
        
        # Фильтруем комментарии (ключи, начинающиеся с _comment_)
        filtered_data = {k: v for k, v in config_data.items() if not k.startswith("_comment_")}
        
        # Маппинг полей в секции
        return cls(
            system=SystemSettings(
                PROJECT_NAME=filtered_data.get("PROJECT_NAME", "taxi_bot"),
                VERSION=filtered_data.get("VERSION", "2.0.0"),
                DEBUG=filtered_data.get("DEBUG", True),
                LOG_LEVEL=filtered_data.get("LOG_LEVEL", "DEBUG"),
                ENVIRONMENT=filtered_data.get("ENVIRONMENT", "development"),
                RUN_TESTS_ON_STARTUP=filtered_data.get("RUN_TESTS_ON_STARTUP", False),
                RUN_DEV_MODE=filtered_data.get("RUN_DEV_MODE", True),
                COMPONENT_MODE=os.getenv("COMPONENT_MODE", filtered_data.get("COMPONENT_MODE", "all")),
            ),
            deployment=DeploymentSettings(
                WEB_ADMIN_INSTANCES_COUNT=filtered_data.get("WEB_ADMIN_INSTANCES_COUNT", 1),
                WEB_ADMIN_PORT=filtered_data.get("WEB_ADMIN_PORT", 8081),
                WEB_CLIENT_INSTANCES_COUNT=filtered_data.get("WEB_CLIENT_INSTANCES_COUNT", 1),
                WEB_CLIENT_PORT=filtered_data.get("WEB_CLIENT_PORT", 8082),
                NOTIFICATIONS_INSTANCES_COUNT=filtered_data.get("NOTIFICATIONS_INSTANCES_COUNT", 1),
                NOTIFICATIONS_PORT=filtered_data.get("NOTIFICATIONS_PORT", 8083),
                BOT_INSTANCES_COUNT=filtered_data.get("BOT_INSTANCES_COUNT", 1),
                BOT_WEBAPP_PORT=filtered_data.get("BOT_WEBAPP_PORT", 8000),
                WORKER_INSTANCES_COUNT=filtered_data.get("WORKER_INSTANCES_COUNT", 1),
                MATCHING_WORKER_INSTANCES_COUNT=filtered_data.get("MATCHING_WORKER_INSTANCES_COUNT", 1),
                NGINX_PORT=filtered_data.get("NGINX_PORT", 8080),
                
                USERS_SERVICE_HOST=os.getenv("USERS_SERVICE_HOST", filtered_data.get("USERS_SERVICE_HOST", "users_service")),
                USERS_SERVICE_PORT=filtered_data.get("USERS_SERVICE_PORT", 8084),
                TRIP_SERVICE_HOST=os.getenv("TRIP_SERVICE_HOST", filtered_data.get("TRIP_SERVICE_HOST", "trip_service")),
                TRIP_SERVICE_PORT=filtered_data.get("TRIP_SERVICE_PORT", 8085),
                PRICING_SERVICE_HOST=os.getenv("PRICING_SERVICE_HOST", filtered_data.get("PRICING_SERVICE_HOST", "pricing_service")),
                PRICING_SERVICE_PORT=filtered_data.get("PRICING_SERVICE_PORT", 8086),
                PAYMENTS_SERVICE_HOST=os.getenv("PAYMENTS_SERVICE_HOST", filtered_data.get("PAYMENTS_SERVICE_HOST", "payments_service")),
                PAYMENTS_SERVICE_PORT=filtered_data.get("PAYMENTS_SERVICE_PORT", 8087),
                MINIAPP_BFF_HOST=os.getenv("MINIAPP_BFF_HOST", filtered_data.get("MINIAPP_BFF_HOST", "miniapp_bff")),
                MINIAPP_BFF_PORT=filtered_data.get("MINIAPP_BFF_PORT", 8088),
                REALTIME_WS_GATEWAY_HOST=os.getenv("REALTIME_WS_GATEWAY_HOST", filtered_data.get("REALTIME_WS_GATEWAY_HOST", "realtime_ws_gateway")),
                REALTIME_WS_GATEWAY_PORT=filtered_data.get("REALTIME_WS_GATEWAY_PORT", 8089),
                REALTIME_LOCATION_INGEST_HOST=os.getenv("REALTIME_LOCATION_INGEST_HOST", filtered_data.get("REALTIME_LOCATION_INGEST_HOST", "realtime_location_ingest")),
                REALTIME_LOCATION_INGEST_PORT=filtered_data.get("REALTIME_LOCATION_INGEST_PORT", 8090),
                ORDER_MATCHING_SERVICE_HOST=os.getenv("ORDER_MATCHING_SERVICE_HOST", filtered_data.get("ORDER_MATCHING_SERVICE_HOST", "order_matching_service")),
                ORDER_MATCHING_SERVICE_PORT=filtered_data.get("ORDER_MATCHING_SERVICE_PORT", 8091),
            ),
            logging=LoggingSettings(
                LOG_TO_FILE=filtered_data.get("LOG_TO_FILE", True),
                LOG_FILE_PATH=filtered_data.get("LOG_FILE_PATH", "logs/app.log"),
                LOG_TO_TELEGRAM=filtered_data.get("LOG_TO_TELEGRAM", False),
                LOG_TELEGRAM_CHAT_ID=filtered_data.get("LOG_TELEGRAM_CHAT_ID"),
                LOG_TELEGRAM_NEW_USERS_CHAT_ID=filtered_data.get("LOG_TELEGRAM_NEW_USERS_CHAT_ID"),
                LOG_TELEGRAM_ADMINS_CHAT_ID=filtered_data.get("LOG_TELEGRAM_ADMINS_CHAT_ID"),
                LOG_TELEGRAM_PAYMENTS_CHAT_ID=filtered_data.get("LOG_TELEGRAM_PAYMENTS_CHAT_ID"),
                LOG_TELEGRAM_ORDERS_CHAT_ID=filtered_data.get("LOG_TELEGRAM_ORDERS_CHAT_ID"),
                LOG_TELEGRAM_SUPPORT_CHAT_ID=filtered_data.get("LOG_TELEGRAM_SUPPORT_CHAT_ID"),
                LOG_TELEGRAM_SERVER_LOGS_CHAT_ID=filtered_data.get("LOG_TELEGRAM_SERVER_LOGS_CHAT_ID"),
                LOG_FORMAT=filtered_data.get("LOG_FORMAT", "json"),
                LOG_MAX_BYTES=filtered_data.get("LOG_MAX_BYTES", 10485760),
                LOG_BACKUP_COUNT=filtered_data.get("LOG_BACKUP_COUNT", 5),
            ),
            telegram=TelegramSettings(
                BOT_TOKEN=os.getenv("BOT_TOKEN", filtered_data.get("BOT_TOKEN", "")),
                ADMIN_BOT_TOKEN=os.getenv("ADMIN_BOT_TOKEN", filtered_data.get("ADMIN_BOT_TOKEN", "")),
                USE_WEBHOOK=filtered_data.get("USE_WEBHOOK", False),
                WEBHOOK_HOST=filtered_data.get("WEBHOOK_HOST", "https://example.com"),
                WEBHOOK_PATH=filtered_data.get("WEBHOOK_PATH", "/webhook"),
                WEBHOOK_URL_MAIN=filtered_data.get("WEBHOOK_URL_MAIN"),
                WEBHOOK_URL_LOGGER=filtered_data.get("WEBHOOK_URL_LOGGER"),
                WEBHOOK_SECRET=os.getenv("WEBHOOK_SECRET", filtered_data.get("WEBHOOK_SECRET")),
                WEBAPP_HOST=filtered_data.get("WEBAPP_HOST", "0.0.0.0"),
                WEBAPP_PORT=filtered_data.get("WEBAPP_PORT", filtered_data.get("BOT_WEBAPP_PORT", 8000)),
            ),
            google_maps=GoogleMapsSettings(
                GOOGLE_MAPS_API_KEY=os.getenv("GOOGLE_MAPS_API_KEY", filtered_data.get("GOOGLE_MAPS_API_KEY", "")),
                GEOCODING_LANGUAGE=filtered_data.get("GEOCODING_LANGUAGE", "ru"),
            ),
            domain=DomainSettings(
                DOMAIN=filtered_data.get("DOMAIN", "taxi.example.com"),
                DEFAULT_LANGUAGE=filtered_data.get("DEFAULT_LANGUAGE", "ru"),
                SUPPORTED_LANGUAGES=filtered_data.get("SUPPORTED_LANGUAGES", ["ru", "uk", "en", "de"]),
                SUPPORTED_CITIES=filtered_data.get("SUPPORTED_CITIES", ["Kyiv"]),
                DEFAULT_CITY=filtered_data.get("DEFAULT_CITY", "Kyiv"),
                TIMEZONE=filtered_data.get("TIMEZONE", "Europe/Kyiv"),
            ),
            database=DatabaseSettings(
                DB_HOST=os.getenv("DB_HOST", filtered_data.get("DB_HOST", "localhost")),
                DB_PORT=int(os.getenv("DB_PORT", filtered_data.get("DB_PORT", 5432))),
                DB_NAME=os.getenv("DB_NAME", filtered_data.get("DB_NAME", "taxi_bot")),
                DB_USER=os.getenv("DB_USER", filtered_data.get("DB_USER", "postgres")),
                DB_PASSWORD=os.getenv("DB_PASSWORD", filtered_data.get("DB_PASSWORD", "")),
                DB_MIN_POOL_SIZE=filtered_data.get("DB_MIN_POOL_SIZE", 5),
                DB_MAX_POOL_SIZE=filtered_data.get("DB_MAX_POOL_SIZE", 20),
                DB_COMMAND_TIMEOUT=filtered_data.get("DB_COMMAND_TIMEOUT", 60),
                DB_RETRY_ATTEMPTS=filtered_data.get("DB_RETRY_ATTEMPTS", 3),
                DB_RETRY_DELAY=filtered_data.get("DB_RETRY_DELAY", 1.0),
            ),
            redis=RedisSettings(
                REDIS_HOST=os.getenv("REDIS_HOST", filtered_data.get("REDIS_HOST", "localhost")),
                REDIS_PORT=int(os.getenv("REDIS_PORT", filtered_data.get("REDIS_PORT", 6379))),
                REDIS_DB=filtered_data.get("REDIS_DB", 0),
                REDIS_PASSWORD=os.getenv("REDIS_PASSWORD", filtered_data.get("REDIS_PASSWORD", "")),
                REDIS_NAMESPACE=filtered_data.get("REDIS_NAMESPACE", "taxi"),
                REDIS_MAX_CONNECTIONS=filtered_data.get("REDIS_MAX_CONNECTIONS", 50),
            ),
            redis_ttl=RedisTTLSettings(
                PROFILE_TTL=filtered_data.get("PROFILE_TTL", 300),
                ORDER_TTL=filtered_data.get("ORDER_TTL", 86400),
                DRIVER_LOCATION_TTL=filtered_data.get("DRIVER_LOCATION_TTL", 300),
                LAST_SEEN_TTL=filtered_data.get("LAST_SEEN_TTL", 300),
                NOTIFIED_DRIVERS_TTL=filtered_data.get("NOTIFIED_DRIVERS_TTL", 86400),
                SESSION_TTL=filtered_data.get("SESSION_TTL", 3600),
            ),
            rabbitmq=RabbitMQSettings(
                RABBITMQ_HOST=os.getenv("RABBITMQ_HOST", filtered_data.get("RABBITMQ_HOST", "localhost")),
                RABBITMQ_PORT=int(os.getenv("RABBITMQ_PORT", filtered_data.get("RABBITMQ_PORT", 5672))),
                RABBITMQ_USER=os.getenv("RABBITMQ_USER", filtered_data.get("RABBITMQ_USER", "guest")),
                RABBITMQ_PASSWORD=os.getenv("RABBITMQ_PASSWORD", filtered_data.get("RABBITMQ_PASSWORD", "guest")),
                RABBITMQ_VHOST=filtered_data.get("RABBITMQ_VHOST", "/"),
                RABBITMQ_EXCHANGE=filtered_data.get("RABBITMQ_EXCHANGE", "taxi.events"),
                RABBITMQ_PREFETCH_COUNT=filtered_data.get("RABBITMQ_PREFETCH_COUNT", 10),
            ),
            stars=StarsSettings(
                STARS_TO_USD_RATE=filtered_data.get("STARS_TO_USD_RATE", 0.013),
                MIN_BALANCE_STARS=filtered_data.get("MIN_BALANCE_STARS", 100),
                PLATFORM_COMMISSION_PERCENT=filtered_data.get("PLATFORM_COMMISSION_PERCENT", 15.0),
                DRIVER_BONUS_PERCENT=filtered_data.get("DRIVER_BONUS_PERCENT", 5.0),
                WITHDRAWAL_MIN_STARS=filtered_data.get("WITHDRAWAL_MIN_STARS", 500),
            ),
            fares=FareSettings(
                BASE_FARE_FIRST_5KM=filtered_data.get("BASE_FARE_FIRST_5KM", 10.0),
                FARE_PER_KM_AFTER_5=filtered_data.get("FARE_PER_KM_AFTER_5", 1.0),
                PICKUP_FREE_DISTANCE_KM=filtered_data.get("PICKUP_FREE_DISTANCE_KM", 5.0),
                PICKUP_FARE_PER_KM=filtered_data.get("PICKUP_FARE_PER_KM", 0.5),
                NIGHT_FEE=filtered_data.get("NIGHT_FEE", 5.0),
                NIGHT_START_HOUR=filtered_data.get("NIGHT_START_HOUR", 23),
                NIGHT_END_HOUR=filtered_data.get("NIGHT_END_HOUR", 6),
                WAITING_FREE_MINUTES=filtered_data.get("WAITING_FREE_MINUTES", 5),
                WAITING_FARE_PER_MINUTE=filtered_data.get("WAITING_FARE_PER_MINUTE", 0.25),
                MOVEMENT_THRESHOLD_METERS=filtered_data.get("MOVEMENT_THRESHOLD_METERS", 200.0),
                CURRENCY=filtered_data.get("CURRENCY", "EUR"),
            ),
            search=SearchSettings(
                DRIVER_SEARCH_RADIUS_KM=filtered_data.get("DRIVER_SEARCH_RADIUS_KM", 5.0),
                SEARCH_RADIUS_MIN_KM=filtered_data.get("SEARCH_RADIUS_MIN_KM", 1.0),
                SEARCH_RADIUS_MAX_KM=filtered_data.get("SEARCH_RADIUS_MAX_KM", 10.0),
                SEARCH_RADIUS_STEP_KM=filtered_data.get("SEARCH_RADIUS_STEP_KM", 1.0),
                MAX_DRIVERS_TO_NOTIFY=filtered_data.get("MAX_DRIVERS_TO_NOTIFY", 10),
                DRIVER_RESPONSE_TIMEOUT=filtered_data.get("DRIVER_RESPONSE_TIMEOUT", 30),
                SEARCH_RETRY_INTERVAL=filtered_data.get("SEARCH_RETRY_INTERVAL", 5),
                MAX_SEARCH_RETRIES=filtered_data.get("MAX_SEARCH_RETRIES", 3),
            ),
            timeouts=TimeoutSettings(
                ORDER_TIMEOUT=filtered_data.get("ORDER_TIMEOUT", 300),
                DRIVER_ARRIVAL_TIMEOUT=filtered_data.get("DRIVER_ARRIVAL_TIMEOUT", 900),
                RIDE_IDLE_TIMEOUT=filtered_data.get("RIDE_IDLE_TIMEOUT", 3600),
                LOCATION_UPDATE_INTERVAL=filtered_data.get("LOCATION_UPDATE_INTERVAL", 10),
                AUTOSAVE_INTERVAL=filtered_data.get("AUTOSAVE_INTERVAL", 15),
                HEALTH_CHECK_INTERVAL=filtered_data.get("HEALTH_CHECK_INTERVAL", 30),
            ),
        )


@lru_cache()
def get_settings() -> Settings:
    """
    Возвращает синглтон настроек приложения.
    Использует кэширование для производительности.
    """
    from dotenv import load_dotenv
    
    # Загружаем .env файл
    env_path = get_project_root() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    return Settings.from_config_json()


# Экспорт синглтона для удобного импорта
settings = get_settings()
