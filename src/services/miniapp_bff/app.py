# src/services/miniapp_bff/app.py
"""
FastAPI приложение для MiniApp BFF.

Backend for Frontend для Telegram Mini App.
Все endpoints требуют валидацию Telegram initData.

Endpoints:
- GET /api/v1/miniapp/home - данные главного экрана
- POST /api/v1/miniapp/fare - расчёт стоимости
- POST /api/v1/miniapp/trip - создать поездку
- GET /api/v1/miniapp/trip/{id} - статус поездки
- POST /api/v1/miniapp/trip/{id}/cancel - отменить
- GET /api/v1/miniapp/history - история поездок
- PATCH /api/v1/miniapp/profile - обновить профиль
- POST /api/v1/miniapp/driver/online - выйти на линию
- POST /api/v1/miniapp/driver/offline - уйти с линии
- POST /api/v1/miniapp/driver/location - обновить геолокацию
- POST /api/v1/miniapp/driver/accept/{trip_id} - принять заказ
- POST /api/v1/miniapp/driver/start/{trip_id} - начать поездку
- POST /api/v1/miniapp/driver/complete/{trip_id} - завершить
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.shared.models.common import HealthStatus
from src.services.miniapp_bff.telegram_auth import (
    validate_init_data,
    TelegramInitData,
    TelegramAuthError,
)
from src.services.miniapp_bff.dependencies import (
    init_dependencies,
    cleanup_dependencies,
    get_bot_token,
    get_miniapp_service,
)
from src.services.miniapp_bff.service import MiniAppService


# === REQUEST MODELS ===

class FareRequest(BaseModel):
    """Запрос расчёта стоимости."""
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    vehicle_class: str = "standard"


class CreateTripRequest(BaseModel):
    """Запрос на создание поездки."""
    pickup_lat: float
    pickup_lon: float
    pickup_address: str
    dropoff_lat: float
    dropoff_lon: float
    dropoff_address: str
    vehicle_class: str = "standard"
    payment_method: str = "stars"


class CancelTripRequest(BaseModel):
    """Запрос на отмену поездки."""
    reason: str | None = None


class UpdateProfileRequest(BaseModel):
    """Запрос на обновление профиля."""
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    language: str | None = None


class LocationRequest(BaseModel):
    """Запрос обновления геолокации."""
    lat: float
    lon: float


# === AUTH DEPENDENCY ===

async def get_current_user(
    x_telegram_init_data: Annotated[str, Header(alias="X-Telegram-Init-Data")],
) -> TelegramInitData:
    """
    Валидировать initData из заголовка X-Telegram-Init-Data.
    
    Все endpoints MiniApp BFF требуют этот заголовок.
    """
    bot_token = get_bot_token()
    
    try:
        return validate_init_data(x_telegram_init_data, bot_token)
    except TelegramAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


# === LIFESPAN ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения."""
    from src.infra.redis_client import RedisClient
    from src.config import settings
    
    redis = RedisClient()
    await redis.connect()
    
    # URL микросервисов из конфига
    users_url = f"http://localhost:{settings.deployment.USERS_SERVICE_PORT}"
    trips_url = f"http://localhost:{settings.deployment.TRIP_SERVICE_PORT}"
    pricing_url = f"http://localhost:{settings.deployment.PRICING_SERVICE_PORT}"
    payments_url = f"http://localhost:{settings.deployment.PAYMENTS_SERVICE_PORT}"
    
    await init_dependencies(
        redis=redis,
        bot_token=settings.telegram.BOT_TOKEN,
        users_service_url=users_url,
        trips_service_url=trips_url,
        pricing_service_url=pricing_url,
        payments_service_url=payments_url,
    )
    
    yield
    
    await cleanup_dependencies()
    await redis.disconnect()


# === APP ===

