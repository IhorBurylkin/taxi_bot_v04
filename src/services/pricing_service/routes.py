from fastapi import APIRouter, Depends
from src.services.pricing_service.service import PricingService
from src.services.pricing_service.dependencies import get_pricing_service
from src.shared.models.trip_dto import CalculatePriceRequest, FareBreakdownDTO
from src.services.utils.geo_utils import calculate_distance

router = APIRouter(prefix="/pricing", tags=["pricing"])

@router.post("/calculate", response_model=FareBreakdownDTO)
async def calculate_price(
    request: CalculatePriceRequest,
    service: PricingService = Depends(get_pricing_service)
):
    # 1. Рассчитываем дистанцию маршрута
    # TODO: В будущем здесь должен быть вызов Google Maps API / OSRM для точного маршрута
    # Пока считаем по прямой (haversine)
    distance_km = calculate_distance(
        request.pickup_location.lat, request.pickup_location.lon,
        request.destination_location.lat, request.destination_location.lon
    )
    
    # Учитываем остановки (если есть)
    if request.stops:
        current_lat, current_lon = request.pickup_location.lat, request.pickup_location.lon
        distance_km = 0.0
        
        # Pickup -> Stop 1
        distance_km += calculate_distance(
            current_lat, current_lon,
            request.stops[0].lat, request.stops[0].lon
        )
        current_lat, current_lon = request.stops[0].lat, request.stops[0].lon
        
        # Stop 1 -> Stop 2 ...
        for i in range(1, len(request.stops)):
            distance_km += calculate_distance(
                current_lat, current_lon,
                request.stops[i].lat, request.stops[i].lon
            )
            current_lat, current_lon = request.stops[i].lat, request.stops[i].lon
            
        # Last Stop -> Destination
        distance_km += calculate_distance(
            current_lat, current_lon,
            request.destination_location.lat, request.destination_location.lon
        )
    
    # 2. Вызываем сервис расчета
    # TODO: Определить is_night на основе времени сервера или таймзоны города
    return service.calculate_price(
        distance_km=distance_km,
        pickup_distance_km=0.0, # Пока 0, так как водитель еще не назначен
        waiting_minutes=0,
        is_night=False,
        stops_count=len(request.stops)
    )
