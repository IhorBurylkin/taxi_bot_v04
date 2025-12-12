#!/usr/bin/env python3
# entrypoint_worker.py
"""
Точка входа для запуска Worker компонента в Docker контейнере.
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
    """Запуск только Worker компонента."""
    
    # Для масштабирования: показать идентификатор воркера
    worker_id = os.getenv("WORKER_INSTANCE_ID", "0")
    print(f"⚙️  Запуск Worker instance #{worker_id}")
    
    try:
        asyncio.run(main(mode="worker"))
    except KeyboardInterrupt:
        pass
