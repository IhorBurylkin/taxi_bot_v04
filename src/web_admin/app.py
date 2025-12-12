# src/web/app.py
"""
NiceGUI приложение для админ-панели и мониторинга.
"""

from __future__ import annotations

from typing import Optional
import asyncio

from nicegui import app, ui

from src.config import settings
from src.common.logger import log_info
from src.common.constants import TypeMsg


def create_app() -> None:
    """Создаёт и конфигурирует NiceGUI приложение."""
    
    # Регистрируем маршруты
    from src.web.views import dashboard, orders, drivers, health
    
    # Инициализация при старте
    @app.on_startup
    async def startup() -> None:
        """Инициализация при старте веб-приложения."""
        await log_info("Web UI запущен", type_msg=TypeMsg.INFO)
    
    @app.on_shutdown
    async def shutdown() -> None:
        """Очистка ресурсов при остановке."""
        await log_info("Web UI остановлен", type_msg=TypeMsg.INFO)


def run_web(
    host: str = "0.0.0.0",
    port: int = 8081,
    reload: bool = False,
) -> None:
    """
    Запускает веб-сервер.
    
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
        title="Taxi Bot Admin",
        favicon="🚕",
    )
