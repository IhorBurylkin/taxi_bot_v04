# src/services/pricing/app.py
"""
FastAPI приложение для Pricing Service.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.common.logger import log_info
from src.common.constants import TypeMsg
from src.config import settings
from src.shared.models.common import HealthStatus, ErrorResponse
from src.shared.models.trip import FareDTO


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class FareCalculationRequest(BaseModel):
    """Запрос на расчёт стоимости."""
    
    distance_km: float = Field(..., ge=0, description="Расстояние в км")
    duration_minutes: int = Field(..., ge=0, description="Время в минутах")
    surge_multiplier: float = Field(default=1.0, ge=1.0, le=5.0)
    city: str | None = Field(default=None, description="Город для тарифной зоны")
    waiting_minutes: int = Field(default=0, ge=0, description="Время ожидания")


class FareCalculationResponse(BaseModel):
    """Ответ с расчётом стоимости."""
    
    fare: FareDTO
    breakdown: dict[str, float]


class SurgeRequest(BaseModel):
    """Запрос на расчёт surge multiplier."""
    
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: str | None = None


class SurgeResponse(BaseModel):
    """Ответ с surge multiplier."""
    
    surge_multiplier: float
    demand_level: str  # low, normal, high, very_high
    reason: str | None = None


class StarsConversionRequest(BaseModel):
    """Запрос на конвертацию в Stars."""
    
    amount: float
    currency: str = "EUR"


class StarsConversionResponse(BaseModel):
    """Ответ с количеством Stars."""
    
    amount_stars: int
    exchange_rate: float
    currency: str


class TariffDTO(BaseModel):
    """DTO тарифа."""
    
    id: str
    city: str
    name: str
    base_fare: float
    fare_per_km: float
    fare_per_minute: float
    pickup_fare: float
    waiting_fare_per_minute: float
    min_fare: float
    currency: str = "EUR"
    is_active: bool = True


# =============================================================================
# LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Жизненный цикл приложения."""
    await log_info(
        "Pricing Service запускается...",
        type_msg=TypeMsg.INFO,
    )
    
    from src.services.pricing.dependencies import init_dependencies, close_dependencies
    await init_dependencies()
    
    yield
    
    await close_dependencies()
    await log_info(
        "Pricing Service остановлен",
        type_msg=TypeMsg.INFO,
    )


# =============================================================================
# ПРИЛОЖЕНИЕ
# =============================================================================

app = FastAPI(
    title="Pricing Service",
    description="Сервис тарификации и расчёта стоимости поездок",
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
    from src.services.pricing.dependencies import get_redis
    
    deps = {}
    
    try:
        redis = await get_redis()
        await redis.ping()
        deps["redis"] = "healthy"
    except Exception:
        deps["redis"] = "unhealthy"
    
    overall = "healthy" if all(v == "healthy" for v in deps.values()) else "degraded"
    
    return HealthStatus(
        service="pricing_service",
        status=overall,
        version=settings.system.VERSION,
        dependencies=deps,
    )


# =============================================================================
# FARE CALCULATION API
# =============================================================================

@app.post(
    "/api/v1/pricing/calculate",
    response_model=FareCalculationResponse,
    tags=["Pricing"],
)
async def calculate_fare(request: FareCalculationRequest) -> FareCalculationResponse:
    """Расчёт стоимости поездки."""
    from src.services.pricing.dependencies import get_pricing_service
    
    service = await get_pricing_service()
    fare, breakdown = await service.calculate_fare(
        distance_km=request.distance_km,
        duration_minutes=request.duration_minutes,
        surge_multiplier=request.surge_multiplier,
        city=request.city,
        waiting_minutes=request.waiting_minutes,
    )
    
    return FareCalculationResponse(fare=fare, breakdown=breakdown)


@app.post(
    "/api/v1/pricing/surge",
    response_model=SurgeResponse,
    tags=["Pricing"],
)
async def get_surge_multiplier(request: SurgeRequest) -> SurgeResponse:
    """Получение коэффициента спроса для региона."""
    from src.services.pricing.dependencies import get_pricing_service
    
    service = await get_pricing_service()
    surge, level, reason = await service.get_surge_multiplier(
        lat=request.latitude,
        lon=request.longitude,
        city=request.city,
    )
    
    return SurgeResponse(
        surge_multiplier=surge,
        demand_level=level,
        reason=reason,
    )


@app.post(
    "/api/v1/pricing/convert-to-stars",
    response_model=StarsConversionResponse,
    tags=["Pricing"],
)
async def convert_to_stars(request: StarsConversionRequest) -> StarsConversionResponse:
    """Конвертация суммы в Telegram Stars."""
    from src.services.pricing.dependencies import get_pricing_service
    
    service = await get_pricing_service()
    stars, rate = await service.convert_to_stars(
        amount=request.amount,
        currency=request.currency,
    )
    
    return StarsConversionResponse(
        amount_stars=stars,
        exchange_rate=rate,
        currency=request.currency,
    )


# =============================================================================
# TARIFFS MANAGEMENT API
# =============================================================================

@app.get(
    "/api/v1/tariffs",
    response_model=list[TariffDTO],
    tags=["Tariffs"],
)
async def list_tariffs(city: str | None = None) -> list[TariffDTO]:
    """Список тарифов."""
    from src.services.pricing.dependencies import get_pricing_service
    
    service = await get_pricing_service()
    return await service.list_tariffs(city)


@app.get(
    "/api/v1/tariffs/{tariff_id}",
    response_model=TariffDTO,
    tags=["Tariffs"],
)
async def get_tariff(tariff_id: str) -> TariffDTO:
    """Получение тарифа по ID."""
    from src.services.pricing.dependencies import get_pricing_service
    
    service = await get_pricing_service()
    tariff = await service.get_tariff(tariff_id)
    
    if not tariff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тариф не найден",
        )
    
    return tariff


@app.post(
    "/api/v1/tariffs",
    response_model=TariffDTO,
    status_code=status.HTTP_201_CREATED,
    tags=["Tariffs"],
)
async def create_tariff(tariff: TariffDTO) -> TariffDTO:
    """Создание нового тарифа."""
    from src.services.pricing.dependencies import get_pricing_service
    
    service = await get_pricing_service()
    return await service.create_tariff(tariff)


@app.put(
    "/api/v1/tariffs/{tariff_id}",
    response_model=TariffDTO,
    tags=["Tariffs"],
)
async def update_tariff(tariff_id: str, tariff: TariffDTO) -> TariffDTO:
    """Обновление тарифа."""
    from src.services.pricing.dependencies import get_pricing_service
    
    service = await get_pricing_service()
    updated = await service.update_tariff(tariff_id, tariff)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тариф не найден",
        )
    
    return updated
