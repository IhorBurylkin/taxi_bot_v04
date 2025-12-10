# src/core/users/models.py
"""
Модели данных пользователей.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.common.constants import UserRole, DriverStatus


class User(BaseModel):
    """Модель пользователя."""
    
    id: int = Field(..., description="Telegram ID пользователя")
    username: Optional[str] = Field(None, description="Username в Telegram")
    first_name: str = Field(..., description="Имя")
    last_name: Optional[str] = Field(None, description="Фамилия")
    phone: Optional[str] = Field(None, description="Номер телефона")
    language: str = Field("ru", description="Код языка")
    role: UserRole = Field(UserRole.PASSENGER, description="Роль пользователя")
    
    rating: float = Field(5.0, ge=1.0, le=5.0, description="Рейтинг")
    trips_count: int = Field(0, ge=0, description="Количество поездок")
    
    is_blocked: bool = Field(False, description="Заблокирован ли пользователь")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата регистрации")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Дата обновления")
    
    class Config:
        from_attributes = True
    
    @property
    def full_name(self) -> str:
        """Полное имя пользователя."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя (username или имя)."""
        if self.username:
            return f"@{self.username}"
        return self.full_name


class DriverProfile(BaseModel):
    """Профиль водителя (расширение User)."""
    
    user_id: int = Field(..., description="ID пользователя (FK)")
    
    # Информация о транспорте
    car_brand: str = Field(..., description="Марка автомобиля")
    car_model: str = Field(..., description="Модель автомобиля")
    car_color: str = Field(..., description="Цвет автомобиля")
    car_plate: str = Field(..., description="Номер автомобиля")
    car_year: Optional[int] = Field(None, description="Год выпуска")
    
    # Документы
    license_number: Optional[str] = Field(None, description="Номер водительского удостоверения")
    license_expiry: Optional[datetime] = Field(None, description="Срок действия прав")
    
    # Статус
    status: DriverStatus = Field(DriverStatus.OFFLINE, description="Статус водителя")
    is_verified: bool = Field(False, description="Верифицирован ли водитель")
    
    # Статистика
    completed_orders: int = Field(0, ge=0, description="Завершённых заказов")
    cancelled_orders: int = Field(0, ge=0, description="Отменённых заказов")
    total_earnings: float = Field(0.0, ge=0.0, description="Общий заработок")
    
    # Геолокация (последняя известная)
    last_latitude: Optional[float] = Field(None, description="Последняя широта")
    last_longitude: Optional[float] = Field(None, description="Последняя долгота")
    last_seen: Optional[datetime] = Field(None, description="Последняя активность")
    
    # Баланс
    balance_stars: int = Field(0, ge=0, description="Баланс в Stars")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания профиля")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Дата обновления")
    
    class Config:
        from_attributes = True
    
    @property
    def car_info(self) -> str:
        """Информация об автомобиле."""
        return f"{self.car_brand} {self.car_model} ({self.car_color}), {self.car_plate}"
    
    @property
    def is_online(self) -> bool:
        """Онлайн ли водитель."""
        return self.status == DriverStatus.ONLINE
    
    @property
    def is_available(self) -> bool:
        """Доступен ли водитель для заказов."""
        return self.status == DriverStatus.ONLINE and self.is_verified


class UserCreateDTO(BaseModel):
    """DTO для создания пользователя."""
    
    id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    language: str = "ru"


class DriverProfileCreateDTO(BaseModel):
    """DTO для создания профиля водителя."""
    
    user_id: int
    car_brand: str
    car_model: str
    car_color: str
    car_plate: str
    car_year: Optional[int] = None


class DriverLocationDTO(BaseModel):
    """DTO для обновления геолокации водителя."""
    
    driver_id: int
    latitude: float
    longitude: float
