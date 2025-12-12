#!/usr/bin/env python3
"""
Entrypoint для Order Matching Service.

Запуск:
    python entrypoint_order_matching.py
    
Порт по умолчанию: 8091
"""

import os
import sys

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

from src.config import settings


def main() -> None:
    """Запустить Order Matching Service."""
    port = settings.deployment.ORDER_MATCHING_SERVICE_PORT
    
    uvicorn.run(
        "src.services.order_matching.app:app",
        host="0.0.0.0",
        port=port,
        reload=settings.system.DEBUG,
        log_level=settings.system.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
