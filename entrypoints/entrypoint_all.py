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

# Убеждаемся что путь к модулям правильный
sys.path.insert(0, "/app")

from main import main


if __name__ == "__main__":
    """Запуск всех компонентов одновременно."""
    print("[DEV_MODE] Запуск всех компонентов (bot + web + worker)...")
    print("Для остановки используйте Ctrl+C")
    
    try:
        asyncio.run(main(mode="all"))
    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки, завершение работы...")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        sys.exit(1)
    finally:
        print("Все компоненты остановлены")
