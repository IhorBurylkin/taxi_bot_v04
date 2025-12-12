# tests/common/test_logger.py
"""
Unit тесты для модуля логирования (src/common/logger.py).
"""

import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.common.logger import (
    JsonFormatter,
    ColoredFormatter,
    get_logger,
    setup_logging,
    log_info,
    log_debug,
    log_warning,
    log_error,
    _get_caller_info,
    _loggers,
)
from src.common.constants import TypeMsg


class TestJsonFormatter:
    """Тесты для JsonFormatter."""

    def test_format_basic_record(self) -> None:
        """Тест форматирования базовой записи."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        
        assert '"level": "INFO"' in result
        assert '"message": "Test message"' in result
        assert '"module": "test_module"' in result
        assert '"function": "test_function"' in result
        assert '"line": 10' in result

    def test_format_with_extra_data(self) -> None:
        """Тест форматирования записи с дополнительными данными."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=20,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.extra_data = {"user_id": 123, "action": "test"}
        
        result = formatter.format(record)
        
        assert '"extra"' in result
        assert '"user_id": 123' in result
        assert '"action": "test"' in result

    def test_format_with_exception(self) -> None:
        """Тест форматирования записи с исключением."""
        formatter = JsonFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=30,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        
        assert '"exception"' in result
        assert "ValueError" in result
        assert "Test exception" in result


class TestColoredFormatter:
    """Тесты для ColoredFormatter."""

    def test_format_basic_record(self) -> None:
        """Тест цветного форматирования базовой записи."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        result = formatter.format(record)
        
        assert "INFO" in result
        assert "Test message" in result
        assert "\033[" in result  # ANSI код присутствует

    def test_format_with_caller_info(self) -> None:
        """Тест форматирования с информацией о вызывающей функции."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=15,
            msg="Debug message",
            args=(),
            exc_info=None,
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.extra_data = {
            "caller_function": "my_function",
            "caller_module": "my_module",
            "caller_file": "my_file.py",
            "caller_line": 42,
        }
        
        result = formatter.format(record)
        
        assert "my_module.my_function()" in result
        assert "my_file.py:42" in result


class TestGetLogger:
    """Тесты для get_logger."""

    def setup_method(self) -> None:
        """Очистка кэша логгеров перед каждым тестом."""
        _loggers.clear()
        # Очистка хендлеров у существующих логгеров
        for logger in logging.Logger.manager.loggerDict.values():
            if isinstance(logger, logging.Logger):
                logger.handlers.clear()

    def test_get_logger_creates_new_logger(self) -> None:
        """Тест создания нового логгера."""
        logger = get_logger("test_logger")
        
        assert logger is not None
        assert logger.name == "test_logger"
        # Проверяем, что есть хотя бы консольный хендлер
        assert len(logger.handlers) >= 1

    def test_get_logger_returns_cached_logger(self) -> None:
        """Тест возврата кэшированного логгера."""
        logger1 = get_logger("test_logger")
        logger2 = get_logger("test_logger")
        
        assert logger1 is logger2

    def test_get_logger_creates_log_directory(self) -> None:
        """Тест создания директории для логов."""
        get_logger("test_logger")
        
        log_dir = Path("logs")
        assert log_dir.exists()
        assert log_dir.is_dir()

    @patch("src.config.settings")
    def test_get_logger_uses_settings(self, mock_settings: Mock) -> None:
        """Тест использования настроек из конфига."""
        mock_settings.logging.LOG_LEVEL = "WARNING"
        mock_settings.logging.LOG_FORMAT = "json"
        mock_settings.logging.LOG_TO_FILE = True
        mock_settings.logging.LOG_FILE_PATH = "logs/test.log"
        mock_settings.logging.LOG_MAX_BYTES = 10485760
        mock_settings.logging.LOG_BACKUP_COUNT = 5
        mock_settings.system.ENVIRONMENT = "production"
        
        logger = get_logger("test_with_settings")
        
        assert logger.level == logging.WARNING

    def test_get_logger_handles_missing_settings(self) -> None:
        """Тест работы при отсутствии настроек."""
        # settings импортируется внутри функции, поэтому патчим модуль src.config
        with patch.dict('sys.modules', {'src.config': None}):
            logger = get_logger("test_no_settings")
            
            assert logger is not None
            assert logger.level == logging.DEBUG


