import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from src.infra.redis_client import RedisClient, get_redis, init_redis, close_redis

class TestModel(BaseModel):
    id: int
    name: str

@pytest.fixture
def mock_redis_lib():
    with patch("src.infra.redis_client.redis.from_url") as mock:
        client_mock = AsyncMock()
        mock.return_value = client_mock
        yield mock

@pytest.fixture
def redis_client(mock_redis_lib):
    # Reset singleton
    RedisClient._instance = None
    RedisClient._client = None
    
    client = RedisClient()
    # Manually set the client to avoid needing to call connect() in every test
    # or we can call connect() with a mock URL
    client._client = mock_redis_lib.return_value
    client._namespace = "test"
    return client

@pytest.mark.asyncio
async def test_singleton():
    RedisClient._instance = None
    client1 = RedisClient()
    client2 = RedisClient()
    assert client1 is client2
    assert get_redis() is client1

@pytest.mark.asyncio
async def test_connect(mock_redis_lib):
    RedisClient._instance = None
    client = RedisClient()
    
    # Mock settings
    with patch("src.config.settings") as mock_settings:
        mock_settings.redis.url = "redis://localhost:6379/0"
        mock_settings.redis.REDIS_MAX_CONNECTIONS = 10
        mock_settings.redis.REDIS_NAMESPACE = "test_ns"
        
        # Fix logger issue
        mock_settings.logging.LOG_LEVEL = "DEBUG"
        mock_settings.logging.LOG_FORMAT = "colored"
        mock_settings.logging.LOG_TO_FILE = False
        mock_settings.logging.LOG_FILE_PATH = "logs/app.log"
        mock_settings.logging.LOG_MAX_BYTES = 10485760
        mock_settings.logging.LOG_BACKUP_COUNT = 5
        mock_settings.system.ENVIRONMENT = "development"
        
        await client.connect()
        
        mock_redis_lib.assert_called_once_with(
            "redis://localhost:6379/0",
            max_connections=10,
            decode_responses=True
        )
        assert client._namespace == "test_ns"
        client.client.ping.assert_called_once()

@pytest.mark.asyncio
async def test_connect_already_connected(mock_redis_lib):
    RedisClient._instance = None
    client = RedisClient()
    client._client = AsyncMock()
    
    await client.connect()
    mock_redis_lib.assert_not_called()

@pytest.mark.asyncio
async def test_disconnect(redis_client):
    # Capture the mock before it gets set to None
    client_mock = redis_client.client
    
    # Mock settings for logger
    with patch("src.config.settings") as mock_settings:
        mock_settings.logging.LOG_LEVEL = "DEBUG"
        mock_settings.logging.LOG_FORMAT = "colored"
        mock_settings.logging.LOG_TO_FILE = False
        mock_settings.logging.LOG_FILE_PATH = "logs/app.log"
        mock_settings.logging.LOG_MAX_BYTES = 10485760
        mock_settings.logging.LOG_BACKUP_COUNT = 5
        mock_settings.system.ENVIRONMENT = "development"

        await redis_client.disconnect()
        
    client_mock.aclose.assert_called_once()
    assert redis_client._client is None

@pytest.mark.asyncio
async def test_client_property_error():
    RedisClient._instance = None
    client = RedisClient()
    with pytest.raises(RuntimeError, match="Redis клиент не инициализирован"):
        _ = client.client

@pytest.mark.asyncio
async def test_basic_operations(redis_client):
    # GET
    redis_client.client.get.return_value = "value"
    assert await redis_client.get("key") == "value"
    redis_client.client.get.assert_called_with("test:key")
    
    # SET
    redis_client.client.set.return_value = True
    assert await redis_client.set("key", "value", ttl=60) is True
    redis_client.client.set.assert_called_with("test:key", "value", ex=60)
    
    # DELETE
    redis_client.client.delete.return_value = 1
    assert await redis_client.delete("key") == 1
    redis_client.client.delete.assert_called_with("test:key")
    
    # EXISTS
    redis_client.client.exists.return_value = 1
    assert await redis_client.exists("key") is True
    redis_client.client.exists.assert_called_with("test:key")
    
    # EXPIRE
    redis_client.client.expire.return_value = True
    assert await redis_client.expire("key", 60) is True
    redis_client.client.expire.assert_called_with("test:key", 60)
    
    # TTL
    redis_client.client.ttl.return_value = 30
    assert await redis_client.ttl("key") == 30
    redis_client.client.ttl.assert_called_with("test:key")

@pytest.mark.asyncio
async def test_pydantic_operations(redis_client):
    model = TestModel(id=1, name="test")
    
    # SET MODEL
    redis_client.client.set.return_value = True
    assert await redis_client.set_model("key", model, ttl=60) is True
    redis_client.client.set.assert_called_with(
        "test:key", 
        model.model_dump_json(), 
        ex=60
    )
    
    # GET MODEL - Success
    redis_client.client.get.return_value = model.model_dump_json()
    result = await redis_client.get_model("key", TestModel)
    assert result == model
    
    # GET MODEL - None
    redis_client.client.get.return_value = None
    assert await redis_client.get_model("key", TestModel) is None
    
    # GET MODEL - Error
    redis_client.client.get.return_value = "invalid json"
    assert await redis_client.get_model("key", TestModel) is None

