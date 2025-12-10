# src/bot/middleware/auth.py
"""
Middleware для аутентификации пользователей.
Обогащает контекст данными пользователя из БД.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from src.common.logger import log_info
from src.common.constants import TypeMsg


class AuthMiddleware(BaseMiddleware):
    """
    Middleware аутентификации.
    Загружает данные пользователя из БД и добавляет в контекст.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Обрабатывает входящее событие.
        
        Args:
            handler: Следующий обработчик
            event: Событие Telegram
            data: Контекстные данные
            
        Returns:
            Результат обработчика
        """
        # Получаем user_id
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        
        if user_id:
            # Загружаем пользователя из кэша/БД
            try:
                from src.bot.dependencies import get_user_service
                user_service = get_user_service()
                
                user = await user_service.get_user(user_id)
                data["db_user"] = user
                
                # Загружаем профиль водителя, если есть
                if user and user.role.value == "driver":
                    driver_profile = await user_service.get_driver_profile(user_id)
                    data["driver_profile"] = driver_profile
            except Exception:
                # Если не удалось загрузить — продолжаем без данных
                data["db_user"] = None
                data["driver_profile"] = None
        
        return await handler(event, data)
