#!/usr/bin/env python3
# entrypoint_web.py
"""
Точка входа для запуска Web Admin компонента в Docker контейнере.
УСТАРЕЛ: Используйте entrypoint_web_admin.py или entrypoint_web_client.py
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
    """Запуск Web Admin компонента (для обратной совместимости)."""
    
    # Для масштабирования: установить порт из переменной окружения
    instance_id = os.getenv("WEB_INSTANCE_ID", "0")
    print(f"⚠️  УСТАРЕВШИЙ ENTRYPOINT: используйте entrypoint_web_admin.py")
    print(f"🌐 Запуск Web Admin instance #{instance_id}")
    
    try:
        asyncio.run(main(mode="web_admin"))
    except KeyboardInterrupt:
        pass
