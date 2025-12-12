from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from src.config import settings
from src.common.logger import log_info

_AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

_SESSION_LOCK = asyncio.Lock()
_SESSION: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    """Возвращает (и создает при необходимости) общий HTTP-клиент для Google Maps."""

    global _SESSION
    if _SESSION is not None and not _SESSION.closed:
        return _SESSION

    async with _SESSION_LOCK:
        if _SESSION is None or _SESSION.closed:
            timeout = aiohttp.ClientTimeout(total=6)
            _SESSION = aiohttp.ClientSession(timeout=timeout)
            await log_info(f"HTTP-сессия создана", type_msg="debug")

    return _SESSION


async def close_gmaps_session() -> None:
    """Аккуратно закрывает HTTP-сессию Google Maps."""

    global _SESSION
    if _SESSION is None:
        await log_info(f"HTTP-сессия отсутствует", type_msg="debug")
        return
    try:
        await _SESSION.close()
        await log_info(f"HTTP-сессия закрыта", type_msg="debug")
    except Exception as error:  # noqa: BLE001
        await log_info(
            f"Не удалось закрыть HTTP-сессию",
            type_msg="warning",
            reason=str(error),
        )
    finally:
        _SESSION = None


def _normalize_query(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    return normalized or None


async def fetch_city_suggestions(
    query: str,
    lang: str,
    *,
    session_token: Optional[str] = None,
    limit: int = 5,
    place_type: Optional[str] = "(cities)",
) -> List[Dict[str, str]]:
    """Запрашивает подсказки городов из Google Places Autocomplete."""

    normalized = _normalize_query(query)
    if not normalized:
        return []

    if not settings.google_maps.GOOGLE_MAPS_API_KEY:
        await log_info(f"API ключ не задан", type_msg="warning")
        return []

    params: Dict[str, Any] = {
        "input": normalized,
        "language": lang or "en",
        "key": settings.google_maps.GOOGLE_MAPS_API_KEY,
    }
    if place_type:
        params["types"] = place_type
    if session_token:
        params["sessiontoken"] = session_token

    try:
        session = await _get_session()
        async with session.get(_AUTOCOMPLETE_URL, params=params) as response:
            payload = await response.json()
    except Exception as error:  # noqa: BLE001
        await log_info(
            f"Запрос автодополнения завершился ошибкой",
            type_msg="error",
            reason=str(error),
        )
        return []

    status = payload.get("status")
    if status not in {"OK", "ZERO_RESULTS"}:
        await log_info(
            f"Получен неожиданный статус",
            type_msg="warning",
            extra={"status": status, "query": normalized},
        )
        return []

    predictions = payload.get("predictions") or []
    suggestions: List[Dict[str, str]] = []
    for item in predictions[:limit]:
        description = item.get("description")
        place_id = item.get("place_id")
        structured = item.get("structured_formatting") or {}
        if not description or not place_id:
            continue
        suggestions.append(
            {
                "description": description,
                "place_id": place_id,
                "main_text": structured.get("main_text", description),
                "secondary_text": structured.get("secondary_text", ""),
            }
        )

    await log_info(
        f"Получено подсказок",
        type_msg="info",
        extra={"count": len(suggestions), "query": normalized},
    )
    return suggestions


def _extract_component(components: List[Dict[str, Any]], component_type: str, *, short: bool = False) -> Optional[str]:
    for component in components:
        types = component.get("types") or []
        if component_type in types:
            key = "short_name" if short else "long_name"
            value = component.get(key)
            if value:
                return value
    return None


async def fetch_place_details(
    place_id: str,
    lang: str,
    *,
    session_token: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Возвращает страну, регион и город для выбранного place_id."""

    if not place_id:
        return {}

    if not settings.google_maps.GOOGLE_MAPS_API_KEY:
        await log_info(f"API ключ не задан", type_msg="warning")
        return {}

    params: Dict[str, Any] = {
        "place_id": place_id,
        "language": lang or "en",
        "fields": "address_component,formatted_address,name,geometry",
        "key": settings.google_maps.GOOGLE_MAPS_API_KEY,
    }
    if session_token:
        params["sessiontoken"] = session_token

    try:
        session = await _get_session()
        async with session.get(_DETAILS_URL, params=params) as response:
            payload = await response.json()
    except Exception as error:  # noqa: BLE001
        await log_info(
            f"Запрос деталей завершился ошибкой",
            type_msg="error",
            reason=str(error),
        )
        return {}

    status = payload.get("status")
    if status != "OK":
        await log_info(
            f"Неожиданный статус",
            type_msg="warning",
            extra={"status": status, "place_id": place_id},
        )
        return {}

    result = payload.get("result") or {}
    components = result.get("address_components") or []
    country = _extract_component(components, "country")
    country_code = _extract_component(components, "country", short=True)
    region = _extract_component(components, "administrative_area_level_1")
    city = _extract_component(components, "locality") or _extract_component(components, "postal_town")
    if not city:
        city = _extract_component(components, "administrative_area_level_2")

    details = {
        "country": country,
        "country_code": country_code,
        "region": region,
        "city": city or result.get("name"),
        "formatted_address": result.get("formatted_address"),
        "place_id": place_id,
        "geometry": result.get("geometry"),
    }

    await log_info(
        f"Детали места получены",
        type_msg="info",
        extra={"place_id": place_id, "city": details.get("city")},
    )
    return details


async def fetch_route_info(
    origin: str,
    destination: str,
    lang: str,
    waypoints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Рассчитывает маршрут между двумя точками через Google Directions API.
    Возвращает словарь с дистанцией (км), длительностью и полилайном.
    """
    if not origin or not destination:
        return {}

    if not settings.google_maps.GOOGLE_MAPS_API_KEY:
        await log_info(f"API ключ не задан", type_msg="warning")
        return {}

    params = {
        "origin": origin,
        "destination": destination,
        "language": lang or "en",
        "key": settings.google_maps.GOOGLE_MAPS_API_KEY,
        "mode": "driving"
    }
    
    if waypoints:
        params["waypoints"] = "|".join(waypoints)

    try:
        session = await _get_session()
        async with session.get(_DIRECTIONS_URL, params=params) as response:
            payload = await response.json()
    except Exception as error:
        await log_info(
            f"Запрос маршрута завершился ошибкой",
            type_msg="error",
            reason=str(error),
        )
        return {}

    status = payload.get("status")
    if status != "OK":
        await log_info(
            f"Неожиданный статус маршрута",
            type_msg="warning",
            extra={"status": status, "origin": origin, "dest": destination},
        )
        return {}

    routes = payload.get("routes", [])
    if not routes:
        return {}

    # Берем первый маршрут
    route = routes[0]
    legs = route.get("legs", [])
    if not legs:
        return {}

    distance_m = 0
    duration_s = 0
    
    for leg in legs:
        distance_m += leg.get("distance", {}).get("value", 0)
        duration_s += leg.get("duration", {}).get("value", 0)
    
    # Для start/end address берем начало первого лега и конец последнего
    start_address = legs[0].get("start_address")
    end_address = legs[-1].get("end_address")
    
    # Обзорная полилиния для отображения на карте
    polyline = route.get("overview_polyline", {}).get("points", "")

    return {
        "distance_km": round(distance_m / 1000, 2),
        "duration_min": round(duration_s / 60),
        "polyline": polyline,
        "start_address": start_address,
        "end_address": end_address,
    }


async def reverse_geocode(
    lat: float,
    lng: float,
    lang: str,
) -> Dict[str, Optional[str]]:
    """
    Выполняет обратное геокодирование: получает адрес по координатам.
    """
    if not settings.google_maps.GOOGLE_MAPS_API_KEY:
        await log_info("API ключ не задан", type_msg="warning")
        return {}

    params: Dict[str, Any] = {
        "latlng": f"{lat},{lng}",
        "language": lang or "en",
        "key": settings.google_maps.GOOGLE_MAPS_API_KEY,
    }

    try:
        session = await _get_session()
        async with session.get(_GEOCODE_URL, params=params) as response:
            payload = await response.json()
    except Exception as error:
        await log_info(
            f"Запрос reverse geocode завершился ошибкой",
            type_msg="error",
            reason=str(error),
        )
        return {}

    status = payload.get("status")
    if status != "OK":
        await log_info(
            f"Неожиданный статус reverse geocode",
            type_msg="warning",
            extra={"status": status, "lat": lat, "lng": lng},
        )
        return {}

    results = payload.get("results", [])
    if not results:
        return {}

    # Берём первый (наиболее точный) результат
    result = results[0]
    components = result.get("address_components") or []
    
    country = _extract_component(components, "country")
    country_code = _extract_component(components, "country", short=True)
    region = _extract_component(components, "administrative_area_level_1")
    city = _extract_component(components, "locality") or _extract_component(components, "postal_town")
    if not city:
        city = _extract_component(components, "administrative_area_level_2")

    details = {
        "country": country,
        "country_code": country_code,
        "region": region,
        "city": city,
        "formatted_address": result.get("formatted_address"),
        "place_id": result.get("place_id"),
        "geometry": {
            "location": {"lat": lat, "lng": lng}
        },
    }

    await log_info(
        f"Reverse geocode выполнен",
        type_msg="debug",
        extra={"lat": lat, "lng": lng, "address": details.get("formatted_address")},
    )
    return details


async def search_cities(
    query: str,
    lang: str,
    *,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Поиск городов по запросу с получением координат.
    """
    # Получаем подсказки городов
    suggestions = await fetch_city_suggestions(query, lang, limit=limit)
    
    if not suggestions:
        return []
    
    results: List[Dict[str, Any]] = []
    
    for suggestion in suggestions:
        place_id = suggestion.get("place_id")
        if not place_id:
            continue
            
        # Получаем детали места для получения координат
        details = await fetch_place_details(place_id, lang)
        if not details:
            continue
            
        geometry = details.get("geometry") or {}
        location = geometry.get("location") or {}
        
        city_info = {
            "city": details.get("city") or suggestion.get("main_text", ""),
            "description": suggestion.get("description", ""),
            "lat": location.get("lat"),
            "lng": location.get("lng"),
            "country": details.get("country"),
            "country_code": details.get("country_code"),
            "region": details.get("region"),
            "place_id": place_id,
        }
        results.append(city_info)
    
    await log_info(
        f"Поиск городов выполнен",
        type_msg="debug",
        extra={"query": query, "count": len(results)},
    )
    return results
