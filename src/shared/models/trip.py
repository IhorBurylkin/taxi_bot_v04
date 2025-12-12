# src/shared/models/trip.py
"""
DTO для поездок (trips/orders).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TripStatus(str, Enum):
    """Статус поездки."""
    PENDING = "pending"  # Заказ создан, ищем водителя
    MATCHING = "matching"  # Идёт поиск водителя
    ACCEPTED = "accepted"  # Водитель принял заказ
    DRIVER_ARRIVED = "driver_arrived"  # Водитель на месте
    IN_PROGRESS = "in_progress"  # Поездка началась
    COMPLETED = "completed"  # Поездка завершена
    CANCELLED = "cancelled"  # Отменено
    EXPIRED = "expired"  # Истёк таймаут поиска


class LocationDTO(BaseModel):
    """DTO для геолокации."""
    
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: str | None = None
    
    class Config:
        from_attributes = True


class FareDTO(BaseModel):
    """DTO для расчёта стоимости поездки."""
    
    base_fare: float = 0.0
    distance_fare: float = 0.0
    time_fare: float = 0.0
    pickup_fare: float = 0.0
    waiting_fare: float = 0.0
    surge_multiplier: float = 1.0
    total_fare: float = 0.0
    currency: str = "EUR"
    
    # В Stars (для Telegram Payments)
    total_stars: int | None = None


class TripDTO(BaseModel):
    """DTO поездки для межсервисного взаимодействия."""
    
    id: str  # UUID
    rider_id: int
    driver_id: int | None = None
    
    # Маршрут
    pickup: LocationDTO
    dropoff: LocationDTO
    
    # Параметры
    distance_km: float | None = None
    duration_minutes: int | None = None
    
    # Стоимость
    fare: FareDTO | None = None
    
    # Статус
    status: TripStatus = TripStatus.PENDING
    
    # Временные метки
    created_at: datetime | None = None
    accepted_at: datetime | None = None
    driver_arrived_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    
    # Рейтинги
    rider_rating: int | None = None
    driver_rating: int | None = None
    
    class Config:
        from_attributes = True


class TripCreateRequest(BaseModel):
    """Запрос на создание поездки."""
    
    rider_id: int
    pickup: LocationDTO
    dropoff: LocationDTO
    
    # Опционально: предрасчитанные данные
    distance_km: float | None = None
    duration_minutes: int | None = None


class TripSearchParams(BaseModel):
    """Параметры поиска поездок."""
    
    rider_id: int | None = None
    driver_id: int | None = None
    status: TripStatus | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


class NearbyDriverDTO(BaseModel):
    """DTO для ближайшего водителя."""
    
    driver_id: int
    distance_km: float
    eta_minutes: int | None = None
    rating: float = 5.0
    car_model: str | None = None
    car_color: str | None = None
    car_number: str | None = None
