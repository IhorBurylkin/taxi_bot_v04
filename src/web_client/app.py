# src/web_client/app.py
"""
NiceGUI приложение для клиентского веб-интерфейса.
Предоставляет UI для пассажиров и водителей.
"""

from __future__ import annotations

from typing import Optional
import asyncio

from nicegui import app, ui

from src.config import settings
from src.common.logger import log_info
from src.common.constants import TypeMsg


def create_app() -> None:
    """Создаёт и конфигурирует NiceGUI приложение для клиентов."""
    
    # Регистрируем маршруты
    from src.web_client.views import home, order, profile, tracking
    
    # Инициализация при старте
    @app.on_startup
    async def startup() -> None:
        """Инициализация при старте веб-клиента."""
        await log_info("Web Client запущен", type_msg=TypeMsg.INFO)
    
    @app.on_shutdown
    async def shutdown() -> None:
        """Очистка ресурсов при остановке."""
        await log_info("Web Client остановлен", type_msg=TypeMsg.INFO)


def run_web_client(
    host: str = "0.0.0.0",
    port: int = 8082,
    reload: bool = False,
) -> None:
    """
    Запускает веб-сервер для клиентов.
    
    Args:
        host: Хост для привязки
        port: Порт
        reload: Авто-перезагрузка при изменениях
    """
    create_app()
    ui.run(
        host=host,
        port=port,
        reload=reload,
        title="Taxi Bot — Заказ такси",
        favicon="🚕",
    )
