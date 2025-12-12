# tests/infra/test_database.py
"""
Тесты для менеджера базы данных.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

import pytest

from src.infra.database import DatabaseManager, retry_on_connection_error


class TestRetryOnConnectionError:
    """Тесты для декоратора retry_on_connection_error."""
    
    @pytest.mark.asyncio
    async def test_success_first_attempt(self) -> None:
        """Проверяет успешное выполнение с первой попытки."""
        @retry_on_connection_error(max_attempts=3, delay=0.01)
        async def successful_func():
            return "success"
        
        result = await successful_func()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self) -> None:
        """Проверяет повторную попытку при ошибке подключения."""
        call_count = 0
        
        @retry_on_connection_error(max_attempts=3, delay=0.01)
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionRefusedError("Connection refused")
            return "success"
        
        result = await failing_then_success()
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self) -> None:
        """Проверяет превышение максимального количества попыток."""
        @retry_on_connection_error(max_attempts=2, delay=0.01)
        async def always_failing():
            raise ConnectionRefusedError("Connection refused")
        
        with pytest.raises(ConnectionRefusedError):
            await always_failing()
    
    @pytest.mark.asyncio
    async def test_non_connection_error_not_retried(self) -> None:
        """Проверяет, что другие ошибки не приводят к повторным попыткам."""
        call_count = 0
        
        @retry_on_connection_error(max_attempts=3, delay=0.01)
        async def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a connection error")
        
        with pytest.raises(ValueError):
            await raises_value_error()
        
        assert call_count == 1  # Не должно быть повторных попыток


class TestDatabaseManager:
    """Тесты для DatabaseManager."""
    
    @pytest.fixture
    def db_manager(self) -> DatabaseManager:
        """Создаёт экземпляр DatabaseManager для тестов."""
        # Сбрасываем синглтон для каждого теста
        DatabaseManager._instance = None
        DatabaseManager._pool = None
        manager = DatabaseManager()
        return manager
    
    def test_singleton(self) -> None:
        """Проверяет паттерн Singleton."""
        DatabaseManager._instance = None
        
        manager1 = DatabaseManager()
        manager2 = DatabaseManager()
        
        assert manager1 is manager2
    
    def test_pool_not_initialized(self, db_manager: DatabaseManager) -> None:
        """Проверяет ошибку при обращении к неинициализированному пулу."""
        with pytest.raises(RuntimeError, match="Пул соединений не инициализирован"):
            _ = db_manager.pool
    
    @pytest.mark.asyncio
    async def test_connect_creates_pool(self, db_manager: DatabaseManager) -> None:
        """Проверяет создание пула при подключении."""
        mock_pool = MagicMock()
        
        with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
            await db_manager.connect(
                dsn="postgresql://test:test@localhost/test",
                min_size=2,
                max_size=5,
            )
        
        assert db_manager._pool is not None
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self, db_manager: DatabaseManager) -> None:
        """Проверяет, что повторное подключение не создаёт новый пул."""
        mock_pool = MagicMock()
        db_manager._pool = mock_pool
        
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            await db_manager.connect(dsn="postgresql://test:test@localhost/test")
        
        # create_pool не должен был вызываться
        mock_create.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, db_manager: DatabaseManager) -> None:
        """Проверяет отключение от базы данных."""
        mock_pool = AsyncMock()
        db_manager._pool = mock_pool
        
        await db_manager.disconnect()
        
        mock_pool.close.assert_called_once()
        assert db_manager._pool is None
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, db_manager: DatabaseManager) -> None:
        """Проверяет отключение, когда соединение не установлено."""
        db_manager._pool = None
        
        # Не должно вызывать исключений
        await db_manager.disconnect()
    
    @pytest.mark.asyncio
    async def test_execute(self, db_manager: DatabaseManager) -> None:
        """Проверяет выполнение запроса без возврата данных."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db_manager._pool = mock_pool
        
        result = await db_manager.execute("INSERT INTO test VALUES ($1)", "value")
        
        assert result == "INSERT 0 1"
        mock_conn.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch(self, db_manager: DatabaseManager) -> None:
        """Проверяет выполнение запроса с возвратом данных."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [{"id": 1, "name": "test"}]
        
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db_manager._pool = mock_pool
        
        result = await db_manager.fetch("SELECT * FROM test")
        
        assert len(result) == 1
        assert result[0]["id"] == 1
    
    @pytest.mark.asyncio
    async def test_fetchrow(self, db_manager: DatabaseManager) -> None:
        """Проверяет получение одной записи."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"id": 1, "name": "test"}
        
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db_manager._pool = mock_pool
        
        result = await db_manager.fetchrow("SELECT * FROM test WHERE id = $1", 1)
        
        assert result["id"] == 1
        mock_conn.fetchrow.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetchval(self, db_manager: DatabaseManager) -> None:
        """Проверяет получение одного значения."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 42
        
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db_manager._pool = mock_pool
        
        result = await db_manager.fetchval("SELECT COUNT(*) FROM test")
        
        assert result == 42
    
    @pytest.mark.asyncio
    async def test_acquire_context_manager(self, db_manager: DatabaseManager) -> None:
        """Проверяет контекстный менеджер acquire."""
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.acquire.return_value.__aexit__.return_value = None
        db_manager._pool = mock_pool
        
        async with db_manager.acquire() as conn:
            assert conn is mock_conn
    
    @pytest.mark.asyncio
    async def test_transaction_context_manager(self, db_manager: DatabaseManager) -> None:
        """Проверяет контекстный менеджер транзакции."""
        mock_conn = MagicMock()
        mock_conn.transaction.return_value.__aenter__.return_value = None
        mock_conn.transaction.return_value.__aexit__.return_value = None
        
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.acquire.return_value.__aexit__.return_value = None
        db_manager._pool = mock_pool
        
        async with db_manager.transaction() as conn:
            assert conn is mock_conn
