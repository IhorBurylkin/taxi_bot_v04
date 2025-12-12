import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.geo.service import GeoService, Location, RouteInfo, AddressSuggestion

@pytest.fixture
def mock_settings():
    with patch("src.core.geo.service.settings", create=True) as mock:
        mock.google_maps.GOOGLE_MAPS_API_KEY = "test_key"
        mock.google_maps.GEOCODING_LANGUAGE = "ru"
        yield mock

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        mock_cls.return_value = client
        yield client

@pytest.fixture
def geo_service(mock_settings, mock_httpx_client):
    service = GeoService()
    return service

# --- Geocode Tests ---

@pytest.mark.asyncio
async def test_geocode_success(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{
            "geometry": {"location": {"lat": 55.75, "lng": 37.61}},
            "formatted_address": "Moscow, Russia"
        }]
    }
    mock_httpx_client.get.return_value = mock_response
    
    result = await geo_service.geocode("Moscow")
    
    assert isinstance(result, Location)
    assert result.latitude == 55.75
    assert result.longitude == 37.61
    assert result.address == "Moscow, Russia"

@pytest.mark.asyncio
async def test_geocode_no_results(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ZERO_RESULTS", "results": []}
    mock_httpx_client.get.return_value = mock_response
    
    result = await geo_service.geocode("Unknown Place")
    assert result is None

@pytest.mark.asyncio
async def test_geocode_error(geo_service, mock_httpx_client):
    mock_httpx_client.get.side_effect = Exception("Network Error")
    
    result = await geo_service.geocode("Moscow")
    assert result is None

@pytest.mark.asyncio
async def test_geocode_no_api_key(mock_httpx_client):
    with patch("src.config.settings") as mock_settings:
        mock_settings.google_maps.GOOGLE_MAPS_API_KEY = None
        service = GeoService(api_key=None)
        result = await service.geocode("Moscow")
        assert result is None

# --- Reverse Geocode Tests ---

@pytest.mark.asyncio
async def test_reverse_geocode_success(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{"formatted_address": "Moscow, Russia"}]
    }
    mock_httpx_client.get.return_value = mock_response
    
    result = await geo_service.reverse_geocode(55.75, 37.61)
    assert result == "Moscow, Russia"

@pytest.mark.asyncio
async def test_reverse_geocode_no_results(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ZERO_RESULTS"}
    mock_httpx_client.get.return_value = mock_response
    
    result = await geo_service.reverse_geocode(0, 0)
    assert result is None

# --- Calculate Route Tests ---

@pytest.mark.asyncio
async def test_calculate_route_success(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "routes": [{
            "legs": [{
                "distance": {"value": 5000},
                "duration": {"value": 600}
            }],
            "overview_polyline": {"points": "encoded_polyline"}
        }]
    }
    mock_httpx_client.get.return_value = mock_response
    
    result = await geo_service.calculate_route(55.75, 37.61, 55.80, 37.70)
    
    assert isinstance(result, RouteInfo)
    assert result.distance_km == 5.0
    assert result.duration_minutes == 10
    assert result.polyline == "encoded_polyline"

@pytest.mark.asyncio
async def test_calculate_route_no_routes(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ZERO_RESULTS"}
    mock_httpx_client.get.return_value = mock_response
    
    result = await geo_service.calculate_route(55.75, 37.61, 55.80, 37.70)
    assert result is None

# --- Autocomplete Tests ---

@pytest.mark.asyncio
async def test_autocomplete_success(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "predictions": [{
            "place_id": "place123",
            "description": "Moscow, Russia",
            "structured_formatting": {
                "main_text": "Moscow",
                "secondary_text": "Russia"
            }
        }]
    }
    mock_httpx_client.get.return_value = mock_response
    
    results = await geo_service.autocomplete("Mosc")
    
    assert len(results) == 1
    assert isinstance(results[0], AddressSuggestion)
    assert results[0].place_id == "place123"

@pytest.mark.asyncio
async def test_autocomplete_error(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "REQUEST_DENIED"}
    mock_httpx_client.get.return_value = mock_response
    
    results = await geo_service.autocomplete("Mosc")
    assert results == []

# --- Get Place Details Tests ---

@pytest.mark.asyncio
async def test_get_place_details_success(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "result": {
            "geometry": {"location": {"lat": 55.75, "lng": 37.61}},
            "formatted_address": "Moscow, Russia"
        }
    }
    mock_httpx_client.get.return_value = mock_response
    
    result = await geo_service.get_place_details("place123")
    
    assert isinstance(result, Location)
    assert result.latitude == 55.75
    assert result.longitude == 37.61

@pytest.mark.asyncio
async def test_get_place_details_fail(geo_service, mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "INVALID_REQUEST"}
    mock_httpx_client.get.return_value = mock_response
    
    result = await geo_service.get_place_details("place123")
    assert result is None

@pytest.mark.asyncio
async def test_close(geo_service, mock_httpx_client):
    await geo_service.close()
    mock_httpx_client.aclose.assert_called_once()
