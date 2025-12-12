#!/usr/bin/env python3
# entrypoint_web_admin.py
"""
Точка входа для запуска Web Admin компонента в Docker контейнере.
Админ-панель для управления заказами, водителями и мониторинга системы.
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
    """Запуск Web Admin компонента."""
    
    # Для масштабирования: установить порт из переменной окружения
    instance_id = os.getenv("WEB_ADMIN_INSTANCE_ID", "0")
    print(f"🔐 Запуск Web Admin instance #{instance_id}")
    
    try:
        asyncio.run(main(mode="web_admin"))
    except KeyboardInterrupt:
        pass
