#!/usr/bin/env python3
# entrypoint_trip_service.py
"""
Точка входа для Trip Service.
Порт: 8085
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn

from src.config import settings
from src.common.logger import log_info
from src.common.constants import TypeMsg


async def main() -> None:
    """Запуск Trip Service."""
    await log_info(
        f"Запуск Trip Service на порту {settings.deployment.TRIP_SERVICE_PORT}",
        type_msg=TypeMsg.INFO,
    )
    
    config = uvicorn.Config(
        "src.services.trips.app:app",
        host="0.0.0.0",
        port=settings.deployment.TRIP_SERVICE_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
