#!/usr/bin/env python3
# entrypoint_notifications.py
"""
Точка входа для запуска Notifications сервиса в Docker контейнере.
Централизованный сервис для обработки уведомлений (Telegram, Email, Push).
"""

from __future__ import annotations

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from main import main


if __name__ == "__main__":
    """Запуск Notifications сервиса."""
    
    # Для масштабирования: установить порт из переменной окружения
    instance_id = os.getenv("NOTIFICATIONS_INSTANCE_ID", "0")
    print(f"📢 Запуск Notifications instance #{instance_id}")
    
    try:
        asyncio.run(main(mode="notifications"))
    except KeyboardInterrupt:
        pass
