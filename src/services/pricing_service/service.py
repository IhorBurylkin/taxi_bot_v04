from dataclasses import dataclass
import math
from src.shared.models.trip_dto import FareBreakdownDTO
from src.config import settings

class PricingService:
    def calculate_price(
        self, 
        distance_km: float, 
        pickup_distance_km: float = 0.0,
        waiting_minutes: int = 0,
        is_night: bool = False,
        stops_count: int = 0
    ) -> FareBreakdownDTO:
        """
        Расчет стоимости поездки.
        
        Логика:
        - Базовая стоимость: BASE_FARE_FIRST_5KM за первые 5 км + FARE_PER_KM_AFTER_5 за каждый км свыше 5
        - Подача: PICKUP_FARE_PER_KM €/км при дистанции водителя > PICKUP_FREE_DISTANCE_KM
        - Ночной тариф: +NIGHT_FEE €
        - Ожидание: WAITING_FREE_MINUTES мин бесплатно, затем WAITING_FARE_PER_MINUTE €/мин
        """
        
        # 1. Базовая стоимость (дистанция)
        base_cost = settings.fares.BASE_FARE_FIRST_5KM
        if distance_km > 5.0:
            extra_km = distance_km - 5.0
            base_cost += extra_km * settings.fares.FARE_PER_KM_AFTER_5
            
        # 2. Стоимость подачи
        pickup_cost = 0.0
        if pickup_distance_km > settings.fares.PICKUP_FREE_DISTANCE_KM:
            chargeable_pickup_km = pickup_distance_km - settings.fares.PICKUP_FREE_DISTANCE_KM
            pickup_cost = chargeable_pickup_km * settings.fares.PICKUP_FARE_PER_KM
            
        # 3. Ночной тариф
        night_fee = settings.fares.NIGHT_FEE if is_night else 0.0
        
        # 4. Ожидание (начальное)
        waiting_cost = 0.0
        chargeable_waiting_minutes = max(0, waiting_minutes - settings.fares.WAITING_FREE_MINUTES)
        if chargeable_waiting_minutes > 0:
            waiting_cost = chargeable_waiting_minutes * settings.fares.WAITING_FARE_PER_MINUTE
            
        # 5. Итого
        total_cost = base_cost + pickup_cost + night_fee + waiting_cost
        
        # Округление до целого евро (если >= 0.5)
        if total_cost - int(total_cost) >= 0.5:
            total_cost = float(math.ceil(total_cost))
        else:
            total_cost = float(int(total_cost))
            
        return FareBreakdownDTO(
            distance_km=distance_km,
            base_cost=round(base_cost, 2),
            pickup_distance_km=pickup_distance_km,
            pickup_cost=round(pickup_cost, 2),
            night_fee=round(night_fee, 2),
            waiting_minutes=waiting_minutes,
            waiting_cost=round(waiting_cost, 2),
            total_cost=total_cost,
            currency="EUR"
        )
