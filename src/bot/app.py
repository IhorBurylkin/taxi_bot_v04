# src/bot/app.py
"""
Инициализация Telegram бота.
Создание Bot и Dispatcher, настройка webhook/polling.
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
import redis.asyncio as redis

from src.common.logger import get_logger, log_info
from src.common.constants import TypeMsg

logger = get_logger("bot")


def create_bot(token: str | None = None) -> Bot:
    """
    Создаёт экземпляр бота.
    
    Args:
        token: Токен бота (если None, берётся из конфига)
        
    Returns:
        Экземпляр Bot
    """
    if token is None:
        from src.config import settings
        token = settings.telegram.BOT_TOKEN
    
    if not token:
        raise ValueError("BOT_TOKEN не задан")
    
    return Bot(
        token=token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )


def create_dispatcher(redis_url: str | None = None) -> Dispatcher:
    """
    Создаёт диспетчер с Redis storage для FSM.
    
    Args:
        redis_url: URL Redis (если None, берётся из конфига)
        
    Returns:
        Экземпляр Dispatcher
    """
    if redis_url is None:
        from src.config import settings
        redis_url = settings.redis.url
    
    # Создаём Redis storage для FSM
    redis_client = redis.from_url(redis_url)
    storage = RedisStorage(redis_client)
    
    dp = Dispatcher(storage=storage)
    
    # Регистрируем роутеры
    from src.bot.handlers import register_routers
    register_routers(dp)
    
    # Регистрируем middleware
    from src.bot.middleware import register_middleware
    register_middleware(dp)
    
    return dp


async def setup_webhook(bot: Bot, webhook_url: str, secret: str = "") -> None:
    """
    Настраивает webhook.
    
    Args:
        bot: Экземпляр бота
        webhook_url: URL webhook
        secret: Секретный токен
    """
    await log_info(f"Настройка webhook: {webhook_url}", type_msg=TypeMsg.INFO)
    
    await bot.set_webhook(
        url=webhook_url,
        secret_token=secret if secret else None,
        drop_pending_updates=True,
    )


async def remove_webhook(bot: Bot) -> None:
    """
    Удаляет webhook.
    
    Args:
        bot: Экземпляр бота
    """
    await bot.delete_webhook(drop_pending_updates=True)
    await log_info("Webhook удалён", type_msg=TypeMsg.INFO)
