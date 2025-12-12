# src/infra/database.py
"""
Менеджер базы данных PostgreSQL.
Реализует пул соединений, автоматический retry и транзакции.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, AsyncGenerator, Callable, TypeVar

import asyncpg
from asyncpg import Connection, Pool, Record

from src.common.logger import get_logger, log_error, log_info, log_warning
from src.common.constants import TypeMsg

logger = get_logger("database")

T = TypeVar("T")


def retry_on_connection_error(
    max_attempts: int = 3,
    delay: float = 1.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Декоратор для автоматического ретрая при ошибках подключения.
    
    Args:
        max_attempts: Максимальное количество попыток
        delay: Задержка между попытками (секунды)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except (
                    asyncpg.PostgresConnectionError,
                    asyncpg.InterfaceError,
                    ConnectionRefusedError,
                    OSError,
                ) as e:
                    last_error = e
                    if attempt < max_attempts:
                        await log_info(
                            f"Ошибка подключения к БД (попытка {attempt}/{max_attempts}): {e}",
                            type_msg=TypeMsg.WARNING,
                        )
                        await asyncio.sleep(delay * attempt)
                    else:
                        await log_error(f"Не удалось подключиться к БД после {max_attempts} попыток: {e}")
            
            raise last_error  # type: ignore
        
        return wrapper  # type: ignore
    
    return decorator


class DatabaseManager:
    """
    Менеджер подключений к PostgreSQL.
    Реализует паттерн Singleton для пула соединений.
    """
    
    _instance: DatabaseManager | None = None
    _pool: Pool | None = None
    
    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Инициализация (вызывается только один раз благодаря Singleton)."""
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._pool = None
    
    @property
    def pool(self) -> Pool:
        """Возвращает пул соединений."""
        if self._pool is None:
            raise RuntimeError("Пул соединений не инициализирован. Вызовите connect() сначала.")
        return self._pool
    
    @retry_on_connection_error(max_attempts=3, delay=1.0)
    async def connect(
        self,
        dsn: str | None = None,
        min_size: int = 5,
        max_size: int = 20,
        command_timeout: int = 60,
    ) -> None:
        """
        Создаёт пул соединений к PostgreSQL.
        
        Args:
            dsn: DSN строка подключения (если None, берётся из конфига)
            min_size: Минимальный размер пула
            max_size: Максимальный размер пула
            command_timeout: Таймаут команд (секунды)
        """
        if self._pool is not None:
            return
        
        # Получаем DSN из конфига, если не передан
        if dsn is None:
            from src.config import settings
            dsn = settings.database.dsn
            min_size = settings.database.DB_MIN_POOL_SIZE
            max_size = settings.database.DB_MAX_POOL_SIZE
            command_timeout = settings.database.DB_COMMAND_TIMEOUT
        
        await log_info("Подключение к PostgreSQL...", type_msg=TypeMsg.INFO)
        
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,
            command_timeout=command_timeout,
        )
        
        await log_info("Подключение к PostgreSQL установлено", type_msg=TypeMsg.INFO)
    
    async def disconnect(self) -> None:
        """Закрывает пул соединений."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            await log_info("Соединение с PostgreSQL закрыто", type_msg=TypeMsg.INFO)
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Connection, None]:
        """
        Контекстный менеджер для получения соединения из пула.
        
        Yields:
            Соединение с БД
            
        Example:
            async with db.acquire() as conn:
                result = await conn.fetch("SELECT * FROM users")
        """
        async with self.pool.acquire() as connection:
            yield connection
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Connection, None]:
        """
        Контекстный менеджер для транзакции.
        Автоматически делает commit при успехе и rollback при ошибке.
        
        Yields:
            Соединение с БД в контексте транзакции
            
        Example:
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO users ...")
                await conn.execute("UPDATE accounts ...")
        """
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                yield connection
    
    @retry_on_connection_error()
    async def execute(self, query: str, *args: Any) -> str:
        """
        Выполняет SQL запрос без возврата данных.
        
        Args:
            query: SQL запрос
            *args: Параметры запроса
            
        Returns:
            Статус выполнения
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    @retry_on_connection_error()
    async def fetch(self, query: str, *args: Any) -> list[Record]:
        """
        Выполняет SQL запрос и возвращает все строки.
        
        Args:
            query: SQL запрос
            *args: Параметры запроса
            
        Returns:
            Список записей
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    @retry_on_connection_error()
    async def fetchrow(self, query: str, *args: Any) -> Record | None:
        """
        Выполняет SQL запрос и возвращает одну строку.
        
        Args:
            query: SQL запрос
            *args: Параметры запроса
            
        Returns:
            Запись или None
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    @retry_on_connection_error()
    async def fetchval(self, query: str, *args: Any, column: int = 0) -> Any:
        """
        Выполняет SQL запрос и возвращает одно значение.
        
        Args:
            query: SQL запрос
            *args: Параметры запроса
            column: Индекс колонки
            
        Returns:
            Значение
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column)
    
    async def health_check(self) -> bool:
        """
        Проверяет здоровье подключения к БД.
        
        Returns:
            True если подключение работает
        """
        try:
            result = await self.fetchval("SELECT 1")
            return result == 1
        except Exception as e:
            await log_error(f"Health check PostgreSQL failed: {e}")
            return False


# Глобальный экземпляр
_db_manager: DatabaseManager | None = None


def get_db() -> DatabaseManager:
    """
    Возвращает глобальный экземпляр DatabaseManager.
    
    Returns:
        DatabaseManager
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_db() -> None:
    """
    Инициализирует подключение к базе данных.
    Использует настройки из конфигурации.
    """
    from src.config import settings
    
    db = get_db()
    await db.connect(
        dsn=settings.database.dsn,
        min_size=settings.database.DB_MIN_POOL_SIZE,
        max_size=settings.database.DB_MAX_POOL_SIZE,
        command_timeout=settings.database.DB_COMMAND_TIMEOUT,
    )
    await log_info(f"PostgreSQL подключён: {settings.database.DB_HOST}:{settings.database.DB_PORT}/{settings.database.DB_NAME}", type_msg=TypeMsg.INFO)
    
    # Инициализация схемы БД
    await _init_schema(db)


async def _init_schema(db: DatabaseManager) -> None:
    """Выполняет начальную миграцию БД."""
    from src.config.loader import get_project_root
    
    schema_path = get_project_root() / "migrations" / "init.sql"
    if not schema_path.exists():
        await log_error(f"Файл схемы БД не найден: {schema_path}")
        return

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
            
        await log_info("Применение схемы БД...", type_msg=TypeMsg.INFO)
        
        # Используем advisory lock для предотвращения одновременного запуска миграций
        # 123456789 - произвольный ID для лока
        async with db.acquire() as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(123456789)")
            await conn.execute(schema_sql)
            
        await log_info("Схема БД успешно применена", type_msg=TypeMsg.INFO)
    except Exception as e:
        await log_error(f"Ошибка при инициализации схемы БД: {e}")
        # Не рейзим ошибку, если это deadlock или duplicate, так как это может быть гонка при старте
        if "deadlock detected" in str(e) or "already exists" in str(e):
             await log_warning(f"Игнорируем ошибку инициализации (гонка процессов): {e}")
        else:
             raise


async def close_db() -> None:
    """
    Закрывает подключение к базе данных.
    """
    db = get_db()
    await db.disconnect()
    await log_info("PostgreSQL отключён", type_msg=TypeMsg.INFO)
