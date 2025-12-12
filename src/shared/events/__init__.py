# src/shared/events/__init__.py
"""
Схемы событий для RabbitMQ.

События разделены по доменам:
- user_events: регистрация, обновление профиля, блокировка
- trip_events: создание, изменение статуса, завершение
- payment_events: запрос оплаты, успех, неудача
- notification_events: запрос на отправку уведомления
- location_events: обновление геолокации (только важные)

Все события идемпотентны и содержат event_id для дедупликации.
"""

from src.shared.events.base import DomainEvent, EventMetadata
from src.shared.events.user_events import (
    UserRegistered,
    UserProfileUpdated,
    UserBlocked,
    UserUnblocked,
    DriverStatusChanged,
)
from src.shared.events.trip_events import (
    TripCreated,
    TripStatusChanged,
    TripCompleted,
    TripCancelled,
    MatchRequested,
    OfferCreated,
    OfferAccepted,
    OfferExpired,
    DriverArrived,
    RideStarted,
)
from src.shared.events.payment_events import (
    PaymentRequested,
    PaymentSucceeded,
    PaymentFailed,
    RefundRequested,
    RefundCompleted,
)
from src.shared.events.notification_events import (
    NotificationRequested,
    NotificationSent,
    NotificationFailed,
)

__all__ = [
    # Base
    "DomainEvent",
    "EventMetadata",
    # User events
    "UserRegistered",
    "UserProfileUpdated",
    "UserBlocked",
    "UserUnblocked",
    "DriverStatusChanged",
    # Trip events
    "TripCreated",
    "TripStatusChanged",
    "TripCompleted",
    "TripCancelled",
    "MatchRequested",
    "OfferCreated",
    "OfferAccepted",
    "OfferExpired",
    "DriverArrived",
    "RideStarted",
    # Payment events
    "PaymentRequested",
    "PaymentSucceeded",
    "PaymentFailed",
    "RefundRequested",
    "RefundCompleted",
    # Notification events
    "NotificationRequested",
    "NotificationSent",
    "NotificationFailed",
]
