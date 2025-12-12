#!/usr/bin/env python3
"""
Entrypoint для Realtime WebSocket Gateway.

Запуск:
    python entrypoint_realtime_ws.py
    
Порт по умолчанию: 8089
"""

import os
import sys

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

from src.config import settings


def main() -> None:
    """Запустить Realtime WebSocket Gateway."""
    port = settings.deployment.REALTIME_WS_GATEWAY_PORT
    
    uvicorn.run(
        "src.services.realtime_ws.app:app",
        host="0.0.0.0",
        port=port,
        reload=settings.system.DEBUG,
        log_level=settings.system.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
