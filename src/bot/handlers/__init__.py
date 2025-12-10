# src/bot/handlers/__init__.py
"""
Хендлеры Telegram бота.
Организованы по роутерам: пассажиры, водители, общие.
"""

from aiogram import Dispatcher, Router

from src.bot.handlers.common import router as common_router
from src.bot.handlers.passenger import router as passenger_router
from src.bot.handlers.driver import router as driver_router


def register_routers(dp: Dispatcher) -> None:
    """
    Регистрирует все роутеры в диспетчере.
    
    Args:
        dp: Диспетчер
    """
    # Порядок важен! Сначала общие, потом специфичные
    dp.include_router(common_router)
    dp.include_router(passenger_router)
    dp.include_router(driver_router)


__all__ = [
    "register_routers",
    "common_router",
    "passenger_router",
    "driver_router",
]
