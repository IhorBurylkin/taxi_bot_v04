import math
from typing import List, Tuple, Optional
from src.infra.redis_client import RedisClient
from src.common.logger import log_info

class GeoUtils:
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self.drivers_geo_key = "drivers:locations"

    async def update_driver_location(self, driver_id: int, lat: float, lon: float):
        """Updates driver's location in Redis GEO index."""
        await self.redis.geoadd(self.drivers_geo_key, lon, lat, str(driver_id))

    async def find_drivers_in_radius(
        self, 
        lat: float, 
        lon: float, 
        radius_km: float = 5.0, 
        count: int = 10
    ) -> List[Tuple[int, float]]:
        """
        Finds drivers within radius.
        Returns list of (driver_id, distance_km).
        """
        # Redis GEORADIUS returns list of [member, distance, coord, ...] depending on flags
        # Our wrapper returns list of tuples (member, distance) if with_dist=True
        results = await self.redis.georadius(
            self.drivers_geo_key,
            lon,
            lat,
            radius_km,
            unit="km",
            with_dist=True,
            count=count,
            sort="ASC"
        )
        
        drivers = []
        for member, distance in results:
            try:
                drivers.append((int(member), distance))
            except ValueError:
                continue
                
        return drivers

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculates distance between two points using Haversine formula.
        Fallback if Redis is not available or for precise calculations.
        """
        R = 6371  # Earth radius in km
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
