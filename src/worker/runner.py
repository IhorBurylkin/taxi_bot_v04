# src/worker/runner.py
"""
Запускалка всех воркеров.
"""

from __future__ import annotations

import asyncio
from typing import List

from src.worker.base import BaseWorker
from src.worker.matching import MatchingWorker
from src.worker.notifications import NotificationWorker
from src.infra.database import init_db, close_db
from src.infra.redis_client import init_redis, close_redis
from src.infra.event_bus import init_event_bus, close_event_bus
from src.common.logger import log_info, log_error, setup_logging
from src.common.constants import TypeMsg


async def run_workers() -> None:
    """Запускает все воркеры."""
    await setup_logging()
    await log_info("Запуск воркеров...", type_msg=TypeMsg.INFO)
    
    # Инициализация инфраструктуры
    await init_db()
    await init_redis()
    await init_event_bus()
    
    # Создаём воркеры
    workers: List[BaseWorker] = [
        MatchingWorker(),
        NotificationWorker(),
    ]
    
    try:
        # Запускаем все воркеры
        for worker in workers:
            await worker.start()
        
        await log_info(
            f"Запущено {len(workers)} воркеров",
            type_msg=TypeMsg.INFO,
        )
        
        # Ждём завершения (Ctrl+C)
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        await log_info("Получен сигнал остановки", type_msg=TypeMsg.INFO)
    except Exception as e:
        await log_error(f"Критическая ошибка: {e}")
    finally:
        # Останавливаем воркеры
        for worker in workers:
            await worker.stop()
        
        # Закрываем инфраструктуру
        await close_event_bus()
        await close_redis()
        await close_db()
        
        await log_info("Воркеры остановлены", type_msg=TypeMsg.INFO)


def main() -> None:
    """Точка входа."""
    try:
        asyncio.run(run_workers())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
