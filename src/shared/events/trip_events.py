# src/shared/events/trip_events.py
"""
События домена поездок (trip/order).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.shared.events.base import DomainEvent


class TripCreated(DomainEvent):
    """Событие: поездка/заказ создан."""
    
    event_type: Literal["trip.created"] = "trip.created"
    
    trip_id: str
    rider_id: int
    pickup_lat: float
    pickup_lon: float
    pickup_address: str | None = None
    dropoff_lat: float
    dropoff_lon: float
    dropoff_address: str | None = None
    distance_km: float | None = None
    duration_minutes: int | None = None
    estimated_fare: float | None = None
    currency: str = "EUR"


class TripStatusChanged(DomainEvent):
    """Событие: статус поездки изменён."""
    
    event_type: Literal["trip.status_changed"] = "trip.status_changed"
    
    trip_id: str
    old_status: str | None = None
    new_status: str  # pending, matching, accepted, driver_arrived, in_progress, completed, cancelled
    driver_id: int | None = None
    reason: str | None = None


class TripCompleted(DomainEvent):
    """Событие: поездка завершена."""
    
    event_type: Literal["trip.completed"] = "trip.completed"
    
    trip_id: str
    rider_id: int
    driver_id: int
    final_fare: float
    currency: str = "EUR"
    distance_km: float
    duration_minutes: int
    rating_rider: int | None = None
    rating_driver: int | None = None


class TripCancelled(DomainEvent):
    """Событие: поездка отменена."""
    
    event_type: Literal["trip.cancelled"] = "trip.cancelled"
    
    trip_id: str
    cancelled_by: str  # rider, driver, system
    cancellation_reason: str | None = None
    cancellation_fee: float | None = None


class MatchRequested(DomainEvent):
    """Событие: запрос на поиск водителя."""
    
    event_type: Literal["match.requested"] = "match.requested"
    
    trip_id: str
    pickup_lat: float
    pickup_lon: float
    search_radius_km: float = 3.0
    max_drivers: int = 10


class OfferCreated(DomainEvent):
    """Событие: предложение отправлено водителю."""
    
    event_type: Literal["offer.created"] = "offer.created"
    
    offer_id: str
    trip_id: str
    driver_id: int
    fare: float
    currency: str = "EUR"
    expires_at: str  # ISO datetime


class OfferAccepted(DomainEvent):
    """Событие: водитель принял предложение."""
    
    event_type: Literal["offer.accepted"] = "offer.accepted"
    
    offer_id: str
    trip_id: str
    driver_id: int
    eta_minutes: int | None = None


class OfferExpired(DomainEvent):
    """Событие: предложение истекло."""
    
    event_type: Literal["offer.expired"] = "offer.expired"
    
    offer_id: str
    trip_id: str
    driver_id: int


class DriverArrived(DomainEvent):
    """Событие: водитель прибыл к точке посадки."""
    
    event_type: Literal["driver.arrived"] = "driver.arrived"
    
    trip_id: str
    driver_id: int
    arrival_lat: float
    arrival_lon: float


class RideStarted(DomainEvent):
    """Событие: поездка началась."""
    
    event_type: Literal["ride.started"] = "ride.started"
    
    trip_id: str
    driver_id: int
    rider_id: int
    start_lat: float
    start_lon: float