@pytest.mark.asyncio
async def test_json_operations(redis_client):
    data = {"a": 1, "b": "test"}
    
    # SET JSON
    redis_client.client.set.return_value = True
    assert await redis_client.set_json("key", data, ttl=60) is True
    redis_client.client.set.assert_called_with(
        "test:key", 
        json.dumps(data, ensure_ascii=False), 
        ex=60
    )
    
    # GET JSON - Success
    redis_client.client.get.return_value = json.dumps(data)
    assert await redis_client.get_json("key") == data
    
    # GET JSON - None
    redis_client.client.get.return_value = None
    assert await redis_client.get_json("key") is None
    
    # GET JSON - Error
    redis_client.client.get.return_value = "invalid json"
    assert await redis_client.get_json("key") is None

@pytest.mark.asyncio
async def test_hash_operations(redis_client):
    # HGET
    redis_client.client.hget.return_value = "value"
    assert await redis_client.hget("name", "key") == "value"
    redis_client.client.hget.assert_called_with("test:name", "key")
    
    # HSET
    redis_client.client.hset.return_value = 1
    assert await redis_client.hset("name", "key", "value") == 1
    redis_client.client.hset.assert_called_with("test:name", "key", "value")
    
    # HGETALL
    redis_client.client.hgetall.return_value = {"k": "v"}
    assert await redis_client.hgetall("name") == {"k": "v"}
    redis_client.client.hgetall.assert_called_with("test:name")
    
    # HDEL
    redis_client.client.hdel.return_value = 1
    assert await redis_client.hdel("name", "k1", "k2") == 1
    redis_client.client.hdel.assert_called_with("test:name", "k1", "k2")

@pytest.mark.asyncio
async def test_geo_operations(redis_client):
    # GEOADD
    redis_client.client.geoadd.return_value = 1
    assert await redis_client.geoadd("key", 10.0, 20.0, "member") == 1
    redis_client.client.geoadd.assert_called_with("test:key", (10.0, 20.0, "member"))
    
    # GEOPOS
    redis_client.client.geopos.return_value = [(10.0, 20.0)]
    assert await redis_client.geopos("key", "member") == (10.0, 20.0)
    redis_client.client.geopos.assert_called_with("test:key", "member")
    
    # GEOPOS - None
    redis_client.client.geopos.return_value = [None]
    assert await redis_client.geopos("key", "member") is None
    
    # GEORADIUS
    redis_client.client.georadius.return_value = [("m1", "1.5"), ("m2", "2.0")]
    results = await redis_client.georadius("key", 10.0, 20.0, 5.0)
    assert results == [("m1", 1.5), ("m2", 2.0)]
    redis_client.client.georadius.assert_called_with(
        "test:key", 10.0, 20.0, 5.0,
        unit="km", withdist=True, count=None, sort="ASC"
    )
    
    # GEORADIUS - without dist
    redis_client.client.georadius.return_value = ["m1", "m2"]
    results = await redis_client.georadius("key", 10.0, 20.0, 5.0, with_dist=False)
    assert results == [("m1", 0.0), ("m2", 0.0)]
    
    # GEOREM
    redis_client.client.zrem.return_value = 1
    assert await redis_client.georem("key", "member") == 1
    redis_client.client.zrem.assert_called_with("test:key", "member")

@pytest.mark.asyncio
async def test_set_operations(redis_client):
    # SADD
    redis_client.client.sadd.return_value = 1
    assert await redis_client.sadd("key", "m1", "m2") == 1
    redis_client.client.sadd.assert_called_with("test:key", "m1", "m2")
    
    # SREM
    redis_client.client.srem.return_value = 1
    assert await redis_client.srem("key", "m1") == 1
    redis_client.client.srem.assert_called_with("test:key", "m1")
    
    # SISMEMBER
    redis_client.client.sismember.return_value = True
    assert await redis_client.sismember("key", "m1") is True
    redis_client.client.sismember.assert_called_with("test:key", "m1")
    
    # SMEMBERS
    redis_client.client.smembers.return_value = {"m1", "m2"}
    assert await redis_client.smembers("key") == {"m1", "m2"}
    redis_client.client.smembers.assert_called_with("test:key")

@pytest.mark.asyncio
async def test_health_check(redis_client):
    # Success
    redis_client.client.ping.return_value = True
    assert await redis_client.health_check() is True
    
    # Fail
    redis_client.client.ping.side_effect = Exception("Connection error")
    assert await redis_client.health_check() is False

@pytest.mark.asyncio
async def test_init_close_redis(mock_redis_lib):
    RedisClient._instance = None
    
    with patch("src.config.settings") as mock_settings:
        mock_settings.redis.url = "redis://localhost:6379/0"
        mock_settings.redis.REDIS_MAX_CONNECTIONS = 10
        mock_settings.redis.REDIS_NAMESPACE = "test"
        mock_settings.redis.REDIS_HOST = "localhost"
        mock_settings.redis.REDIS_PORT = 6379
        mock_settings.redis.REDIS_DB = 0
        
        await init_redis()
        mock_redis_lib.assert_called()
        
        await close_redis()
        mock_redis_lib.return_value.aclose.assert_called()
