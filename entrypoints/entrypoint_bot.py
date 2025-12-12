#!/usr/bin/env python3
# entrypoint_bot.py
"""
Точка входа для запуска Telegram Bot компонента в Docker контейнере.
"""

from __future__ import annotations

import asyncio
import sys

# Убеждаемся что путь к модулям правильный
sys.path.insert(0, "/app")

from main import main


if __name__ == "__main__":
    """Запуск только Telegram Bot компонента."""
    try:
        asyncio.run(main(mode="bot"))
    except KeyboardInterrupt:
        pass
