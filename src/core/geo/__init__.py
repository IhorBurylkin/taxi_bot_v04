# src/core/geo/__init__.py
"""
Geo-сервис.
Работа с Google Maps API для геокодирования и расчёта маршрутов.
"""

from src.core.geo.service import GeoService

__all__ = [
    "GeoService",
]
