# src/bot/middleware/__init__.py
"""
Middleware для Telegram бота.
"""

from aiogram import Dispatcher

from src.bot.middleware.auth import AuthMiddleware
from src.bot.middleware.logging import LoggingMiddleware


def register_middleware(dp: Dispatcher) -> None:
    """
    Регистрирует все middleware в диспетчере.
    
    Args:
        dp: Диспетчер
    """
    # Порядок важен! Сначала логирование, потом аутентификация
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())


__all__ = [
    "register_middleware",
    "AuthMiddleware",
    "LoggingMiddleware",
]