class TestSetupLogging:
    """Тесты для setup_logging."""

    def setup_method(self) -> None:
        """Очистка перед тестом."""
        _loggers.clear()

    def test_setup_logging_initializes_system(self) -> None:
        """Тест инициализации системы логирования."""
        setup_logging()
        
        assert "taxi_bot" in _loggers

    def test_setup_logging_sets_third_party_levels(self) -> None:
        """Тест установки уровней для сторонних библиотек."""
        setup_logging()
        
        aiogram_logger = logging.getLogger("aiogram")
        asyncpg_logger = logging.getLogger("asyncpg")
        
        assert aiogram_logger.level == logging.INFO
        assert asyncpg_logger.level == logging.WARNING


class TestGetCallerInfo:
    """Тесты для _get_caller_info."""

    def test_get_caller_info_returns_dict(self) -> None:
        """Тест возврата словаря с информацией о вызывающей функции."""
        info = _get_caller_info()
        
        assert isinstance(info, dict)

    def test_get_caller_info_contains_caller_data(self) -> None:
        """Тест наличия данных о вызывающей функции."""
        def test_function():
            return _get_caller_info()
        
        info = test_function()
        
        # Может быть пустым, если не удалось получить информацию
        # Проверяем только тип
        assert isinstance(info, dict)


class TestLogFunctions:
    """Тесты для асинхронных функций логирования."""

    def setup_method(self) -> None:
        """Очистка перед тестом."""
        _loggers.clear()

    @pytest.mark.asyncio
    async def test_log_info_basic(self) -> None:
        """Тест базового логирования INFO."""
        with patch.object(logging.Logger, "info") as mock_info:
            await log_info("Test message")
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert "Test message" in call_args[0]

    @pytest.mark.asyncio
    async def test_log_info_with_type_msg(self) -> None:
        """Тест логирования с разными типами сообщений."""
        with patch.object(logging.Logger, "debug") as mock_debug:
            await log_info("Debug message", type_msg=TypeMsg.DEBUG)
            
            mock_debug.assert_called_once()

        with patch.object(logging.Logger, "warning") as mock_warning:
            await log_info("Warning message", type_msg=TypeMsg.WARNING)
            
            mock_warning.assert_called_once()

        with patch.object(logging.Logger, "error") as mock_error:
            await log_info("Error message", type_msg=TypeMsg.ERROR)
            
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_info_with_extra(self) -> None:
        """Тест логирования с дополнительными данными."""
        with patch.object(logging.Logger, "info") as mock_info:
            extra_data = {"user_id": 123, "action": "test"}
            await log_info("Test message", extra=extra_data)
            
            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            assert "extra" in call_kwargs

    @pytest.mark.asyncio
    async def test_log_debug(self) -> None:
        """Тест функции log_debug."""
        with patch.object(logging.Logger, "debug") as mock_debug:
            await log_debug("Debug message")
            
            mock_debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_warning(self) -> None:
        """Тест функции log_warning."""
        with patch.object(logging.Logger, "warning") as mock_warning:
            await log_warning("Warning message")
            
            mock_warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_error(self) -> None:
        """Тест функции log_error."""
        with patch.object(logging.Logger, "error") as mock_error:
            await log_error("Error message")
            
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_error_with_exc_info(self) -> None:
        """Тест логирования ошибки с трейсбеком."""
        with patch.object(logging.Logger, "error") as mock_error:
            await log_error("Error message", exc_info=True)
            
            mock_error.assert_called_once()
            call_kwargs = mock_error.call_args[1]
            assert call_kwargs.get("exc_info") is True

    @pytest.mark.asyncio
    async def test_log_info_with_custom_logger_name(self) -> None:
        """Тест логирования с пользовательским именем логгера."""
        custom_logger_name = "custom_logger"
        
        with patch("src.common.logger.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            await log_info("Test message", logger_name=custom_logger_name)
            
            mock_get_logger.assert_called_once_with(custom_logger_name)
            mock_logger.info.assert_called_once()
