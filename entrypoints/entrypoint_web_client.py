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

# Убеждаемся что путь к модулям правильный
sys.path.insert(0, "/app")

from main import main


if __name__ == "__main__":
    """Запуск Web Client компонента."""
    
    # Для масштабирования: установить порт из переменной окружения
    instance_id = os.getenv("WEB_CLIENT_INSTANCE_ID", "0")
    print(f"🌐 Запуск Web Client instance #{instance_id}")
    
    try:
        asyncio.run(main(mode="web_client"))
    except KeyboardInterrupt:
        pass
