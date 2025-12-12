# src/services/realtime_location/app.py
"""
FastAPI приложение для Realtime Location Ingest.

Высокопроизводительный приём геолокации от водителей.

Endpoints:
- POST /api/v1/location - обновить локацию одного водителя
- POST /api/v1/location/batch - пакетное обновление
- GET /api/v1/location/{driver_id} - последняя локация
- GET /api/v1/location/nearby - ближайшие водители
- DELETE /api/v1/location/{driver_id} - удалить из индекса
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.shared.models.common import HealthStatus
from src.services.realtime_location.service import LocationIngestService


# === MODELS ===

class LocationUpdate(BaseModel):
    """Обновление геолокации."""
    driver_id: int
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    heading: float | None = Field(default=None, ge=0, le=360)
    speed: float | None = Field(default=None, ge=0)  # км/ч
    accuracy: float | None = Field(default=None, ge=0)  # метры
    timestamp: datetime | None = None


class BatchLocationUpdate(BaseModel):
    """Пакетное обновление."""
    updates: list[LocationUpdate]


class LocationResponse(BaseModel):
    """Ответ с локацией."""
    driver_id: int
    lat: float
    lon: float
    heading: float | None = None
    speed: float | None = None
    timestamp: str | None = None


class NearbyDriverResponse(BaseModel):
    """Ближайший водитель."""
    driver_id: int
    distance_km: float
    lat: float
    lon: float


class StatsResponse(BaseModel):
    """Статистика сервиса."""
    total_updates: int
    unique_drivers: int


# === SERVICE SINGLETON ===

_service: LocationIngestService | None = None


def get_service() -> LocationIngestService:
    """Получить сервис."""
    if _service is None:
        raise RuntimeError("Service not initialized")
    return _service


# === LIFESPAN ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения."""
    global _service
    
    from redis.asyncio import Redis
    from src.config import settings
    
    redis = Redis(
        host=settings.redis.REDIS_HOST,
        port=settings.redis.REDIS_PORT,
        db=settings.redis.REDIS_DB,
        password=settings.redis.REDIS_PASSWORD,
        decode_responses=False,
    )
    
    _service = LocationIngestService(redis)
    
    yield
    
    await redis.close()


# === APP ===

app = FastAPI(
    title="Realtime Location Ingest",
    description="Высокопроизводительный приём геолокации от водителей.",
    version="0.5.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# === HEALTH CHECK ===

@app.get("/health", response_model=HealthStatus, tags=["Health"])
async def health_check() -> HealthStatus:
    """Проверка здоровья сервиса."""
    return HealthStatus(
        status="healthy",
        service="realtime_location_ingest",
        version="0.5.0",
    )


# === STATS ===

@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats() -> StatsResponse:
    """Получить статистику сервиса."""
    service = get_service()
    stats = service.get_stats()
    return StatsResponse(
        total_updates=stats["total_updates"],
        unique_drivers=stats["unique_drivers"],
    )


# === LOCATION ENDPOINTS ===

@app.post(
    "/api/v1/location",
    tags=["Location"],
    summary="Обновить геолокацию",
)
async def update_location(update: LocationUpdate) -> dict[str, Any]:
    """
    Обновить геолокацию водителя.
    
    Сохраняет координаты в Redis GEO и публикует в Pub/Sub.
    """
    service = get_service()
    result = await service.update_location(
        driver_id=update.driver_id,
        lat=update.lat,
        lon=update.lon,
        heading=update.heading,
        speed=update.speed,
        accuracy=update.accuracy,
        timestamp=update.timestamp,
    )
    
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@app.post(
    "/api/v1/location/batch",
    tags=["Location"],
    summary="Пакетное обновление",
)
async def update_locations_batch(batch: BatchLocationUpdate) -> dict[str, Any]:
    """
    Пакетное обновление геолокаций.
    
    Используется для обработки нескольких водителей за раз.
    """
    service = get_service()
    updates = [u.model_dump() for u in batch.updates]
    return await service.update_locations_batch(updates)


@app.get(
    "/api/v1/location/{driver_id}",
    response_model=LocationResponse,
    responses={404: {"description": "Водитель не найден"}},
    tags=["Location"],
    summary="Последняя локация водителя",
)
async def get_driver_location(driver_id: int) -> LocationResponse:
    """Получить последнюю известную локацию водителя."""
    service = get_service()
    location = await service.get_driver_location(driver_id)
    
    if not location:
        raise HTTPException(status_code=404, detail="Водитель не найден")
    
    return LocationResponse(**location)


@app.get(
    "/api/v1/location/nearby",
    response_model=list[NearbyDriverResponse],
    tags=["Location"],
    summary="Ближайшие водители",
)
async def get_nearby_drivers(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(default=5.0, ge=0.1, le=50),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[NearbyDriverResponse]:
    """
    Найти ближайших водителей.
    
    Использует Redis GEORADIUS для быстрого поиска.
    """
    service = get_service()
    drivers = await service.get_nearby_drivers(lat, lon, radius_km, limit)
    return [NearbyDriverResponse(**d) for d in drivers]


@app.delete(
    "/api/v1/location/{driver_id}",
    tags=["Location"],
    summary="Удалить водителя из индекса",
)
async def remove_driver(driver_id: int) -> dict[str, str]:
    """
    Удалить водителя из индекса.
    
    Вызывается когда водитель уходит offline.
    """
    service = get_service()
    await service.remove_driver(driver_id)
    return {"status": "removed", "driver_id": str(driver_id)}


# === STARTUP ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
