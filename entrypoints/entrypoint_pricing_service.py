#!/usr/bin/env python3
# entrypoint_pricing_service.py
"""
Точка входа для Pricing Service.
Порт: 8086
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

import uvicorn

from src.config import settings
from src.common.logger import log_info
from src.common.constants import TypeMsg


async def main() -> None:
    """Запуск Pricing Service."""
    await log_info(
        f"Запуск Pricing Service на порту {settings.deployment.PRICING_SERVICE_PORT}",
        type_msg=TypeMsg.INFO,
    )
    
    config = uvicorn.Config(
        "src.services.pricing.app:app",
        host="0.0.0.0",
        port=settings.deployment.PRICING_SERVICE_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
