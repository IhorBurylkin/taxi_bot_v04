#!/usr/bin/env python3
# entrypoint_users_service.py
"""
Точка входа для Users Service.
Порт: 8084
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
    """Запуск Users Service."""
    await log_info(
        f"Запуск Users Service на порту {settings.deployment.USERS_SERVICE_PORT}",
        type_msg=TypeMsg.INFO,
    )
    
    config = uvicorn.Config(
        "src.services.users.app:app",
        host="0.0.0.0",
        port=settings.deployment.USERS_SERVICE_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
