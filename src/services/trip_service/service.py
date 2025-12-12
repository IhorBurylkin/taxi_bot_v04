import httpx
from uuid import UUID
from typing import Optional
from src.services.trip_service.repository import TripRepository
from src.shared.events.trip_events import TripCreated, TripStatusChanged
from src.infra.event_bus import EventBus
from src.config import settings
from src.shared.models.trip_dto import CreateTripRequest, TripDTO
from src.shared.models.location_dto import LocationDTO
from src.shared.models.enums import OrderStatus
from src.services.trip_service.state_machine import TripStateMachine
from src.common.logger import log_info

class TripService:
    def __init__(self, repository: TripRepository, event_bus: EventBus):
        self.repository = repository
        self.event_bus = event_bus
        self.pricing_url = f"http://localhost:{settings.deployment.PRICING_SERVICE_PORT}/api/v1/pricing/calculate"

    async def update_status(self, trip_id: UUID, new_status: OrderStatus, driver_id: Optional[int] = None) -> TripDTO:
        trip = await self.get_trip(trip_id)
        if not trip:
            raise ValueError("Trip not found")
            
        if not TripStateMachine.can_transition(trip.status, new_status):
            raise ValueError(f"Invalid transition from {trip.status} to {new_status}")
            
        await self.repository.update_trip_status(trip_id, new_status.value)
        
        if driver_id and new_status == OrderStatus.ON_WAY:
             await self.repository.update_trip_driver(trip_id, driver_id)
             
        # Publish event
        event = TripStatusChanged(
            trip_id=str(trip_id),
            old_status=trip.status.value,
            new_status=new_status.value,
            driver_id=driver_id
        )
        await self.event_bus.publish(event)
        
        return await self.get_trip(trip_id)

    async def create_trip(self, request: CreateTripRequest) -> TripDTO:
        # 1. Calculate Price
        price_data = {}
        try:
            async with httpx.AsyncClient() as client:
                pricing_payload = {
                    "pickup_location": request.pickup_location.model_dump(),
                    "destination_location": request.destination_location.model_dump() if request.destination_location else None,
                    "stops": [] 
                }
                
                response = await client.post(self.pricing_url, json=pricing_payload)
                if response.status_code == 200:
                    price_data = response.json()
                else:
                    await log_info(f"Pricing service error: {response.text}", type_msg="error")
        except Exception as e:
             await log_info(f"Failed to contact pricing service: {e}", type_msg="error")

        # 2. Create in DB
        trip_data = request.model_dump()
        
        trip_data['pickup_lat'] = request.pickup_location.lat
        trip_data['pickup_lon'] = request.pickup_location.lon
        trip_data['pickup_address'] = request.pickup_location.address
        
        if request.destination_location:
            trip_data['destination_lat'] = request.destination_location.lat
            trip_data['destination_lon'] = request.destination_location.lon
            trip_data['destination_address'] = request.destination_location.address
            
        trip_data['fare'] = price_data.get('total_price', 0.0)
        trip_data['distance_km'] = price_data.get('distance_km', 0.0)
        trip_data['status'] = OrderStatus.NEW.value
        
        trip_id = await self.repository.create_trip(trip_data)
        
        # 3. Publish Event
        event = TripCreated(
            trip_id=str(trip_id),
            rider_id=request.passenger_id,
            pickup_lat=request.pickup_location.lat,
            pickup_lon=request.pickup_location.lon,
            pickup_address=request.pickup_location.address,
            dropoff_lat=request.destination_location.lat if request.destination_location else 0.0,
            dropoff_lon=request.destination_location.lon if request.destination_location else 0.0,
            dropoff_address=request.destination_location.address if request.destination_location else None,
            distance_km=trip_data['distance_km'],
            estimated_fare=trip_data['fare']
        )
        await self.event_bus.publish(event)
        
        # Return DTO
        created_trip = await self.repository.get_trip_by_id(trip_id)
        return self._map_db_to_dto(created_trip)

    async def get_trip(self, trip_id: UUID) -> Optional[TripDTO]:
        data = await self.repository.get_trip_by_id(trip_id)
        if not data:
            return None
        return self._map_db_to_dto(data)

    async def get_all_trips(self, page: int, size: int) -> dict:
        """Retrieves all trips with pagination."""
        offset = (page - 1) * size
        trips_data = await self.repository.get_all_trips(limit=size, offset=offset)
        total = await self.repository.count_trips()
        
        items = [self._map_db_to_dto(trip) for trip in trips_data]
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size
        }

    def _map_db_to_dto(self, data: dict) -> TripDTO:
        pickup = LocationDTO(
            lat=data['pickup_lat'],
            lon=data['pickup_lon'],
            address=data.get('pickup_address')
        )
        
        destination = None
        if data.get('destination_lat'):
            destination = LocationDTO(
                lat=data['destination_lat'],
                lon=data['destination_lon'],
                address=data.get('destination_address')
            )
            
        return TripDTO(
            id=data['id'],
            passenger_id=data['passenger_id'],
            driver_id=data.get('driver_id'),
            pickup_location=pickup,
            destination_location=destination,
            distance_km=data.get('distance_km'),
            duration_min=data.get('duration_min'),
            fare=data.get('fare'),
            currency=data.get('currency', 'EUR'),
            status=data.get('status'),
            payment_method=data.get('payment_method', 'cash'),
            payment_status=data.get('payment_status', 'pending'),
            created_at=data['created_at'],
            accepted_at=data.get('accepted_at'),
            arrived_at=data.get('arrived_at'),
            started_at=data.get('started_at'),
            completed_at=data.get('completed_at'),
            cancelled_at=data.get('cancelled_at'),
            cancellation_reason=data.get('cancellation_reason'),
            notes=data.get('notes')
        )
