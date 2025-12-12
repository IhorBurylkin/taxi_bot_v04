# src/shared/models/user.py
"""
DTO для пользователей и водителей.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """Роль пользователя."""
    RIDER = "rider"
    DRIVER = "driver"
    ADMIN = "admin"


class DriverStatus(str, Enum):
    """Статус водителя."""
    OFFLINE = "offline"
    ONLINE = "online"
    BUSY = "busy"
    ON_TRIP = "on_trip"


class UserDTO(BaseModel):
    """DTO пользователя для межсервисного взаимодействия."""
    
    id: int
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    language_code: str = "en"
    role: UserRole = UserRole.RIDER
    is_active: bool = True
    is_blocked: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    class Config:
        from_attributes = True


class DriverDTO(BaseModel):
    """DTO водителя с дополнительной информацией."""
    
    user_id: int
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    
    # Статус водителя
    status: DriverStatus = DriverStatus.OFFLINE
    is_verified: bool = False
    is_working: bool = False
    
    # Геолокация
    current_lat: float | None = None
    current_lon: float | None = None
    last_location_update: datetime | None = None
    
    # Транспорт
    car_model: str | None = None
    car_color: str | None = None
    car_number: str | None = None
    
    # Рейтинг
    rating: float = 5.0
    total_trips: int = 0
    
    # Баланс Stars
    balance_stars: int = 0
    
    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    """Запрос на создание пользователя."""
    
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    language_code: str = "en"
    role: UserRole = UserRole.RIDER


class DriverCreateRequest(BaseModel):
    """Запрос на создание/регистрацию водителя."""
    
    user_id: int
    car_model: str | None = None
    car_color: str | None = None
    car_number: str | None = None


class DriverLocationUpdate(BaseModel):
    """Обновление геолокации водителя."""
    
    driver_id: int
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    heading: float | None = Field(default=None, ge=0, le=360)
    speed: float | None = Field(default=None, ge=0)  # км/ч
    accuracy: float | None = Field(default=None, ge=0)  # метры
