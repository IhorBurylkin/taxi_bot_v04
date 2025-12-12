import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncpg
from src.infra.database import DatabaseManager, retry_on_connection_error

@pytest.fixture
def mock_pool():
    pool = AsyncMock(spec=asyncpg.Pool)
    pool.acquire = MagicMock()
    pool.close = AsyncMock()
    return pool

@pytest.fixture
def mock_connection():
    conn = AsyncMock(spec=asyncpg.Connection)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.transaction = MagicMock()
    return conn

@pytest.fixture
def db_manager(mock_pool):
    # Reset singleton
    DatabaseManager._instance = None
    manager = DatabaseManager()
    manager._pool = mock_pool
    return manager

# --- Connect/Disconnect Tests ---

@pytest.mark.asyncio
async def test_connect_success():
    DatabaseManager._instance = None
    manager = DatabaseManager()
    
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_create_pool.return_value = AsyncMock(spec=asyncpg.Pool)
        
        await manager.connect(dsn="postgres://user:pass@localhost/db")
        
        mock_create_pool.assert_called_once()
        assert manager._pool is not None

@pytest.mark.asyncio
async def test_connect_already_connected(db_manager):
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        await db_manager.connect()
        mock_create_pool.assert_not_called()

@pytest.mark.asyncio
async def test_disconnect(db_manager, mock_pool):
    await db_manager.disconnect()
    mock_pool.close.assert_called_once()
    assert db_manager._pool is None

# --- Query Execution Tests ---

@pytest.mark.asyncio
async def test_execute(db_manager, mock_pool, mock_connection):
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = "INSERT 0 1"
    
    result = await db_manager.execute("INSERT INTO table VALUES (1)")
    
    assert result == "INSERT 0 1"
    mock_connection.execute.assert_called_once()

@pytest.mark.asyncio
async def test_fetch(db_manager, mock_pool, mock_connection):
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    mock_connection.fetch.return_value = [{"id": 1}]
    
    result = await db_manager.fetch("SELECT * FROM table")
    
    assert result == [{"id": 1}]
    mock_connection.fetch.assert_called_once()

@pytest.mark.asyncio
async def test_fetchrow(db_manager, mock_pool, mock_connection):
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    mock_connection.fetchrow.return_value = {"id": 1}
    
    result = await db_manager.fetchrow("SELECT * FROM table LIMIT 1")
    
    assert result == {"id": 1}
    mock_connection.fetchrow.assert_called_once()

@pytest.mark.asyncio
async def test_fetchval(db_manager, mock_pool, mock_connection):
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    mock_connection.fetchval.return_value = 1
    
    result = await db_manager.fetchval("SELECT count(*) FROM table")
    
    assert result == 1
    mock_connection.fetchval.assert_called_once()

# --- Transaction Tests ---

@pytest.mark.asyncio
async def test_transaction(db_manager, mock_pool, mock_connection):
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    mock_transaction = AsyncMock()
    mock_connection.transaction.return_value.__aenter__.return_value = mock_transaction
    
    async with db_manager.transaction() as conn:
        assert conn == mock_connection
    
    mock_connection.transaction.assert_called_once()

# --- Health Check Tests ---

@pytest.mark.asyncio
async def test_health_check_success(db_manager, mock_pool, mock_connection):
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    mock_connection.fetchval.return_value = 1
    
    result = await db_manager.health_check()
    assert result is True

@pytest.mark.asyncio
async def test_health_check_fail(db_manager, mock_pool, mock_connection):
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    mock_connection.fetchval.side_effect = Exception("DB Error")
    
    result = await db_manager.health_check()
    assert result is False

# --- Retry Decorator Tests ---

@pytest.mark.asyncio
async def test_retry_success():
    mock_func = AsyncMock(return_value="success")
    
    decorated = retry_on_connection_error()(mock_func)
    result = await decorated()
    
    assert result == "success"
    assert mock_func.call_count == 1

@pytest.mark.asyncio
async def test_retry_fail_then_success():
    mock_func = AsyncMock(side_effect=[OSError("Connection refused"), "success"])
    
    decorated = retry_on_connection_error(max_attempts=3, delay=0.01)(mock_func)
    result = await decorated()
    
    assert result == "success"
    assert mock_func.call_count == 2

@pytest.mark.asyncio
async def test_retry_max_attempts_reached():
    mock_func = AsyncMock(side_effect=OSError("Connection refused"))
    
    decorated = retry_on_connection_error(max_attempts=2, delay=0.01)(mock_func)
    
    with pytest.raises(OSError):
        await decorated()
    
    assert mock_func.call_count == 2
