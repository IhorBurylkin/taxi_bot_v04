# src/common/logger.py
"""
Модуль структурированного логирования.
Поддерживает JSON и текстовый формат, ротацию файлов, отправку в Telegram.
"""

from __future__ import annotations

import inspect
import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from src.common.constants import TypeMsg


# =============================================================================
# JSON FORMATTER
# =============================================================================

class JsonFormatter(logging.Formatter):
    """Форматтер для JSON логов."""

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись лога в JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Добавляем дополнительные поля, если есть
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        # Добавляем информацию об исключении
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredFormatter(logging.Formatter):
    """Цветной форматтер для консоли (разработка)."""

    # ANSI коды цветов
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    GRAY = "\033[90m"  # Серый для информации о вызывающей функции

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись лога с цветом."""
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Формируем caller info, если есть
        caller_info = ""
        if hasattr(record, "extra_data") and record.extra_data:
            caller_func = record.extra_data.get("caller_function")
            caller_module = record.extra_data.get("caller_module")
            caller_file = record.extra_data.get("caller_file")
            caller_line = record.extra_data.get("caller_line")
            
            if caller_func:
                caller_info = f" {self.GRAY}[{caller_module}.{caller_func}() {caller_file}:{caller_line}]{self.RESET}"
        
        # Основное сообщение
        message = (
            f"{timestamp} {color}[{record.levelname}]{self.RESET}{caller_info} "
            #f"{record.name}:{record.funcName}:{record.lineno} - "
            f"{record.getMessage()}"
        )
        
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)
        
        return message


# =============================================================================
# ЛОГГЕР
# =============================================================================

_loggers: dict[str, logging.Logger] = {}


def setup_logging() -> None:
    """
    Инициализирует систему логирования.
    Вызывается при старте приложения для настройки корневого логгера.
    """
    # Получаем основной логгер для инициализации всей системы
    get_logger("taxi_bot")
    
    # Устанавливаем уровень для сторонних библиотек
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str = "taxi_bot") -> logging.Logger:
    """
    Возвращает настроенный логгер.
    Использует кэширование для избежания дублирования хендлеров.
    
    Args:
        name: Имя логгера
        
    Returns:
        Настроенный логгер
    """
    if name in _loggers:
        return _loggers[name]
    
    # Ленивый импорт для избежания циклических зависимостей
    try:
        from src.config import settings
        log_level = settings.logging.LOG_LEVEL if hasattr(settings, 'logging') else "DEBUG"
        log_format = settings.logging.LOG_FORMAT if hasattr(settings, 'logging') else "colored"
        log_to_file = settings.logging.LOG_TO_FILE if hasattr(settings, 'logging') else False
        log_file_path = settings.logging.LOG_FILE_PATH if hasattr(settings, 'logging') else "logs/app.log"
        log_max_bytes = settings.logging.LOG_MAX_BYTES if hasattr(settings, 'logging') else 10485760
        log_backup_count = settings.logging.LOG_BACKUP_COUNT if hasattr(settings, 'logging') else 5
        environment = settings.system.ENVIRONMENT if hasattr(settings, 'system') else "development"
    except Exception:
        log_level = "DEBUG"
        log_format = "colored"
        log_to_file = False
        log_file_path = "logs/app.log"
        log_max_bytes = 10485760
        log_backup_count = 5
        environment = "development"
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    
    # Не добавляем хендлеры повторно
    if logger.handlers:
        _loggers[name] = logger
        return logger
    
    # Консольный хендлер
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # Выбор форматтера в зависимости от окружения
    if environment == "production" or log_format == "json":
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter())
    
    logger.addHandler(console_handler)
    
    # Файловый хендлер (всегда включен, пишем в logs/)
    log_path = Path("logs/app.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    
    # Предотвращаем дублирование логов
    logger.propagate = False
    
    _loggers[name] = logger
    return logger


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ЛОГИРОВАНИЯ
# =============================================================================

def _get_caller_info() -> dict[str, Any]:
    """
    Получает информацию о вызывающей функции.
    
    Returns:
        Словарь с информацией о вызывающей функции:
        - caller_function: Имя функции, вызвавшей логирование
        - caller_module: Модуль вызывающей функции
        - caller_file: Файл вызывающей функции
        - caller_line: Номер строки вызова
    """
    try:
        # Получаем стек вызовов
        # [0] - текущая функция (_get_caller_info)
        # [1] - функция логирования (log_info, log_debug и т.д.)
        # [2] - реальный вызывающий код
        frame = inspect.currentframe()
        if frame is None:
            return {}
        
        # Поднимаемся на 2 уровня вверх по стеку
        caller_frame = frame.f_back
        if caller_frame:
            caller_frame = caller_frame.f_back
        
        if caller_frame is None:
            return {}
        
        # Получаем информацию о вызывающем коде
        frame_info = inspect.getframeinfo(caller_frame)
        caller_function = caller_frame.f_code.co_name
        caller_module = inspect.getmodule(caller_frame)
        
        return {
            "caller_function": caller_function,
            "caller_module": caller_module.__name__ if caller_module else "unknown",
            "caller_file": frame_info.filename.split("/")[-1] if frame_info.filename else "unknown",
            "caller_line": frame_info.lineno,
        }
    except Exception:
        # В случае ошибки возвращаем пустой словарь
        return {}
    finally:
        # Освобождаем ссылки на фреймы для избежания утечек памяти
        del frame
        if 'caller_frame' in locals():
            del caller_frame


async def log_info(
    message: str,
    *,
    type_msg: TypeMsg = TypeMsg.INFO,
    logger_name: str = "taxi_bot",
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Асинхронная функция логирования (INFO уровень).
    
    Args:
        message: Сообщение для логирования
        type_msg: Тип сообщения (для совместимости)
        logger_name: Имя логгера
        extra: Дополнительные данные
    """
    logger = get_logger(logger_name)
    
    # Получаем информацию о вызывающей функции
    caller_info = _get_caller_info()
    
    # Объединяем caller_info и extra
    record_extra = {"extra_data": {**caller_info, **(extra or {})}}
    
    match type_msg:
        case TypeMsg.DEBUG:
            logger.debug(message, extra=record_extra)
        case TypeMsg.INFO:
            logger.info(message, extra=record_extra)
        case TypeMsg.WARNING:
            logger.warning(message, extra=record_extra)
        case TypeMsg.ERROR:
            logger.error(message, extra=record_extra)
        case TypeMsg.CRITICAL:
            logger.critical(message, extra=record_extra)
        case _:
            logger.info(message, extra=record_extra)


async def log_debug(
    message: str,
    logger_name: str = "taxi_bot",
    extra: dict[str, Any] | None = None,
) -> None:
    """Логирование DEBUG уровня."""
    await log_info(message, type_msg=TypeMsg.DEBUG, logger_name=logger_name, extra=extra)


async def log_warning(
    message: str,
    logger_name: str = "taxi_bot",
    extra: dict[str, Any] | None = None,
) -> None:
    """Логирование WARNING уровня."""
    await log_info(message, type_msg=TypeMsg.WARNING, logger_name=logger_name, extra=extra)


async def log_error(
    message: str,
    logger_name: str = "taxi_bot",
    extra: dict[str, Any] | None = None,
    exc_info: bool = False,
) -> None:
    """
    Логирование ERROR уровня.
    
    Args:
        message: Сообщение об ошибке
        logger_name: Имя логгера
        extra: Дополнительные данные
        exc_info: Включать ли трейсбек исключения
    """
    logger = get_logger(logger_name)
    
    # Получаем информацию о вызывающей функции
    caller_info = _get_caller_info()
    
    # Объединяем caller_info и extra
    record_extra = {"extra_data": {**caller_info, **(extra or {})}}
    
    logger.error(message, extra=record_extra, exc_info=exc_info)
