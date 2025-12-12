#!/usr/bin/env python3
"""
Entrypoint для MiniApp BFF.

Backend for Frontend для Telegram Mini App.

Запуск:
    python entrypoint_miniapp_bff.py
    
Порт по умолчанию: 8088
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

import uvicorn

from src.config import settings


def main() -> None:
    """Запустить MiniApp BFF."""
    port = settings.deployment.MINIAPP_BFF_PORT
    
    uvicorn.run(
        "src.services.miniapp_bff.app:app",
        host="0.0.0.0",
        port=port,
        reload=settings.system.DEBUG,
        log_level=settings.system.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
