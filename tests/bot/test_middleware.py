# tests/bot/test_middleware.py
"""
Тесты для middleware Telegram бота.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message, CallbackQuery, User

from src.bot.middleware.auth import AuthMiddleware
from src.bot.middleware.logging import LoggingMiddleware
from src.common.constants import UserRole
from src.core.users.models import User as DBUser


@pytest.fixture
def mock_handler() -> AsyncMock:
    """Создаёт мок хендлера."""
    handler = AsyncMock()
    handler.return_value = "result"
    return handler


@pytest.fixture
def mock_message() -> Message:
    """Создаёт мок Message."""
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123456
    message.text = "Test message"
    return message


@pytest.fixture
def mock_callback() -> CallbackQuery:
    """Создаёт мок CallbackQuery."""
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 123456
    callback.data = "test_callback"
    return callback


@pytest.fixture
def sample_db_user() -> DBUser:
    """Создаёт примерного пользователя БД."""
    return DBUser(
        id=123456,
        username="test_user",
        first_name="Иван",
        last_name="Петров",
        role=UserRole.PASSENGER,
        rating=4.8,
        trips_count=10,
    )


class TestAuthMiddleware:
    """Тесты для AuthMiddleware."""
    
    @pytest.mark.asyncio
    async def test_auth_middleware_with_message(
        self,
        mock_handler: AsyncMock,
        mock_message: Message,
        sample_db_user: DBUser,
    ) -> None:
        """Проверяет работу middleware с Message."""
        # Arrange
        middleware = AuthMiddleware()
        data: Dict[str, Any] = {}
        
        mock_user_service = MagicMock()
        mock_user_service.get_user = AsyncMock(return_value=sample_db_user)
        mock_user_service.get_driver_profile = AsyncMock(return_value=None)
        
        # Act
        with patch("src.bot.dependencies.get_user_service", return_value=mock_user_service):
            result = await middleware(mock_handler, mock_message, data)
        
        # Assert
        assert result == "result"
        assert data["db_user"] == sample_db_user
        mock_handler.assert_called_once_with(mock_message, data)
    
    @pytest.mark.asyncio
    async def test_auth_middleware_with_callback(
        self,
        mock_handler: AsyncMock,
        mock_callback: CallbackQuery,
        sample_db_user: DBUser,
    ) -> None:
        """Проверяет работу middleware с CallbackQuery."""
        # Arrange
        middleware = AuthMiddleware()
        data: Dict[str, Any] = {}
        
        mock_user_service = MagicMock()
        mock_user_service.get_user = AsyncMock(return_value=sample_db_user)
        mock_user_service.get_driver_profile = AsyncMock(return_value=None)
        
        # Act
        with patch("src.bot.dependencies.get_user_service", return_value=mock_user_service):
            result = await middleware(mock_handler, mock_callback, data)
        
        # Assert
        assert result == "result"
        assert data["db_user"] == sample_db_user
        mock_handler.assert_called_once_with(mock_callback, data)
    
    @pytest.mark.asyncio
    async def test_auth_middleware_with_driver(
        self,
        mock_handler: AsyncMock,
        mock_message: Message,
    ) -> None:
        """Проверяет загрузку профиля водителя."""
        # Arrange
        middleware = AuthMiddleware()
        data: Dict[str, Any] = {}
        
        driver_user = DBUser(
            id=123456,
            username="driver_user",
            first_name="Пётр",
            last_name="Водителев",
            role=UserRole.DRIVER,
        )
        
        mock_driver_profile = MagicMock()
        
        mock_user_service = MagicMock()
        mock_user_service.get_user = AsyncMock(return_value=driver_user)
        mock_user_service.get_driver_profile = AsyncMock(return_value=mock_driver_profile)
        
        # Act
        with patch("src.bot.dependencies.get_user_service", return_value=mock_user_service):
            result = await middleware(mock_handler, mock_message, data)
        
        # Assert
        assert result == "result"
        assert data["db_user"] == driver_user
        assert data["driver_profile"] == mock_driver_profile
    
    @pytest.mark.asyncio
    async def test_auth_middleware_user_not_found(
        self,
        mock_handler: AsyncMock,
        mock_message: Message,
    ) -> None:
        """Проверяет обработку отсутствующего пользователя."""
        # Arrange
        middleware = AuthMiddleware()
        data: Dict[str, Any] = {}
        
        mock_user_service = MagicMock()
        mock_user_service.get_user = AsyncMock(return_value=None)
        
        # Act
        with patch("src.bot.dependencies.get_user_service", return_value=mock_user_service):
            result = await middleware(mock_handler, mock_message, data)
        
        # Assert
        assert result == "result"
        assert data["db_user"] is None
    
    @pytest.mark.asyncio
    async def test_auth_middleware_error_handling(
        self,
        mock_handler: AsyncMock,
        mock_message: Message,
    ) -> None:
        """Проверяет обработку ошибок при загрузке пользователя."""
        # Arrange
        middleware = AuthMiddleware()
        data: Dict[str, Any] = {}
        
        mock_user_service = MagicMock()
        mock_user_service.get_user = AsyncMock(side_effect=Exception("DB error"))
        
        # Act
        with patch("src.bot.dependencies.get_user_service", return_value=mock_user_service):
            result = await middleware(mock_handler, mock_message, data)
        
        # Assert
        assert result == "result"
        assert data["db_user"] is None
        assert data["driver_profile"] is None
    
    @pytest.mark.asyncio
    async def test_auth_middleware_no_user_id(
        self,
        mock_handler: AsyncMock,
    ) -> None:
        """Проверяет обработку события без user_id."""
        # Arrange
        middleware = AuthMiddleware()
        data: Dict[str, Any] = {}
        
        message = MagicMock(spec=Message)
        message.from_user = None
        
        # Act
        result = await middleware(mock_handler, message, data)
        
        # Assert
        assert result == "result"
        assert "db_user" not in data


class TestLoggingMiddleware:
    """Тесты для LoggingMiddleware."""
    
    @pytest.mark.asyncio
    async def test_logging_middleware_with_message(
        self,
        mock_handler: AsyncMock,
        mock_message: Message,
    ) -> None:
        """Проверяет логирование Message."""
        # Arrange
        middleware = LoggingMiddleware()
        data: Dict[str, Any] = {}
        
        # Act
        with patch("src.bot.middleware.logging.log_info", new_callable=AsyncMock) as mock_log:
            result = await middleware(mock_handler, mock_message, data)
        
        # Assert
        assert result == "result"
        mock_log.assert_called_once()
        log_message = mock_log.call_args[0][0]
        assert "123456" in log_message  # Проверяем user_id
        assert "Test message" in log_message  # Проверяем текст
        mock_handler.assert_called_once_with(mock_message, data)
    
    @pytest.mark.asyncio
    async def test_logging_middleware_with_callback(
        self,
        mock_handler: AsyncMock,
        mock_callback: CallbackQuery,
    ) -> None:
        """Проверяет логирование CallbackQuery."""
        # Arrange
        middleware = LoggingMiddleware()
        data: Dict[str, Any] = {}
        
        # Act
        with patch("src.bot.middleware.logging.log_info", new_callable=AsyncMock) as mock_log:
            result = await middleware(mock_handler, mock_callback, data)
        
        # Assert
        assert result == "result"
        mock_log.assert_called_once()
        log_message = mock_log.call_args[0][0]
        assert "123456" in log_message  # Проверяем user_id
        assert "test_callback" in log_message  # Проверяем callback data
    
    @pytest.mark.asyncio
    async def test_logging_middleware_handler_error(
        self,
        mock_handler: AsyncMock,
        mock_message: Message,
    ) -> None:
        """Проверяет логирование ошибок хендлера."""
        # Arrange
        middleware = LoggingMiddleware()
        data: Dict[str, Any] = {}
        
        mock_handler.side_effect = ValueError("Handler error")
        
        # Act & Assert
        with patch("src.bot.middleware.logging.log_info", new_callable=AsyncMock):
            with patch("src.bot.middleware.logging.log_error", new_callable=AsyncMock) as mock_error:
                with pytest.raises(ValueError, match="Handler error"):
                    await middleware(mock_handler, mock_message, data)
                
                mock_error.assert_called_once()
                error_message = mock_error.call_args[0][0]
                assert "Ошибка в хендлере" in error_message
    
    @pytest.mark.asyncio
    async def test_logging_middleware_no_user(
        self,
        mock_handler: AsyncMock,
    ) -> None:
        """Проверяет логирование события без пользователя."""
        # Arrange
        middleware = LoggingMiddleware()
        data: Dict[str, Any] = {}
        
        message = MagicMock(spec=Message)
        message.from_user = None
        message.text = "Test"
        
        # Act
        with patch("src.bot.middleware.logging.log_info", new_callable=AsyncMock) as mock_log:
            result = await middleware(mock_handler, message, data)
        
        # Assert
        assert result == "result"
        mock_log.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_logging_middleware_long_text_truncation(
        self,
        mock_handler: AsyncMock,
    ) -> None:
        """Проверяет обрезку длинного текста."""
        # Arrange
        middleware = LoggingMiddleware()
        data: Dict[str, Any] = {}
        
        message = MagicMock(spec=Message)
        message.from_user = MagicMock(spec=User)
        message.from_user.id = 123456
        message.text = "A" * 100  # Длинный текст
        
        # Act
        with patch("src.bot.middleware.logging.log_info", new_callable=AsyncMock) as mock_log:
            await middleware(mock_handler, message, data)
        
        # Assert
        log_message = mock_log.call_args[0][0]
        # Проверяем, что текст обрезан до 50 символов
        assert len(message.text) == 100
        assert "A" * 50 in log_message
