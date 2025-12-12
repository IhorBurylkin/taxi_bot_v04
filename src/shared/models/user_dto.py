from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from src.shared.models.enums import UserRole

class UserDTO(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    language: str = "en"
    role: UserRole = UserRole.PASSENGER
    is_active: bool = True
    is_blocked: bool = False
    city_lat: Optional[float] = None
    city_lng: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CreateUserRequest(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language: str = "en"
    role: UserRole = UserRole.PASSENGER

class UpdateUserStatusRequest(BaseModel):
    role: UserRole

class DriverProfileDTO(BaseModel):
    user_id: int
    car_brand: Optional[str] = None
    car_model: Optional[str] = None
    car_color: Optional[str] = None
    car_plate: Optional[str] = None
    is_verified: bool = False
    is_working: bool = False
    rating: float = 5.00
    total_trips: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CreateDriverProfileRequest(BaseModel):
    car_brand: str
    car_model: str
    car_color: str
    car_plate: str
