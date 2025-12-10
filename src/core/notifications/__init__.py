# src/core/notifications/__init__.py
"""
Домен уведомлений.
Отправка уведомлений пользователям.
"""

from src.core.notifications.service import NotificationService

__all__ = [
    "NotificationService",
]
