from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from src.shared.models.enums import OrderStatus, PaymentMethod
from src.shared.models.location_dto import LocationDTO

class TripDTO(BaseModel):
    id: UUID
    passenger_id: int
    driver_id: Optional[int] = None
    
    pickup_location: LocationDTO
    destination_location: Optional[LocationDTO] = None
    
    stops: List[LocationDTO] = Field(default_factory=list)
    
    distance_km: Optional[float] = None
    duration_min: Optional[int] = None
    fare: Optional[float] = None
    currency: str = "EUR"
    
    status: OrderStatus = OrderStatus.DRAFT
    payment_method: PaymentMethod = PaymentMethod.CASH
    payment_status: str = "pending"
    
    created_at: datetime
    accepted_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    cancellation_reason: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class CreateTripRequest(BaseModel):
    passenger_id: int
    pickup_location: LocationDTO
    destination_location: Optional[LocationDTO] = None
    payment_method: PaymentMethod = PaymentMethod.CASH
    notes: Optional[str] = None

class CalculatePriceRequest(BaseModel):
    pickup_location: LocationDTO
    destination_location: LocationDTO
    stops: List[LocationDTO] = Field(default_factory=list)

class FareBreakdownDTO(BaseModel):
    distance_km: float
    base_cost: float
    pickup_distance_km: float
    pickup_cost: float
    night_fee: float
    waiting_minutes: int
    waiting_cost: float
    total_cost: float
    currency: str = "EUR"
