import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime
from src.services.trip_service.service import TripService
from src.shared.models.trip_dto import CreateTripRequest, TripDTO
from src.shared.models.location_dto import LocationDTO
from src.shared.models.enums import OrderStatus

@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    trip_id = uuid4()
    repo.create_trip.return_value = trip_id
    repo.get_trip_by_id.return_value = {
        "id": trip_id,
        "passenger_id": 123,
        "pickup_lat": 10.0,
        "pickup_lon": 20.0,
        "pickup_address": "A",
        "status": "new",
        "created_at": datetime.utcnow()
    }
    return repo

@pytest.fixture
def mock_event_bus():
    return AsyncMock()

@pytest.mark.asyncio
async def test_create_trip(mock_repo, mock_event_bus):
    service = TripService(mock_repo, mock_event_bus)
    
    request = CreateTripRequest(
        passenger_id=123,
        pickup_location=LocationDTO(lat=10.0, lon=20.0, address="A"),
        destination_location=LocationDTO(lat=30.0, lon=40.0, address="B")
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total_price": 100.0, "distance_km": 5.0}
        mock_post.return_value = mock_response
        
        trip = await service.create_trip(request)
        
        assert trip is not None
        mock_repo.create_trip.assert_called_once()
        mock_event_bus.publish.assert_called_once()
        assert mock_event_bus.publish.call_args[0][0].event_type == "trip.created"

@pytest.mark.asyncio
async def test_update_status_valid(mock_repo, mock_event_bus):
    service = TripService(mock_repo, mock_event_bus)
    trip_id = uuid4()
    
    mock_repo.get_trip_by_id.return_value = {
        "id": trip_id,
        "passenger_id": 123,
        "pickup_lat": 10.0,
        "pickup_lon": 20.0,
        "status": "new",
        "created_at": datetime.utcnow()
    }
    
    await service.update_status(trip_id, OrderStatus.SEARCHING)
    
    mock_repo.update_trip_status.assert_called_with(trip_id, "searching")
    mock_event_bus.publish.assert_called_once()

@pytest.mark.asyncio
async def test_update_status_invalid(mock_repo, mock_event_bus):
    service = TripService(mock_repo, mock_event_bus)
    trip_id = uuid4()
    
    mock_repo.get_trip_by_id.return_value = {
        "id": trip_id,
        "passenger_id": 123,
        "pickup_lat": 10.0,
        "pickup_lon": 20.0,
        "status": "new",
        "created_at": datetime.utcnow()
    }
    
    with pytest.raises(ValueError):
        await service.update_status(trip_id, OrderStatus.COMPLETED) # Invalid transition
