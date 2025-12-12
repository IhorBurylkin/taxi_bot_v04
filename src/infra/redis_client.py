# src/infra/redis_client.py
"""
Клиент Redis для кэширования и Geo-операций.
Поддерживает типизированные операции с Pydantic моделями.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar, Type

import redis.asyncio as redis
from pydantic import BaseModel

from src.common.logger import get_logger, log_error, log_info
from src.common.constants import TypeMsg

logger = get_logger("redis")

T = TypeVar("T", bound=BaseModel)


class RedisClient:
    """
    Асинхронный клиент Redis.
    Поддерживает:
    - Типизированные get/set с Pydantic моделями
    - Geo-операции (GEOADD, GEORADIUS)
    - Hash операции
    - Пайплайны
    """
    
    _instance: RedisClient | None = None
    _client: redis.Redis | None = None
    
    def __new__(cls) -> RedisClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Инициализация (вызывается только один раз благодаря Singleton)."""
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._client = None
        self._namespace = "taxi"
    
    @property
    def client(self) -> redis.Redis:
        """Возвращает клиент Redis."""
        if self._client is None:
            raise RuntimeError("Redis клиент не инициализирован. Вызовите connect() сначала.")
        return self._client
    
    def _make_key(self, key: str) -> str:
        """Добавляет namespace к ключу."""
        return f"{self._namespace}:{key}"
    
    async def connect(
        self,
        url: str | None = None,
        max_connections: int = 50,
    ) -> None:
        """
        Подключается к Redis.
        
        Args:
            url: URL Redis (если None, берётся из конфига)
            max_connections: Максимальное количество соединений
        """
        if self._client is not None:
            return
        
        # Получаем URL из конфига, если не передан
        if url is None:
            from src.config import settings
            url = settings.redis.url
            max_connections = settings.redis.REDIS_MAX_CONNECTIONS
            self._namespace = settings.redis.REDIS_NAMESPACE
        
        await log_info("Подключение к Redis...", type_msg=TypeMsg.INFO)
        
        self._client = redis.from_url(
            url,
            max_connections=max_connections,
            decode_responses=True,
        )
        
        # Проверяем подключение
        await self._client.ping()
        
        await log_info("Подключение к Redis установлено", type_msg=TypeMsg.INFO)
    
    async def disconnect(self) -> None:
        """Закрывает соединение с Redis."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            await log_info("Соединение с Redis закрыто", type_msg=TypeMsg.INFO)
    
    # =========================================================================
    # БАЗОВЫЕ ОПЕРАЦИИ
    # =========================================================================
    
    async def get(self, key: str) -> str | None:
        """Получает значение по ключу."""
        return await self.client.get(self._make_key(key))
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """
        Устанавливает значение.
        
        Args:
            key: Ключ
            value: Значение
            ttl: Время жизни в секундах
            
        Returns:
            True если успешно
        """
        return await self.client.set(
            self._make_key(key),
            value,
            ex=ttl,
        )
    
    async def delete(self, key: str) -> int:
        """Удаляет ключ."""
        return await self.client.delete(self._make_key(key))
    
    async def exists(self, key: str) -> bool:
        """Проверяет существование ключа."""
        return await self.client.exists(self._make_key(key)) > 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Устанавливает TTL для ключа."""
        return await self.client.expire(self._make_key(key), ttl)
    
    async def ttl(self, key: str) -> int:
        """Возвращает оставшееся время жизни ключа."""
        return await self.client.ttl(self._make_key(key))
    
    # =========================================================================
    # ТИПИЗИРОВАННЫЕ ОПЕРАЦИИ (PYDANTIC)
    # =========================================================================
    
    async def get_model(self, key: str, model_class: Type[T]) -> T | None:
        """
        Получает и десериализует Pydantic модель.
        
        Args:
            key: Ключ
            model_class: Класс модели Pydantic
            
        Returns:
            Экземпляр модели или None
        """
        data = await self.get(key)
        if data is None:
            return None
        
        try:
            return model_class.model_validate_json(data)
        except Exception as e:
            await log_error(f"Ошибка десериализации модели {model_class.__name__}: {e}")
            return None
    
    async def set_model(
        self,
        key: str,
        model: BaseModel,
        ttl: int | None = None,
    ) -> bool:
        """
        Сериализует и сохраняет Pydantic модель.
        
        Args:
            key: Ключ
            model: Экземпляр модели Pydantic
            ttl: Время жизни в секундах
            
        Returns:
            True если успешно
        """
        data = model.model_dump_json()
        return await self.set(key, data, ttl=ttl)
    
    # =========================================================================
    # JSON ОПЕРАЦИИ
    # =========================================================================
    
    async def get_json(self, key: str) -> dict | list | None:
        """Получает и парсит JSON."""
        data = await self.get(key)
        if data is None:
            return None
        
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None
    
    async def set_json(
        self,
        key: str,
        data: dict | list,
        ttl: int | None = None,
    ) -> bool:
        """Сериализует и сохраняет JSON."""
        return await self.set(key, json.dumps(data, ensure_ascii=False), ttl=ttl)
    
    # =========================================================================
    # HASH ОПЕРАЦИИ
    # =========================================================================
    
    async def hget(self, name: str, key: str) -> str | None:
        """Получает значение из хеша."""
        return await self.client.hget(self._make_key(name), key)
    
    async def hset(self, name: str, key: str, value: str) -> int:
        """Устанавливает значение в хеше."""
        return await self.client.hset(self._make_key(name), key, value)
    
    async def hgetall(self, name: str) -> dict[str, str]:
        """Получает все поля хеша."""
        return await self.client.hgetall(self._make_key(name))
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Удаляет поля из хеша."""
        return await self.client.hdel(self._make_key(name), *keys)
    
    # =========================================================================
    # GEO ОПЕРАЦИИ (для поиска водителей)
    # =========================================================================
    
    async def geoadd(
        self,
        key: str,
        longitude: float,
        latitude: float,
        member: str,
    ) -> int:
        """
        Добавляет геолокацию.
        
        Args:
            key: Ключ (например, "drivers:locations")
            longitude: Долгота
            latitude: Широта
            member: Идентификатор (например, driver_id)
            
        Returns:
            Количество добавленных элементов
        """
        return await self.client.geoadd(
            self._make_key(key),
            (longitude, latitude, member),
        )
    
    async def geopos(
        self,
        key: str,
        member: str,
    ) -> tuple[float, float] | None:
        """
        Получает позицию участника.
        
        Returns:
            (longitude, latitude) или None
        """
        result = await self.client.geopos(self._make_key(key), member)
        if result and result[0]:
            return result[0]
        return None
    
    async def georadius(
        self,
        key: str,
        longitude: float,
        latitude: float,
        radius: float,
        unit: str = "km",
        with_dist: bool = True,
        count: int | None = None,
        sort: str = "ASC",
    ) -> list[tuple[str, float]]:
        """
        Ищет участников в радиусе от точки.
        
        Args:
            key: Ключ
            longitude: Долгота центра
            latitude: Широта центра
            radius: Радиус поиска
            unit: Единица измерения (km, m, mi, ft)
            with_dist: Включать расстояние
            count: Максимальное количество результатов
            sort: Сортировка (ASC, DESC)
            
        Returns:
            Список кортежей (member, distance)
        """
        results = await self.client.georadius(
            self._make_key(key),
            longitude,
            latitude,
            radius,
            unit=unit,
            withdist=with_dist,
            count=count,
            sort=sort,
        )
        
        if with_dist:
            return [(r[0], float(r[1])) for r in results]
        return [(r, 0.0) for r in results]
    
    async def georem(self, key: str, member: str) -> int:
        """Удаляет участника из geo-индекса."""
        return await self.client.zrem(self._make_key(key), member)
    
    # =========================================================================
    # SET ОПЕРАЦИИ
    # =========================================================================
    
    async def sadd(self, key: str, *members: str) -> int:
        """Добавляет элементы в множество."""
        return await self.client.sadd(self._make_key(key), *members)
    
    async def srem(self, key: str, *members: str) -> int:
        """Удаляет элементы из множества."""
        return await self.client.srem(self._make_key(key), *members)
    
    async def sismember(self, key: str, member: str) -> bool:
        """Проверяет принадлежность к множеству."""
        return await self.client.sismember(self._make_key(key), member)
    
    async def smembers(self, key: str) -> set[str]:
        """Возвращает все элементы множества."""
        return await self.client.smembers(self._make_key(key))
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    async def health_check(self) -> bool:
        """
        Проверяет здоровье подключения к Redis.
        
        Returns:
            True если подключение работает
        """
        try:
            return await self.client.ping()
        except Exception as e:
            await log_error(f"Health check Redis failed: {e}")
            return False


def get_redis() -> RedisClient:
    """
    Возвращает глобальный экземпляр RedisClient.
    
    Returns:
        RedisClient
    """
    return RedisClient()


async def init_redis() -> None:
    """
    Инициализирует подключение к Redis.
    Использует настройки из конфигурации.
    """
    from src.config import settings
    
    redis_client = get_redis()
    await redis_client.connect(
        url=settings.redis.url,
        max_connections=settings.redis.REDIS_MAX_CONNECTIONS,
    )
    await log_info(f"Redis подключён: {settings.redis.REDIS_HOST}:{settings.redis.REDIS_PORT}/{settings.redis.REDIS_DB}", type_msg=TypeMsg.INFO)


async def close_redis() -> None:
    """
    Закрывает подключение к Redis.
    """
    redis_client = get_redis()
    await redis_client.disconnect()
    await log_info("Redis отключён", type_msg=TypeMsg.INFO)
