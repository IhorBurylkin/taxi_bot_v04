# src/bot/middleware/logging.py
"""
Middleware для логирования событий.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware логирования.
    Логирует все входящие события.
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
        user_id = None
        event_type = type(event).__name__
        event_data = ""
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            event_data = event.text[:50] if event.text else "[no text]"
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            event_data = event.data or "[no data]"
        
        await log_info(
            f"[{event_type}] user={user_id} data={event_data}",
            type_msg=TypeMsg.DEBUG,
        )
        
        try:
            result = await handler(event, data)
            return result
        except Exception as e:
            await log_error(
                f"Ошибка в хендлере: {e}",
                extra={"user_id": user_id, "event_type": event_type},
            )
            raise
