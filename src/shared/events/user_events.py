# src/shared/events/user_events.py
"""
События домена пользователей.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.shared.events.base import DomainEvent, EventMetadata


class UserRegistered(DomainEvent):
    """Событие: пользователь зарегистрирован."""
    
    event_type: Literal["user.registered"] = "user.registered"
    
    user_id: int
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str = "en"
    role: str = "rider"  # rider, driver


class UserProfileUpdated(DomainEvent):
    """Событие: профиль пользователя обновлён."""
    
    event_type: Literal["user.profile_updated"] = "user.profile_updated"
    
    user_id: int
    updated_fields: dict[str, any] = Field(default_factory=dict)


class UserBlocked(DomainEvent):
    """Событие: пользователь заблокирован."""
    
    event_type: Literal["user.blocked"] = "user.blocked"
    
    user_id: int
    reason: str | None = None
    blocked_by: int | None = None  # admin_id


class UserUnblocked(DomainEvent):
    """Событие: пользователь разблокирован."""
    
    event_type: Literal["user.unblocked"] = "user.unblocked"
    
    user_id: int
    unblocked_by: int | None = None  # admin_id


class DriverStatusChanged(DomainEvent):
    """Событие: статус водителя изменён."""
    
    event_type: Literal["driver.status_changed"] = "driver.status_changed"
    
    driver_id: int
    old_status: str | None = None
    new_status: str  # online, offline, busy, on_trip
    location_lat: float | None = None
    location_lon: float | None = None
