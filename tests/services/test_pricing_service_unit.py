import pytest
from src.services.pricing_service.service import PricingService
from src.config import settings

def test_calculate_price_base():
    service = PricingService()
    
    # Test case 1: Short distance (< 5km)
    # Should be just base fare
    result = service.calculate_price(distance_km=3.0)
    assert result.total_cost == settings.fares.BASE_FARE_FIRST_5KM
    assert result.distance_km == 3.0

def test_calculate_price_long_distance():
    service = PricingService()
    
    # Test case 2: Long distance (10km)
    # 5km base + 5km * per_km
    expected_cost = settings.fares.BASE_FARE_FIRST_5KM + (5.0 * settings.fares.FARE_PER_KM_AFTER_5)
    result = service.calculate_price(distance_km=10.0)
    assert result.base_cost == expected_cost

def test_calculate_price_night():
    service = PricingService()
    
    # Test case 3: Night fee
    result = service.calculate_price(distance_km=3.0, is_night=True)
    expected_cost = settings.fares.BASE_FARE_FIRST_5KM + settings.fares.NIGHT_FEE
    assert result.total_cost == expected_cost
    assert result.night_fee == settings.fares.NIGHT_FEE

def test_calculate_price_waiting():
    service = PricingService()
    
    # Test case 4: Waiting time
    # 10 mins waiting (5 free + 5 paid)
    waiting_mins = settings.fares.WAITING_FREE_MINUTES + 5
    result = service.calculate_price(distance_km=3.0, waiting_minutes=waiting_mins)
    
    expected_waiting_cost = 5 * settings.fares.WAITING_FARE_PER_MINUTE
    assert result.waiting_cost == expected_waiting_cost
