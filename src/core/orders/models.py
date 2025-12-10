# src/core/orders/models.py
"""
Модели данных заказов.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.common.constants import OrderStatus, PaymentMethod, PaymentStatus


class Order(BaseModel):
    """Модель заказа."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="UUID заказа")
    passenger_id: int = Field(..., description="ID пассажира")
    driver_id: Optional[int] = Field(None, description="ID водителя")
    
    # Локации
    pickup_address: str = Field(..., description="Адрес подачи")
    pickup_latitude: float = Field(..., description="Широта подачи")
    pickup_longitude: float = Field(..., description="Долгота подачи")
    
    destination_address: str = Field(..., description="Адрес назначения")
    destination_latitude: float = Field(..., description="Широта назначения")
    destination_longitude: float = Field(..., description="Долгота назначения")
    
    # Расчёты
    distance_km: float = Field(0.0, ge=0.0, description="Расстояние в км")
    duration_minutes: int = Field(0, ge=0, description="Время поездки в минутах")
    estimated_fare: float = Field(0.0, ge=0.0, description="Расчётная стоимость")
    final_fare: Optional[float] = Field(None, description="Итоговая стоимость")
    surge_multiplier: float = Field(1.0, ge=1.0, description="Коэффициент спроса")
    
    # Статус
    status: OrderStatus = Field(OrderStatus.CREATED, description="Статус заказа")
    
    # Оплата
    payment_method: PaymentMethod = Field(PaymentMethod.CASH, description="Способ оплаты")
    payment_status: PaymentStatus = Field(PaymentStatus.PENDING, description="Статус оплаты")
    
    # Временные метки
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Время создания")
    accepted_at: Optional[datetime] = Field(None, description="Время принятия")
    arrived_at: Optional[datetime] = Field(None, description="Время прибытия водителя")
    started_at: Optional[datetime] = Field(None, description="Время начала поездки")
    completed_at: Optional[datetime] = Field(None, description="Время завершения")
    cancelled_at: Optional[datetime] = Field(None, description="Время отмены")
    
    # Дополнительно
    passenger_comment: Optional[str] = Field(None, description="Комментарий пассажира")
    driver_rating: Optional[float] = Field(None, ge=1.0, le=5.0, description="Оценка водителя")
    passenger_rating: Optional[float] = Field(None, ge=1.0, le=5.0, description="Оценка пассажира")
    
    class Config:
        from_attributes = True
    
    @property
    def is_active(self) -> bool:
        """Активен ли заказ."""
        return self.status in (
            OrderStatus.CREATED,
            OrderStatus.SEARCHING,
            OrderStatus.ACCEPTED,
            OrderStatus.DRIVER_ARRIVED,
            OrderStatus.IN_PROGRESS,
        )
    
    @property
    def is_completed(self) -> bool:
        """Завершён ли заказ."""
        return self.status == OrderStatus.COMPLETED
    
    @property
    def is_cancelled(self) -> bool:
        """Отменён ли заказ."""
        return self.status == OrderStatus.CANCELLED
    
    @property
    def fare(self) -> float:
        """Возвращает итоговую или расчётную стоимость."""
        return self.final_fare if self.final_fare is not None else self.estimated_fare


class OrderCreateDTO(BaseModel):
    """DTO для создания заказа."""
    
    passenger_id: int
    
    pickup_address: str
    pickup_latitude: float
    pickup_longitude: float
    
    destination_address: str
    destination_latitude: float
    destination_longitude: float
    
    payment_method: PaymentMethod = PaymentMethod.CASH
    passenger_comment: Optional[str] = None


class OrderAcceptDTO(BaseModel):
    """DTO для принятия заказа водителем."""
    
    order_id: str
    driver_id: int


class FareCalculationDTO(BaseModel):
    """DTO с результатом расчёта стоимости."""
    
    distance_km: float
    duration_minutes: int
    base_fare: float
    distance_fare: float
    time_fare: float
    pickup_fare: float
    surge_multiplier: float
    total_fare: float
    currency: str
