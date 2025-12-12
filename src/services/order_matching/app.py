# src/services/order_matching/app.py
"""
FastAPI приложение для Order Matching Service.

Сервис диспетчеризации и поиска водителей.

Endpoints:
- POST /api/v1/matching/start - начать поиск водителя
- POST /api/v1/matching/cancel/{trip_id} - отменить поиск
- POST /api/v1/matching/response - ответ водителя на предложение
- GET /api/v1/matching/offer/{driver_id} - текущее предложение для водителя
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.shared.models.common import HealthStatus
from src.services.order_matching.service import MatchingService


# === MODELS ===

class StartMatchingRequest(BaseModel):
    """Запрос на начало поиска водителя."""
    trip_id: str
    pickup_lat: float
    pickup_lon: float
    pickup_address: str
    dropoff_address: str
    fare_amount: float
    vehicle_class: str = "standard"


class DriverResponseRequest(BaseModel):
    """Ответ водителя на предложение."""
    trip_id: str
    driver_id: int
    accepted: bool


class OfferResponse(BaseModel):
    """Текущее предложение для водителя."""
    offer_id: str
    trip_id: str
    pickup_address: str
    dropoff_address: str
    fare_amount: float
    distance_km: float
    expires_at: str


# === SERVICE SINGLETON ===

_service: MatchingService | None = None


def get_service() -> MatchingService:
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
    from src.infra.event_bus import EventBus
    from src.config import settings
    
    redis = Redis(
        host=settings.redis.REDIS_HOST,
        port=settings.redis.REDIS_PORT,
        db=settings.redis.REDIS_DB,
        password=settings.redis.REDIS_PASSWORD,
        decode_responses=False,
    )
    
    event_bus = EventBus()
    await event_bus.connect()
    
    # URL других сервисов
    location_url = f"http://localhost:{settings.deployment.REALTIME_LOCATION_INGEST_PORT}"
    users_url = f"http://localhost:{settings.deployment.USERS_SERVICE_PORT}"
    trips_url = f"http://localhost:{settings.deployment.TRIP_SERVICE_PORT}"
    
    _service = MatchingService(
        redis=redis,
        event_bus=event_bus,
        location_service_url=location_url,
        users_service_url=users_url,
        trips_service_url=trips_url,
    )
    
    yield
    
    await _service.close()
    await event_bus.disconnect()
    await redis.close()


# === APP ===

app = FastAPI(
    title="Order Matching Service",
    description="Сервис диспетчеризации и поиска водителей.",
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
        service="order_matching_service",
        version="0.5.0",
    )


# === MATCHING ENDPOINTS ===

@app.post(
    "/api/v1/matching/start",
    tags=["Matching"],
    summary="Начать поиск водителя",
)
async def start_matching(request: StartMatchingRequest) -> dict[str, Any]:
    """
    Начать поиск водителя для заказа.
    
    Запускает асинхронный процесс:
    1. Поиск ближайших водителей
    2. Отправка предложений по очереди
    3. Ожидание ответа (30 сек на каждого)
    4. Расширение радиуса при необходимости
    """
    service = get_service()
    matching_id = await service.start_matching(
        trip_id=request.trip_id,
        pickup_lat=request.pickup_lat,
        pickup_lon=request.pickup_lon,
        pickup_address=request.pickup_address,
        dropoff_address=request.dropoff_address,
        fare_amount=request.fare_amount,
        vehicle_class=request.vehicle_class,
    )
    
    return {
        "status": "started",
        "matching_id": matching_id,
        "trip_id": request.trip_id,
    }


@app.post(
    "/api/v1/matching/cancel/{trip_id}",
    tags=["Matching"],
    summary="Отменить поиск",
)
async def cancel_matching(trip_id: str) -> dict[str, str]:
    """Отменить поиск водителя."""
    service = get_service()
    await service.cancel_matching(trip_id)
    return {"status": "cancelled", "trip_id": trip_id}


@app.post(
    "/api/v1/matching/response",
    tags=["Matching"],
    summary="Ответ водителя",
)
async def driver_response(request: DriverResponseRequest) -> dict[str, Any]:
    """
    Обработать ответ водителя на предложение.
    
    - `accepted=true` — водитель принимает заказ
    - `accepted=false` — водитель отклоняет
    """
    service = get_service()
    result = await service.handle_driver_response(
        trip_id=request.trip_id,
        driver_id=request.driver_id,
        accepted=request.accepted,
    )
    
    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@app.get(
    "/api/v1/matching/offer/{driver_id}",
    response_model=OfferResponse,
    responses={404: {"description": "Нет активного предложения"}},
    tags=["Matching"],
    summary="Текущее предложение для водителя",
)
async def get_offer_for_driver(driver_id: int) -> OfferResponse:
    """Получить текущее предложение для водителя."""
    service = get_service()
    offer = await service.get_offer_for_driver(driver_id)
    
    if not offer:
        raise HTTPException(status_code=404, detail="Нет активного предложения")
    
    return OfferResponse(**offer)


# === STARTUP ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8091)
