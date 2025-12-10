# tests/core/test_geo_service.py
"""
Тесты для Geo-сервиса.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

from src.core.geo.service import (
    Location,
    RouteInfo,
    AddressSuggestion,
    GeoService,
)


class TestLocation:
    """Тесты для dataclass Location."""
    
    def test_create_location(self) -> None:
        """Проверяет создание локации."""
        loc = Location(
            latitude=50.4501,
            longitude=30.5234,
            address="Київ, Україна",
        )
        
        assert loc.latitude == 50.4501
        assert loc.longitude == 30.5234
        assert loc.address == "Київ, Україна"
    
    def test_location_default_address(self) -> None:
        """Проверяет значение адреса по умолчанию."""
        loc = Location(latitude=50.45, longitude=30.52)
        assert loc.address == ""


class TestRouteInfo:
    """Тесты для dataclass RouteInfo."""
    
    def test_create_route_info(self) -> None:
        """Проверяет создание информации о маршруте."""
        route = RouteInfo(
            distance_km=15.5,
            duration_minutes=25,
            polyline="encoded_polyline_string",
        )
        
        assert route.distance_km == 15.5
        assert route.duration_minutes == 25
        assert route.polyline == "encoded_polyline_string"
    
    def test_route_info_default_polyline(self) -> None:
        """Проверяет значение polyline по умолчанию."""
        route = RouteInfo(distance_km=10.0, duration_minutes=15)
        assert route.polyline == ""


class TestAddressSuggestion:
    """Тесты для dataclass AddressSuggestion."""
    
    def test_create_suggestion(self) -> None:
        """Проверяет создание подсказки адреса."""
        suggestion = AddressSuggestion(
            place_id="ChIJBUVa4U7P1EARZcj_5hJVtgQ",
            description="Крещатик, Киев, Украина",
            main_text="Крещатик",
            secondary_text="Киев, Украина",
        )
        
        assert suggestion.place_id == "ChIJBUVa4U7P1EARZcj_5hJVtgQ"
        assert suggestion.description == "Крещатик, Киев, Украина"
        assert suggestion.main_text == "Крещатик"
        assert suggestion.secondary_text == "Киев, Украина"


class TestGeoService:
    """Тесты для GeoService."""
    
    @pytest.fixture
    def geo_service(self) -> GeoService:
        """Создаёт сервис с тестовым API ключом."""
        return GeoService(api_key="test_api_key", language="ru")
    
    def test_init_with_api_key(self, geo_service: GeoService) -> None:
        """Проверяет инициализацию с API ключом."""
        assert geo_service._api_key == "test_api_key"
        assert geo_service._language == "ru"
    
    def test_init_without_api_key(self) -> None:
        """Проверяет инициализацию без API ключа (из конфига)."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.google_maps.GOOGLE_MAPS_API_KEY = "config_api_key"
            mock_settings.google_maps.GEOCODING_LANGUAGE = "uk"
            
            service = GeoService()
            
            assert service._api_key == "config_api_key"
            assert service._language == "uk"
    
    @pytest.mark.asyncio
    async def test_close(self, geo_service: GeoService) -> None:
        """Проверяет закрытие HTTP клиента."""
        await geo_service.close()
        # Не должно быть исключений
    
    @pytest.mark.asyncio
    async def test_geocode_success(self, geo_service: GeoService) -> None:
        """Проверяет успешное геокодирование."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{
                "geometry": {
                    "location": {"lat": 50.4501, "lng": 30.5234}
                },
                "formatted_address": "Крещатик, Киев, Украина",
            }],
        }
        
        with patch.object(
            geo_service._client, 'get',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await geo_service.geocode("Крещатик, Киев")
        
        assert result is not None
        assert result.latitude == 50.4501
        assert result.longitude == 30.5234
        assert result.address == "Крещатик, Киев, Украина"
    
    @pytest.mark.asyncio
    async def test_geocode_no_results(self, geo_service: GeoService) -> None:
        """Проверяет геокодирование без результатов."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ZERO_RESULTS",
            "results": [],
        }
        
        with patch.object(
            geo_service._client, 'get',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await geo_service.geocode("несуществующий адрес xyzabc123")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_geocode_no_api_key(self) -> None:
        """Проверяет геокодирование без API ключа."""
        service = GeoService(api_key="", language="ru")
        
        result = await service.geocode("Крещатик, Киев")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_geocode_exception(self, geo_service: GeoService) -> None:
        """Проверяет обработку исключений при геокодировании."""
        with patch.object(
            geo_service._client, 'get',
            new_callable=AsyncMock,
            side_effect=Exception("Network error")
        ):
            result = await geo_service.geocode("Крещатик, Киев")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_reverse_geocode_success(self, geo_service: GeoService) -> None:
        """Проверяет успешное обратное геокодирование."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{
                "formatted_address": "Крещатик, 1, Киев, Украина",
            }],
        }
        
        with patch.object(
            geo_service._client, 'get',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await geo_service.reverse_geocode(50.4501, 30.5234)
        
        assert result == "Крещатик, 1, Киев, Украина"
    
    @pytest.mark.asyncio
    async def test_reverse_geocode_no_results(self, geo_service: GeoService) -> None:
        """Проверяет обратное геокодирование без результатов."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ZERO_RESULTS",
            "results": [],
        }
        
        with patch.object(
            geo_service._client, 'get',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await geo_service.reverse_geocode(0.0, 0.0)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_reverse_geocode_no_api_key(self) -> None:
        """Проверяет обратное геокодирование без API ключа."""
        service = GeoService(api_key="", language="ru")
        
        result = await service.reverse_geocode(50.45, 30.52)
        
        assert result is None
