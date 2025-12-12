#!/usr/bin/env python3
# entrypoint_web_client.py
"""
Точка входа для запуска Web Client компонента в Docker контейнере.
Клиентский веб-интерфейс для пассажиров и водителей.
"""

from __future__ import annotations

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.web_client.app import run_web_client
from main import init_infrastructure
from nicegui import app
from src.config import settings

# Register startup handler to initialize infrastructure
@app.on_startup
async def on_startup():
    await init_infrastructure()

if __name__ == "__main__":
    """Запуск Web Client компонента."""
    
    # Для масштабирования: установить порт из переменной окружения
    instance_id = os.getenv("WEB_CLIENT_INSTANCE_ID", "0")
    print(f"🌐 Запуск Web Client instance #{instance_id}")
    
    try:
        # Run synchronously, NiceGUI handles the loop
        run_web_client(
            host=settings.telegram.WEBAPP_HOST,
            port=settings.deployment.WEB_CLIENT_PORT
        )
    except KeyboardInterrupt:
        pass