app = FastAPI(
    title="MiniApp BFF",
    description="Backend for Frontend для Telegram Mini App. Агрегирует данные из микросервисов.",
    version="0.5.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS для React Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Telegram Mini App загружается с разных доменов
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === HEALTH CHECK ===

@app.get("/health", response_model=HealthStatus, tags=["Health"])
async def health_check() -> HealthStatus:
    """Проверка здоровья сервиса."""
    return HealthStatus(
        status="healthy",
        service="miniapp_bff",
        version="0.5.0",
    )


# === HOME ===

@app.get("/api/v1/miniapp/home", tags=["Home"])
async def get_home(
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """
    Получить данные для главного экрана.
    
    Возвращает:
    - Профиль пользователя
    - Активную поездку (если есть)
    - Избранные адреса
    - Баланс (для водителей)
    """
    return await service.get_home_data(user.user.id)


# === FARE CALCULATION ===

@app.post("/api/v1/miniapp/fare", tags=["Trips"])
async def calculate_fare(
    request: FareRequest,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """
    Рассчитать стоимость поездки.
    
    Возвращает цену в EUR и Stars.
    """
    return await service.calculate_fare(
        pickup_lat=request.pickup_lat,
        pickup_lon=request.pickup_lon,
        dropoff_lat=request.dropoff_lat,
        dropoff_lon=request.dropoff_lon,
        vehicle_class=request.vehicle_class,
    )


# === TRIPS ===

@app.post("/api/v1/miniapp/trip", tags=["Trips"])
async def create_trip(
    request: CreateTripRequest,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Создать заказ поездки."""
    result = await service.create_trip(
        user_id=user.user.id,
        pickup_lat=request.pickup_lat,
        pickup_lon=request.pickup_lon,
        pickup_address=request.pickup_address,
        dropoff_lat=request.dropoff_lat,
        dropoff_lon=request.dropoff_lon,
        dropoff_address=request.dropoff_address,
        vehicle_class=request.vehicle_class,
        payment_method=request.payment_method,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/v1/miniapp/trip/{trip_id}", tags=["Trips"])
async def get_trip_status(
    trip_id: str,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Получить статус поездки."""
    result = await service.get_trip_status(trip_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/v1/miniapp/trip/{trip_id}/cancel", tags=["Trips"])
async def cancel_trip(
    trip_id: str,
    request: CancelTripRequest,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Отменить поездку."""
    result = await service.cancel_trip(trip_id, request.reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# === HISTORY ===

@app.get("/api/v1/miniapp/history", tags=["History"])
async def get_history(
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Получить историю поездок."""
    return await service.get_trip_history(user.user.id, limit, offset)


# === PROFILE ===

@app.patch("/api/v1/miniapp/profile", tags=["Profile"])
async def update_profile(
    request: UpdateProfileRequest,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Обновить профиль пользователя."""
    data = request.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    
    result = await service.update_profile(user.user.id, data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# === DRIVER ENDPOINTS ===

@app.post("/api/v1/miniapp/driver/online", tags=["Driver"])
async def driver_go_online(
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Водитель выходит на линию."""
    result = await service.driver_go_online(user.user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/v1/miniapp/driver/offline", tags=["Driver"])
async def driver_go_offline(
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Водитель уходит с линии."""
    result = await service.driver_go_offline(user.user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/v1/miniapp/driver/location", tags=["Driver"])
async def update_driver_location(
    request: LocationRequest,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Обновить геолокацию водителя."""
    return await service.update_driver_location(user.user.id, request.lat, request.lon)


@app.post("/api/v1/miniapp/driver/accept/{trip_id}", tags=["Driver"])
async def accept_trip(
    trip_id: str,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Водитель принимает заказ."""
    result = await service.accept_trip(trip_id, user.user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/v1/miniapp/driver/start/{trip_id}", tags=["Driver"])
async def start_trip(
    trip_id: str,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Водитель начинает поездку (пассажир в машине)."""
    result = await service.start_trip(trip_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/v1/miniapp/driver/complete/{trip_id}", tags=["Driver"])
async def complete_trip(
    trip_id: str,
    user: Annotated[TelegramInitData, Depends(get_current_user)],
    service: Annotated[MiniAppService, Depends(get_miniapp_service)],
) -> dict[str, Any]:
    """Водитель завершает поездку."""
    result = await service.complete_trip(trip_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# === STARTUP ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)
