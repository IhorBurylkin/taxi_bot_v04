#!/usr/bin/env python3
"""
Entrypoint для Payments Service.

Запуск:
    python entrypoint_payments_service.py
    
Порт по умолчанию: 8087
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
    """Запустить Payments Service."""
    port = settings.deployment.PAYMENTS_SERVICE_PORT
    
    uvicorn.run(
        "src.services.payments.app:app",
        host="0.0.0.0",
        port=port,
        reload=settings.system.DEBUG,
        log_level=settings.system.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
