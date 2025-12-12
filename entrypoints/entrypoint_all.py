#!/usr/bin/env python3
# entrypoint_all.py
"""
Точка входа для запуска всех компонентов (bot, web, worker) в одном контейнере.
Используется для разработки или простых деплойментов.
"""

from __future__ import annotations

import asyncio
import sys
import signal
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from main import main


if __name__ == "__main__":
    """Запуск всех компонентов одновременно."""
    print("[DEV_MODE] Запуск всех компонентов (bot + web + worker)...")
    print("Для остановки используйте Ctrl+C")
    
    try:
        asyncio.run(main(mode="everything"))
    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки, завершение работы...")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        sys.exit(1)
    finally:
        print("Все компоненты остановлены")
