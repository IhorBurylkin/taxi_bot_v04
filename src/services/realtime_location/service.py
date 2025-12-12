# src/services/realtime_location/service.py
"""
Бизнес-логика приёма геолокации.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis


class LocationIngestService:
    """
    Сервис приёма и обработки геолокации водителей.
    
    Ответственности:
    - Сохранение координат в Redis GEO
    - Обновление last_seen
    - Публикация обновлений в Pub/Sub
    - Валидация координат
    """
    
    # Ключи Redis
    GEO_KEY = "drivers:geo"
    LAST_SEEN_PREFIX = "driver:last_seen:"
    LOCATION_CHANNEL_PREFIX = "location:driver:"
    
    # TTL
    LAST_SEEN_TTL = 300  # 5 минут
    
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis
        
        # Статистика
        self._total_updates = 0
        self._updates_per_driver: dict[int, int] = {}
    
    async def update_location(
        self,
        driver_id: int,
        lat: float,
        lon: float,
        heading: float | None = None,
        speed: float | None = None,
        accuracy: float | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Обновить геолокацию водителя.
        
        1. Валидация координат
        2. Сохранение в Redis GEO
        3. Обновление last_seen
        4. Публикация в Pub/Sub
        
        Returns:
            Результат обновления
        """
        # Валидация координат
        if not self._validate_coordinates(lat, lon):
            return {"error": "Invalid coordinates", "status": "failed"}
        
        now = timestamp or datetime.utcnow()
        
        # Pipeline для атомарности
        pipe = self._redis.pipeline()
        
        # 1. Сохраняем в GEO
        pipe.geoadd(self.GEO_KEY, (lon, lat, str(driver_id)))
        
        # 2. Обновляем last_seen
        last_seen_key = f"{self.LAST_SEEN_PREFIX}{driver_id}"
        last_seen_data = {
            "lat": lat,
            "lon": lon,
            "heading": heading,
            "speed": speed,
            "accuracy": accuracy,
            "timestamp": now.isoformat(),
        }
        pipe.hset(last_seen_key, mapping={
            k: str(v) if v is not None else ""
            for k, v in last_seen_data.items()
        })
        pipe.expire(last_seen_key, self.LAST_SEEN_TTL)
        
        # 3. Публикуем в Pub/Sub для WebSocket
        channel = f"{self.LOCATION_CHANNEL_PREFIX}{driver_id}"
        publish_data = {
            "driver_id": driver_id,
            "lat": lat,
            "lon": lon,
            "heading": heading,
            "speed": speed,
            "timestamp": now.isoformat(),
        }
        pipe.publish(channel, str(publish_data).replace("'", '"'))
        
        await pipe.execute()
        
        # Статистика
        self._total_updates += 1
        self._updates_per_driver[driver_id] = self._updates_per_driver.get(driver_id, 0) + 1
        
        return {
            "status": "ok",
            "driver_id": driver_id,
            "lat": lat,
            "lon": lon,
            "timestamp": now.isoformat(),
        }
    
    async def update_locations_batch(
        self,
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Пакетное обновление геолокаций.
        
        Используется для обработки нескольких водителей за раз.
        """
        results = []
        errors = []
        
        for update in updates:
            try:
                result = await self.update_location(
                    driver_id=update["driver_id"],
                    lat=update["lat"],
                    lon=update["lon"],
                    heading=update.get("heading"),
                    speed=update.get("speed"),
                    accuracy=update.get("accuracy"),
                )
                if result.get("status") == "ok":
                    results.append(result)
                else:
                    errors.append(result)
            except Exception as e:
                errors.append({
                    "driver_id": update.get("driver_id"),
                    "error": str(e),
                })
        
        return {
            "success_count": len(results),
            "error_count": len(errors),
            "errors": errors if errors else None,
        }
    
    async def get_driver_location(self, driver_id: int) -> dict[str, Any] | None:
        """Получить последнюю известную локацию водителя."""
        last_seen_key = f"{self.LAST_SEEN_PREFIX}{driver_id}"
        data = await self._redis.hgetall(last_seen_key)
        
        if not data:
            return None
        
        return {
            "driver_id": driver_id,
            "lat": float(data.get(b"lat", 0)),
            "lon": float(data.get(b"lon", 0)),
            "heading": float(data[b"heading"]) if data.get(b"heading") else None,
            "speed": float(data[b"speed"]) if data.get(b"speed") else None,
            "timestamp": data.get(b"timestamp", b"").decode(),
        }
    
    async def get_nearby_drivers(
        self,
        lat: float,
        lon: float,
        radius_km: float = 5.0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Найти ближайших водителей.
        
        Использует Redis GEORADIUS.
        """
        results = await self._redis.georadius(
            self.GEO_KEY,
            longitude=lon,
            latitude=lat,
            radius=radius_km,
            unit="km",
            withdist=True,
            withcoord=True,
            count=limit,
            sort="ASC",
        )
        
        drivers = []
        for item in results:
            driver_id = int(item[0])
            distance = item[1]
            coords = item[2]
            
            drivers.append({
                "driver_id": driver_id,
                "distance_km": round(distance, 2),
                "lat": coords[1],
                "lon": coords[0],
            })
        
        return drivers
    
    async def remove_driver(self, driver_id: int) -> None:
        """Удалить водителя из индекса (ушёл offline)."""
        pipe = self._redis.pipeline()
        pipe.zrem(self.GEO_KEY, str(driver_id))
        pipe.delete(f"{self.LAST_SEEN_PREFIX}{driver_id}")
        await pipe.execute()
    
    def get_stats(self) -> dict[str, Any]:
        """Получить статистику."""
        return {
            "total_updates": self._total_updates,
            "unique_drivers": len(self._updates_per_driver),
            "top_drivers": sorted(
                self._updates_per_driver.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10],
        }
    
    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        """Валидация координат."""
        return -90 <= lat <= 90 and -180 <= lon <= 180
