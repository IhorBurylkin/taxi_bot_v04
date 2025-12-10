# src/bot/__init__.py
"""
Транспортный слой - Telegram Bot.
Хендлеры, роутеры, middleware для aiogram 3.x.
"""

from src.bot.app import create_bot, create_dispatcher

__all__ = [
    "create_bot",
    "create_dispatcher",
]
