#!/usr/bin/env python3
# entrypoint_bot.py
"""
Точка входа для запуска Telegram Bot компонента в Docker контейнере.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from main import main


if __name__ == "__main__":
    """Запуск только Telegram Bot компонента."""
    try:
        asyncio.run(main(mode="bot"))
    except KeyboardInterrupt:
        pass
