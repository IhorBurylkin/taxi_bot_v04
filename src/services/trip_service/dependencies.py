from fastapi import Request
from src.services.trip_service.repository import TripRepository
from src.services.trip_service.service import TripService
from src.infra.database import DatabaseManager
from src.infra.event_bus import get_event_bus

def get_trip_repository(request: Request) -> TripRepository:
    return TripRepository(DatabaseManager())

def get_trip_service(request: Request) -> TripService:
    repository = get_trip_repository(request)
    event_bus = get_event_bus()
    return TripService(repository, event_bus)
