# tests/infra/test_redis_client.py
"""
Тесты для клиента Redis.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest
from pydantic import BaseModel

from src.infra.redis_client import RedisClient


class SampleModel(BaseModel):
    """Тестовая Pydantic модель."""
    id: int
    name: str
    active: bool = True


class TestRedisClient:
    """Тесты для RedisClient."""
    
    @pytest.fixture
    def redis_client(self) -> RedisClient:
        """Создаёт экземпляр RedisClient для тестов."""
        # Сбрасываем синглтон для каждого теста
        RedisClient._instance = None
        RedisClient._client = None
        client = RedisClient()
        return client
    
    def test_singleton(self) -> None:
        """Проверяет паттерн Singleton."""
        RedisClient._instance = None
        
        client1 = RedisClient()
        client2 = RedisClient()
        
        assert client1 is client2
    
    def test_client_not_initialized(self, redis_client: RedisClient) -> None:
        """Проверяет ошибку при обращении к неинициализированному клиенту."""
        with pytest.raises(RuntimeError, match="Redis клиент не инициализирован"):
            _ = redis_client.client
    
    def test_make_key(self, redis_client: RedisClient) -> None:
        """Проверяет формирование ключа с namespace."""
        key = redis_client._make_key("test_key")
        assert key == "taxi:test_key"
    
    def test_make_key_custom_namespace(self, redis_client: RedisClient) -> None:
        """Проверяет формирование ключа с кастомным namespace."""
        redis_client._namespace = "custom"
        key = redis_client._make_key("test_key")
        assert key == "custom:test_key"
    
    @pytest.mark.asyncio
    async def test_connect(self, redis_client: RedisClient) -> None:
        """Проверяет подключение к Redis."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            await redis_client.connect(
                url="redis://localhost:6379/0",
                max_connections=10,
            )
        
        assert redis_client._client is not None
        mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self, redis_client: RedisClient) -> None:
        """Проверяет, что повторное подключение пропускается."""
        mock_redis = AsyncMock()
        redis_client._client = mock_redis
        
        with patch("redis.asyncio.from_url") as mock_from_url:
            await redis_client.connect(url="redis://localhost:6379/0")
        
        mock_from_url.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, redis_client: RedisClient) -> None:
        """Проверяет отключение от Redis."""
        mock_redis = AsyncMock()
        redis_client._client = mock_redis
        
        await redis_client.disconnect()
        
        mock_redis.aclose.assert_called_once()
        assert redis_client._client is None
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, redis_client: RedisClient) -> None:
        """Проверяет отключение, когда соединение не установлено."""
        redis_client._client = None
        
        # Не должно вызывать исключений
        await redis_client.disconnect()
    
    @pytest.mark.asyncio
    async def test_get(self, redis_client: RedisClient) -> None:
        """Проверяет получение значения."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "test_value"
        redis_client._client = mock_redis
        
        result = await redis_client.get("key")
        
        assert result == "test_value"
        mock_redis.get.assert_called_once_with("taxi:key")
    
    @pytest.mark.asyncio
    async def test_set(self, redis_client: RedisClient) -> None:
        """Проверяет установку значения."""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        redis_client._client = mock_redis
        
        result = await redis_client.set("key", "value", ttl=60)
        
        assert result is True
        mock_redis.set.assert_called_once_with("taxi:key", "value", ex=60)
    
    @pytest.mark.asyncio
    async def test_delete(self, redis_client: RedisClient) -> None:
        """Проверяет удаление ключа."""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 1
        redis_client._client = mock_redis
        
        result = await redis_client.delete("key")
        
        assert result == 1
        mock_redis.delete.assert_called_once_with("taxi:key")
    
    @pytest.mark.asyncio
    async def test_exists(self, redis_client: RedisClient) -> None:
        """Проверяет проверку существования ключа."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        redis_client._client = mock_redis
        
        result = await redis_client.exists("key")
        
        assert result is True
        mock_redis.exists.assert_called_once_with("taxi:key")
    
    @pytest.mark.asyncio
    async def test_exists_false(self, redis_client: RedisClient) -> None:
        """Проверяет проверку несуществующего ключа."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        redis_client._client = mock_redis
        
        result = await redis_client.exists("key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_expire(self, redis_client: RedisClient) -> None:
        """Проверяет установку TTL."""
        mock_redis = AsyncMock()
        mock_redis.expire.return_value = True
        redis_client._client = mock_redis
        
        result = await redis_client.expire("key", 300)
        
        assert result is True
        mock_redis.expire.assert_called_once_with("taxi:key", 300)
    
    @pytest.mark.asyncio
    async def test_ttl(self, redis_client: RedisClient) -> None:
        """Проверяет получение TTL."""
        mock_redis = AsyncMock()
        mock_redis.ttl.return_value = 120
        redis_client._client = mock_redis
        
        result = await redis_client.ttl("key")
        
        assert result == 120
    
    @pytest.mark.asyncio
    async def test_get_model(self, redis_client: RedisClient) -> None:
        """Проверяет получение Pydantic модели."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"id": 1, "name": "Test", "active": true}'
        redis_client._client = mock_redis
        
        result = await redis_client.get_model("key", SampleModel)
        
        assert result is not None
        assert result.id == 1
        assert result.name == "Test"
        assert result.active is True
    
    @pytest.mark.asyncio
    async def test_get_model_not_found(self, redis_client: RedisClient) -> None:
        """Проверяет получение несуществующей модели."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        redis_client._client = mock_redis
        
        result = await redis_client.get_model("key", SampleModel)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_model_invalid_json(self, redis_client: RedisClient) -> None:
        """Проверяет обработку невалидного JSON."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "invalid json"
        redis_client._client = mock_redis
        
        result = await redis_client.get_model("key", SampleModel)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_model(self, redis_client: RedisClient) -> None:
        """Проверяет сохранение Pydantic модели."""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        redis_client._client = mock_redis
        
        model = SampleModel(id=1, name="Test")
        result = await redis_client.set_model("key", model, ttl=60)
        
        assert result is True
        # Проверяем, что был передан JSON
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "taxi:key"
        assert '"id":1' in call_args[0][1] or '"id": 1' in call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_geoadd(self, redis_client: RedisClient) -> None:
        """Проверяет добавление геопозиции."""
        mock_redis = AsyncMock()
        mock_redis.geoadd.return_value = 1
        redis_client._client = mock_redis
        
        result = await redis_client.geoadd("locations", 30.52, 50.45, "driver_123")
        
        assert result == 1
        mock_redis.geoadd.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_georadius(self, redis_client: RedisClient) -> None:
        """Проверяет поиск в радиусе."""
        mock_redis = AsyncMock()
        mock_redis.georadius.return_value = [("driver_123", 1.5), ("driver_456", 2.0)]
        redis_client._client = mock_redis
        
        result = await redis_client.georadius(
            "locations",
            30.52,
            50.45,
            5.0,
            unit="km",
            with_dist=True,
            count=10,
            sort="ASC",
        )
        
        assert len(result) == 2
        assert result[0] == ("driver_123", 1.5)
    
    @pytest.mark.asyncio
    async def test_hset(self, redis_client: RedisClient) -> None:
        """Проверяет установку поля хэша."""
        mock_redis = AsyncMock()
        mock_redis.hset.return_value = 1
        redis_client._client = mock_redis
        
        result = await redis_client.hset("hash_key", "field", "value")
        
        assert result == 1
    
    @pytest.mark.asyncio
    async def test_hget(self, redis_client: RedisClient) -> None:
        """Проверяет получение поля хэша."""
        mock_redis = AsyncMock()
        mock_redis.hget.return_value = "value"
        redis_client._client = mock_redis
        
        result = await redis_client.hget("hash_key", "field")
        
        assert result == "value"
    
    @pytest.mark.asyncio
    async def test_sadd(self, redis_client: RedisClient) -> None:
        """Проверяет добавление в множество."""
        mock_redis = AsyncMock()
        mock_redis.sadd.return_value = 1
        redis_client._client = mock_redis
        
        result = await redis_client.sadd("set_key", "member")
        
        assert result == 1
    
    @pytest.mark.asyncio
    async def test_sismember(self, redis_client: RedisClient) -> None:
        """Проверяет членство в множестве."""
        mock_redis = AsyncMock()
        mock_redis.sismember.return_value = True
        redis_client._client = mock_redis
        
        result = await redis_client.sismember("set_key", "member")
        
        assert result is True
