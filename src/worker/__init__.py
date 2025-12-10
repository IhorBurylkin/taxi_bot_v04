# src/worker/__init__.py
"""
Фоновые воркеры для обработки событий из RabbitMQ.
"""

from src.worker.base import BaseWorker
from src.worker.matching import MatchingWorker
from src.worker.notifications import NotificationWorker

__all__ = ["BaseWorker", "MatchingWorker", "NotificationWorker"]
