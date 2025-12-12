# src/common/logger.py
"""
Модуль структурированного логирования.
Поддерживает JSON и текстовый формат, ротацию файлов, отправку в Telegram.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from src.common.constants import TypeMsg


# =============================================================================
# ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ ДЛЯ ВРЕМЕНИ СТАРТА
# =============================================================================

# Время запуска приложения (устанавливается один раз при импорте модуля)
_APP_START_DATETIME: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# Глобальный файловый хендлер (один для всех логгеров)
_GLOBAL_FILE_HANDLER: logging.Handler | None = None
# Глобальный хендлер ошибок
_GLOBAL_ERROR_HANDLER: logging.Handler | None = None

# Флаг инициализации (предотвращает повторную настройку)
_LOGGING_INITIALIZED: bool = False


# =============================================================================
# JSON FORMATTER
# =============================================================================

class JsonFormatter(logging.Formatter):
    """Форматтер для JSON логов."""

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись лога в JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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


class DateBasedRotatingFileHandler(RotatingFileHandler):
    """
    Хендлер для ротации логов.
    Пишет в фиксированный файл (например, taxi_bot.log).
    При ротации переименовывает текущий файл, добавляя дату и время.
    """
    
    def __init__(self, log_dir: str, max_bytes: int, logger_name: str = "app", encoding: str = 'utf-8'):
        """
        Args:
            log_dir: Директория для логов
            max_bytes: Максимальный размер файла в байтах
            logger_name: Имя логгера (используется в имени файла)
            encoding: Кодировка файла
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger_name = logger_name
        
        # Фиксированное имя файла
        filename = str(self.log_dir / f"{logger_name}.log")
        
        # Инициализируем родительский класс без ротации (backupCount=0)
        super().__init__(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=0,  # Отключаем стандартную ротацию
            encoding=encoding,
        )
    
    def shouldRollover(self, record: logging.LogRecord) -> bool:
        """
        Проверяет, нужна ли ротация.
        
        Ротация происходит только при превышении размера файла.
        """
        # Проверяем размер файла
        if self.maxBytes > 0:
            if self.stream is None:
                self.stream = self._open()
            self.stream.seek(0, 2)  # Переходим в конец файла
            if self.stream.tell() >= self.maxBytes:
                return True
        
        return False
    
    def doRollover(self) -> None:
        """
        Выполняет ротацию лог-файла.
        
        Переименовывает текущий файл в архивный и открывает новый.
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # Генерируем имя для архива
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_filename = self.log_dir / f"{self.logger_name}_{timestamp}.log"
        
        # Переименовываем текущий файл
        if os.path.exists(self.baseFilename):
            try:
                os.rename(self.baseFilename, archive_filename)
            except OSError:
                # Если не удалось переименовать (например, файл занят),
                # просто продолжаем (или можно добавить логику повтора)
                pass
        
        # Открываем новый файл (создастся заново)
        self.stream = self._open()


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
        color = self.COLORS.get(record.levelname, self.GRAY)
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
    Может безопасно вызываться многократно (идемпотентна).
    """
    global _LOGGING_INITIALIZED
    
    # Если уже инициализирован, пропускаем
    if _LOGGING_INITIALIZED:
        return
    
    _LOGGING_INITIALIZED = True
    
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
        # Защита от MagicMock в тестах
        if not isinstance(log_level, str):
            log_level = "DEBUG"
            
        log_format = settings.logging.LOG_FORMAT if hasattr(settings, 'logging') else "colored"
        if not isinstance(log_format, str):
            log_format = "colored"
            
        log_to_file = settings.logging.LOG_TO_FILE if hasattr(settings, 'logging') else False
        log_file_path = settings.logging.LOG_FILE_PATH if hasattr(settings, 'logging') else "logs/app.log"
        if not isinstance(log_file_path, str):
            log_file_path = "logs/app.log"
            
        log_max_bytes = settings.logging.LOG_MAX_BYTES if hasattr(settings, 'logging') else 10485760
        log_backup_count = settings.logging.LOG_BACKUP_COUNT if hasattr(settings, 'logging') else 5
        environment = settings.system.ENVIRONMENT if hasattr(settings, 'logging') else "development"
        if not isinstance(environment, str):
            environment = "development"
            
        run_dev_mode = settings.system.RUN_DEV_MODE if hasattr(settings, 'system') else False
    except Exception as e:
        log_level = "DEBUG"
        log_format = "colored"
        log_to_file = False
        log_file_path = "logs/app.log"
        log_max_bytes = 10485760
        log_backup_count = 5
        environment = "development"
        run_dev_mode = False
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    
    # Не добавляем хендлеры повторно (только если уже был настроен через наш кэш)
    if logger.handlers:
        return logger

    # Очищаем существующие хендлеры (на всякий случай)
    logger.handlers.clear()
    
    # Консольный хендлер
    console_handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)
    
    # Файловый хендлер (глобальный)
    if log_to_file:
        global _GLOBAL_FILE_HANDLER
        if _GLOBAL_FILE_HANDLER is None:
            # Определяем директорию логов
            log_path = Path(log_file_path)
            log_dir = log_path.parent
            log_name = log_path.stem
            
            # Если задана переменная окружения SERVICE_NAME, добавляем её к имени лога
            service_name = os.getenv("SERVICE_NAME")
            if service_name:
                log_name = f"{log_name}_{service_name}"

            # Если RUN_DEV_MODE=True, удаляем старый файл лога перед созданием нового
            # if run_dev_mode:
            #     full_log_path = log_dir / f"{log_name}.log"
            #     try:
            #         if full_log_path.exists():
            #             full_log_path.unlink()
            #             # Также можно вывести сообщение в консоль, но логгер еще не настроен
            #             print(f"[DEV_MODE] Удален старый лог файл: {full_log_path}")
            #     except Exception as e:
            #         print(f"⚠️ Ошибка при удалении старого лога: {e}")

            _GLOBAL_FILE_HANDLER = DateBasedRotatingFileHandler(
                log_dir=str(log_dir),
                max_bytes=log_max_bytes,
                logger_name=log_name,
            )
            if log_format == "json":
                _GLOBAL_FILE_HANDLER.setFormatter(JsonFormatter())
            else:
                # Используем ColoredFormatter для записи цветов в файл по запросу пользователя
                _GLOBAL_FILE_HANDLER.setFormatter(ColoredFormatter())
        
        logger.addHandler(_GLOBAL_FILE_HANDLER)

        # Добавляем отдельный файл для ошибок (фильтрация)
        global _GLOBAL_ERROR_HANDLER
        if _GLOBAL_ERROR_HANDLER is None:
            error_log_path = log_dir / "error.log"
            # Если RUN_DEV_MODE=True, удаляем старый файл ошибок
            # if run_dev_mode:
            #     try:
            #         if error_log_path.exists():
            #             error_log_path.unlink()
            #     except Exception:
            #         pass

            _GLOBAL_ERROR_HANDLER = DateBasedRotatingFileHandler(
                log_dir=str(log_dir),
                max_bytes=log_max_bytes,
                logger_name="error",
            )
            _GLOBAL_ERROR_HANDLER.setLevel(logging.ERROR)
            if log_format == "json":
                _GLOBAL_ERROR_HANDLER.setFormatter(JsonFormatter())
            else:
                _GLOBAL_ERROR_HANDLER.setFormatter(ColoredFormatter())
        
        logger.addHandler(_GLOBAL_ERROR_HANDLER)
    
    # Предотвращаем дублирование логов в родительских логгерах
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
