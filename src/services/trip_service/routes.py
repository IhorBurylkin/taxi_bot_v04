from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from src.services.trip_service.service import TripService
from src.services.trip_service.dependencies import get_trip_service
from src.shared.models.trip_dto import CreateTripRequest, TripDTO
from src.shared.models.enums import OrderStatus

router = APIRouter(prefix="/trips", tags=["Trips"])

class UpdateStatusRequest(BaseModel):
    status: OrderStatus
    driver_id: Optional[int] = None

@router.post("/", response_model=TripDTO)
async def create_trip(
    request: CreateTripRequest,
    service: TripService = Depends(get_trip_service)
):
    return await service.create_trip(request)

@router.get("/{trip_id}", response_model=TripDTO)
async def get_trip(
    trip_id: UUID,
    service: TripService = Depends(get_trip_service)
):
    trip = await service.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip

@router.patch("/{trip_id}/status", response_model=TripDTO)
async def update_trip_status(
    trip_id: UUID,
    request: UpdateStatusRequest,
    service: TripService = Depends(get_trip_service)
):
    try:
        return await service.update_status(trip_id, request.status, request.driver_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=dict)
async def get_all_trips(
    page: int = 1,
    size: int = 20,
    service: TripService = Depends(get_trip_service)
):
    return await service.get_all_trips(page, size)
