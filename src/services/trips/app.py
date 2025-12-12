# src/services/trips/app.py
"""
FastAPI приложение для Trip Service.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware

from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg
from src.config import settings
from src.shared.models.common import HealthStatus, ErrorResponse, PaginationParams, PaginatedResponse
from src.shared.models.trip import (
    TripDTO,
    TripStatus,
    TripCreateRequest,
    TripSearchParams,
    LocationDTO,
)


# =============================================================================
# LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Жизненный цикл приложения."""
    await log_info(
        "Trip Service запускается...",
        type_msg=TypeMsg.INFO,
    )
    
    from src.services.trips.dependencies import init_dependencies, close_dependencies
    await init_dependencies()
    
    yield
    
    await close_dependencies()
    await log_info(
        "Trip Service остановлен",
        type_msg=TypeMsg.INFO,
    )


# =============================================================================
# ПРИЛОЖЕНИЕ
# =============================================================================

app = FastAPI(
    title="Trip Service",
    description="Сервис управления поездками (state machine)",
    version=settings.system.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health", response_model=HealthStatus, tags=["Health"])
async def health_check() -> HealthStatus:
    """Проверка здоровья сервиса."""
    from src.services.trips.dependencies import get_db, get_redis
    
    deps = {}
    
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        deps["postgres"] = "healthy"
    except Exception:
        deps["postgres"] = "unhealthy"
    
    try:
        redis = await get_redis()
        await redis.ping()
        deps["redis"] = "healthy"
    except Exception:
        deps["redis"] = "unhealthy"
    
    overall = "healthy" if all(v == "healthy" for v in deps.values()) else "degraded"
    
    return HealthStatus(
        service="trip_service",
        status=overall,
        version=settings.system.VERSION,
        dependencies=deps,
    )


# =============================================================================
# TRIPS API
# =============================================================================

@app.post(
    "/api/v1/trips",
    response_model=TripDTO,
    status_code=status.HTTP_201_CREATED,
    tags=["Trips"],
)
async def create_trip(request: TripCreateRequest) -> TripDTO:
    """Создание новой поездки."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    trip = await service.create_trip(request)
    return trip


@app.get(
    "/api/v1/trips/{trip_id}",
    response_model=TripDTO,
    tags=["Trips"],
    responses={
        404: {"model": ErrorResponse, "description": "Поездка не найдена"},
    },
)
async def get_trip(trip_id: str) -> TripDTO:
    """Получение поездки по ID."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    trip = await service.get_trip(trip_id)
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поездка не найдена",
        )
    
    return trip


@app.get(
    "/api/v1/trips",
    response_model=list[TripDTO],
    tags=["Trips"],
)
async def list_trips(
    rider_id: int | None = None,
    driver_id: int | None = None,
    status: TripStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[TripDTO]:
    """Список поездок с фильтрацией."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    
    params = TripSearchParams(
        rider_id=rider_id,
        driver_id=driver_id,
        status=status,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    
    trips = await service.list_trips(params, pagination)
    return trips


@app.get(
    "/api/v1/trips/active/rider/{rider_id}",
    response_model=TripDTO | None,
    tags=["Trips"],
)
async def get_active_trip_for_rider(rider_id: int) -> TripDTO | None:
    """Получение активной поездки пассажира."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    return await service.get_active_trip_for_rider(rider_id)


@app.get(
    "/api/v1/trips/active/driver/{driver_id}",
    response_model=TripDTO | None,
    tags=["Trips"],
)
async def get_active_trip_for_driver(driver_id: int) -> TripDTO | None:
    """Получение активной поездки водителя."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    return await service.get_active_trip_for_driver(driver_id)


# =============================================================================
# TRIP STATE MACHINE
# =============================================================================

@app.post(
    "/api/v1/trips/{trip_id}/accept",
    response_model=TripDTO,
    tags=["Trip State"],
)
async def accept_trip(trip_id: str, driver_id: int) -> TripDTO:
    """Водитель принимает заказ."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    trip = await service.accept_trip(trip_id, driver_id)
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поездка не найдена",
        )
    
    return trip


@app.post(
    "/api/v1/trips/{trip_id}/driver-arrived",
    response_model=TripDTO,
    tags=["Trip State"],
)
async def driver_arrived(trip_id: str) -> TripDTO:
    """Водитель прибыл к точке посадки."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    trip = await service.driver_arrived(trip_id)
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поездка не найдена",
        )
    
    return trip


@app.post(
    "/api/v1/trips/{trip_id}/start",
    response_model=TripDTO,
    tags=["Trip State"],
)
async def start_trip(trip_id: str) -> TripDTO:
    """Начало поездки."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    trip = await service.start_trip(trip_id)
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поездка не найдена",
        )
    
    return trip


@app.post(
    "/api/v1/trips/{trip_id}/complete",
    response_model=TripDTO,
    tags=["Trip State"],
)
async def complete_trip(
    trip_id: str,
    final_fare: float | None = None,
) -> TripDTO:
    """Завершение поездки."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    trip = await service.complete_trip(trip_id, final_fare)
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поездка не найдена",
        )
    
    return trip


@app.post(
    "/api/v1/trips/{trip_id}/cancel",
    response_model=TripDTO,
    tags=["Trip State"],
)
async def cancel_trip(
    trip_id: str,
    cancelled_by: str = "rider",
    reason: str | None = None,
) -> TripDTO:
    """Отмена поездки."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    trip = await service.cancel_trip(trip_id, cancelled_by, reason)
    
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поездка не найдена",
        )
    
    return trip


# =============================================================================
# TRIP EVENTS (история)
# =============================================================================

@app.get(
    "/api/v1/trips/{trip_id}/events",
    response_model=list[dict],
    tags=["Trip Events"],
)
async def get_trip_events(trip_id: str) -> list[dict]:
    """Получение истории событий поездки."""
    from src.services.trips.dependencies import get_trip_service
    
    service = await get_trip_service()
    events = await service.get_trip_events(trip_id)
    return events
