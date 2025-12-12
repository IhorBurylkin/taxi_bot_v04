#!/usr/bin/env python3
# entrypoint_worker.py
"""
Точка входа для запуска Worker компонента в Docker контейнере.
"""

from __future__ import annotations

import asyncio
import sys
import os

# Убеждаемся что путь к модулям правильный
sys.path.insert(0, "/app")

from main import main


if __name__ == "__main__":
    """Запуск только Worker компонента."""
    
    # Для масштабирования: показать идентификатор воркера
    worker_id = os.getenv("WORKER_INSTANCE_ID", "0")
    print(f"⚙️  Запуск Worker instance #{worker_id}")
    
    try:
        asyncio.run(main(mode="worker"))
    except KeyboardInterrupt:
        pass
