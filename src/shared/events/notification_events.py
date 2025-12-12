# src/shared/events/notification_events.py
"""
События домена уведомлений.
"""

from __future__ import annotations

from typing import Literal, Any

from pydantic import Field

from src.shared.events.base import DomainEvent


class NotificationRequested(DomainEvent):
    """Событие: запрос на отправку уведомления."""
    
    event_type: Literal["notification.requested"] = "notification.requested"
    
    notification_id: str
    recipient_id: int  # telegram_id
    channel: str = "telegram"  # telegram, email, push
    template_key: str  # ключ из lang_dict
    template_params: dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"  # low, normal, high, critical
    # Дополнительные параметры для Telegram
    reply_markup: dict[str, Any] | None = None
    parse_mode: str = "HTML"


class NotificationSent(DomainEvent):
    """Событие: уведомление отправлено."""
    
    event_type: Literal["notification.sent"] = "notification.sent"
    
    notification_id: str
    recipient_id: int
    channel: str = "telegram"
    message_id: int | None = None  # telegram message_id


class NotificationFailed(DomainEvent):
    """Событие: отправка уведомления не удалась."""
    
    event_type: Literal["notification.failed"] = "notification.failed"
    
    notification_id: str
    recipient_id: int
    channel: str = "telegram"
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    will_retry: bool = False
