# src/core/geo/service.py
"""
Geo-сервис для работы с Google Maps API.
Геокодирование, расчёт маршрутов, автокомплит адресов.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from src.common.constants import TypeMsg
from src.common.logger import log_info, log_error


@dataclass
class Location:
    """Геолокация."""
    latitude: float
    longitude: float
    address: str = ""


@dataclass
class RouteInfo:
    """Информация о маршруте."""
    distance_km: float
    duration_minutes: int
    polyline: str = ""  # Encoded polyline для отрисовки на карте


@dataclass
class AddressSuggestion:
    """Подсказка адреса."""
    place_id: str
    description: str
    main_text: str
    secondary_text: str


class GeoService:
    """
    Сервис для работы с геоданными через Google Maps API.
    
    Реализует:
    - Прямое геокодирование (адрес -> координаты)
    - Обратное геокодирование (координаты -> адрес)
    - Расчёт маршрута между точками
    - Автокомплит адресов
    """
    
    GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
    PLACES_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
    
    def __init__(self, api_key: str | None = None, language: str = "ru") -> None:
        """
        Инициализация сервиса.
        
        Args:
            api_key: API ключ Google Maps (берётся из конфига если None)
            language: Язык для ответов
        """
        if api_key is None:
            from src.config import settings
            api_key = settings.google_maps.GOOGLE_MAPS_API_KEY
            language = settings.google_maps.GEOCODING_LANGUAGE
        
        self._api_key = api_key
        self._language = language
        self._client = httpx.AsyncClient(timeout=10.0)
    
    async def close(self) -> None:
        """Закрывает HTTP клиент."""
        await self._client.aclose()
    
    async def geocode(self, address: str) -> Optional[Location]:
        """
        Прямое геокодирование: адрес -> координаты.
        
        Args:
            address: Адрес для геокодирования
            
        Returns:
            Локация с координатами или None
        """
        if not self._api_key:
            await log_error("Google Maps API key не настроен")
            return None
        
        try:
            response = await self._client.get(
                self.GEOCODING_URL,
                params={
                    "address": address,
                    "key": self._api_key,
                    "language": self._language,
                },
            )
            
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("results"):
                await log_info(
                    f"Геокодирование не дало результатов для: {address}",
                    type_msg=TypeMsg.WARNING,
                )
                return None
            
            result = data["results"][0]
            location = result["geometry"]["location"]
            
            return Location(
                latitude=location["lat"],
                longitude=location["lng"],
                address=result.get("formatted_address", address),
            )
        except Exception as e:
            await log_error(f"Ошибка геокодирования: {e}")
            return None
    
    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> Optional[str]:
        """
        Обратное геокодирование: координаты -> адрес.
        
        Args:
            latitude: Широта
            longitude: Долгота
            
        Returns:
            Адрес или None
        """
        if not self._api_key:
            await log_error("Google Maps API key не настроен")
            return None
        
        try:
            response = await self._client.get(
                self.GEOCODING_URL,
                params={
                    "latlng": f"{latitude},{longitude}",
                    "key": self._api_key,
                    "language": self._language,
                },
            )
            
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("results"):
                return None
            
            return data["results"][0].get("formatted_address")
        except Exception as e:
            await log_error(f"Ошибка обратного геокодирования: {e}")
            return None
    
    async def calculate_route(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> Optional[RouteInfo]:
        """
        Рассчитывает маршрут между двумя точками.
        
        Args:
            origin_lat: Широта начала
            origin_lng: Долгота начала
            dest_lat: Широта конца
            dest_lng: Долгота конца
            
        Returns:
            Информация о маршруте или None
        """
        if not self._api_key:
            await log_error("Google Maps API key не настроен")
            return None
        
        try:
            response = await self._client.get(
                self.DIRECTIONS_URL,
                params={
                    "origin": f"{origin_lat},{origin_lng}",
                    "destination": f"{dest_lat},{dest_lng}",
                    "mode": "driving",
                    "key": self._api_key,
                    "language": self._language,
                },
            )
            
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("routes"):
                await log_info(
                    f"Маршрут не найден: ({origin_lat},{origin_lng}) -> ({dest_lat},{dest_lng})",
                    type_msg=TypeMsg.WARNING,
                )
                return None
            
            route = data["routes"][0]
            leg = route["legs"][0]
            
            # Расстояние в метрах -> км
            distance_m = leg["distance"]["value"]
            distance_km = round(distance_m / 1000, 2)
            
            # Время в секундах -> минуты
            duration_s = leg["duration"]["value"]
            duration_min = round(duration_s / 60)
            
            # Encoded polyline
            polyline = route.get("overview_polyline", {}).get("points", "")
            
            return RouteInfo(
                distance_km=distance_km,
                duration_minutes=duration_min,
                polyline=polyline,
            )
        except Exception as e:
            await log_error(f"Ошибка расчёта маршрута: {e}")
            return None
    
    async def autocomplete(
        self,
        query: str,
        location: Optional[tuple[float, float]] = None,
        radius: int = 50000,
    ) -> list[AddressSuggestion]:
        """
        Автокомплит адресов.
        
        Args:
            query: Поисковый запрос
            location: Координаты для ограничения поиска (lat, lng)
            radius: Радиус поиска в метрах
            
        Returns:
            Список подсказок
        """
        if not self._api_key:
            await log_error("Google Maps API key не настроен")
            return []
        
        try:
            params = {
                "input": query,
                "key": self._api_key,
                "language": self._language,
                "types": "geocode|establishment",
            }
            
            if location:
                params["location"] = f"{location[0]},{location[1]}"
                params["radius"] = str(radius)
            
            response = await self._client.get(self.PLACES_URL, params=params)
            
            data = response.json()
            
            if data.get("status") not in ("OK", "ZERO_RESULTS"):
                await log_error(f"Places API error: {data.get('status')}")
                return []
            
            suggestions = []
            for prediction in data.get("predictions", []):
                structured = prediction.get("structured_formatting", {})
                suggestions.append(AddressSuggestion(
                    place_id=prediction["place_id"],
                    description=prediction["description"],
                    main_text=structured.get("main_text", prediction["description"]),
                    secondary_text=structured.get("secondary_text", ""),
                ))
            
            return suggestions
        except Exception as e:
            await log_error(f"Ошибка автокомплита: {e}")
            return []
    
    async def get_place_details(self, place_id: str) -> Optional[Location]:
        """
        Получает детали места по place_id.
        
        Args:
            place_id: ID места из Places API
            
        Returns:
            Локация с координатами или None
        """
        if not self._api_key:
            await log_error("Google Maps API key не настроен")
            return None
        
        try:
            response = await self._client.get(
                self.PLACE_DETAILS_URL,
                params={
                    "place_id": place_id,
                    "fields": "geometry,formatted_address",
                    "key": self._api_key,
                    "language": self._language,
                },
            )
            
            data = response.json()
            
            if data.get("status") != "OK":
                return None
            
            result = data.get("result", {})
            location = result.get("geometry", {}).get("location", {})
            
            if not location:
                return None
            
            return Location(
                latitude=location["lat"],
                longitude=location["lng"],
                address=result.get("formatted_address", ""),
            )
        except Exception as e:
            await log_error(f"Ошибка получения деталей места: {e}")
            return None
