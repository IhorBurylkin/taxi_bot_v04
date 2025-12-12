# src/services/users/app.py
"""
FastAPI приложение для Users Service.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg
from src.config import settings
from src.shared.models.common import HealthStatus, ErrorResponse
from src.shared.models.user import (
    UserDTO,
    DriverDTO,
    UserCreateRequest,
    DriverCreateRequest,
    DriverLocationUpdate,
)


# =============================================================================
# LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Жизненный цикл приложения."""
    await log_info(
        "Users Service запускается...",
        type_msg=TypeMsg.INFO,
    )
    
    # Инициализация зависимостей
    from src.services.users.dependencies import init_dependencies, close_dependencies
    await init_dependencies()
    
    yield
    
    # Закрытие ресурсов
    await close_dependencies()
    await log_info(
        "Users Service остановлен",
        type_msg=TypeMsg.INFO,
    )


# =============================================================================
# ПРИЛОЖЕНИЕ
# =============================================================================

app = FastAPI(
    title="Users Service",
    description="Сервис управления пользователями и водителями",
    version=settings.system.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене ограничить
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
    from src.services.users.dependencies import get_db, get_redis
    
    deps = {}
    
    # Проверка PostgreSQL
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        deps["postgres"] = "healthy"
    except Exception:
        deps["postgres"] = "unhealthy"
    
    # Проверка Redis
    try:
        redis = await get_redis()
        await redis.ping()
        deps["redis"] = "healthy"
    except Exception:
        deps["redis"] = "unhealthy"
    
    overall = "healthy" if all(v == "healthy" for v in deps.values()) else "degraded"
    
    return HealthStatus(
        service="users_service",
        status=overall,
        version=settings.system.VERSION,
        dependencies=deps,
    )


# =============================================================================
# USERS API
# =============================================================================

@app.post(
    "/api/v1/users",
    response_model=UserDTO,
    status_code=status.HTTP_201_CREATED,
    tags=["Users"],
    responses={
        409: {"model": ErrorResponse, "description": "Пользователь уже существует"},
    },
)
async def create_user(request: UserCreateRequest) -> UserDTO:
    """Создание нового пользователя."""
    from src.services.users.dependencies import get_user_service
    
    service = await get_user_service()
    
    # Проверяем, существует ли пользователь
    existing = await service.get_by_telegram_id(request.telegram_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким telegram_id уже существует",
        )
    
    user = await service.create_user(request)
    return user


@app.get(
    "/api/v1/users/{telegram_id}",
    response_model=UserDTO,
    tags=["Users"],
    responses={
        404: {"model": ErrorResponse, "description": "Пользователь не найден"},
    },
)
async def get_user(telegram_id: int) -> UserDTO:
    """Получение пользователя по telegram_id."""
    from src.services.users.dependencies import get_user_service
    
    service = await get_user_service()
    user = await service.get_by_telegram_id(telegram_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    
    return user


@app.patch(
    "/api/v1/users/{telegram_id}",
    response_model=UserDTO,
    tags=["Users"],
)
async def update_user(telegram_id: int, updates: dict) -> UserDTO:
    """Обновление профиля пользователя."""
    from src.services.users.dependencies import get_user_service
    
    service = await get_user_service()
    user = await service.update_user(telegram_id, updates)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    
    return user


@app.post(
    "/api/v1/users/{telegram_id}/block",
    response_model=UserDTO,
    tags=["Users"],
)
async def block_user(telegram_id: int, reason: str | None = None) -> UserDTO:
    """Блокировка пользователя."""
    from src.services.users.dependencies import get_user_service
    
    service = await get_user_service()
    user = await service.block_user(telegram_id, reason)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    
    return user


@app.post(
    "/api/v1/users/{telegram_id}/unblock",
    response_model=UserDTO,
    tags=["Users"],
)
async def unblock_user(telegram_id: int) -> UserDTO:
    """Разблокировка пользователя."""
    from src.services.users.dependencies import get_user_service
    
    service = await get_user_service()
    user = await service.unblock_user(telegram_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    
    return user


# =============================================================================
# DRIVERS API
# =============================================================================

@app.post(
    "/api/v1/drivers",
    response_model=DriverDTO,
    status_code=status.HTTP_201_CREATED,
    tags=["Drivers"],
)
async def create_driver(request: DriverCreateRequest) -> DriverDTO:
    """Регистрация водителя."""
    from src.services.users.dependencies import get_driver_service
    
    service = await get_driver_service()
    driver = await service.register_driver(request)
    return driver


@app.get(
    "/api/v1/drivers/{driver_id}",
    response_model=DriverDTO,
    tags=["Drivers"],
)
async def get_driver(driver_id: int) -> DriverDTO:
    """Получение информации о водителе."""
    from src.services.users.dependencies import get_driver_service
    
    service = await get_driver_service()
    driver = await service.get_driver(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Водитель не найден",
        )
    
    return driver


@app.post(
    "/api/v1/drivers/{driver_id}/online",
    response_model=DriverDTO,
    tags=["Drivers"],
)
async def set_driver_online(driver_id: int) -> DriverDTO:
    """Перевести водителя в онлайн."""
    from src.services.users.dependencies import get_driver_service
    
    service = await get_driver_service()
    driver = await service.set_online(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Водитель не найден",
        )
    
    return driver


@app.post(
    "/api/v1/drivers/{driver_id}/offline",
    response_model=DriverDTO,
    tags=["Drivers"],
)
async def set_driver_offline(driver_id: int) -> DriverDTO:
    """Перевести водителя в оффлайн."""
    from src.services.users.dependencies import get_driver_service
    
    service = await get_driver_service()
    driver = await service.set_offline(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Водитель не найден",
        )
    
    return driver


@app.post(
    "/api/v1/drivers/{driver_id}/location",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Drivers"],
)
async def update_driver_location(
    driver_id: int,
    location: DriverLocationUpdate,
) -> None:
    """Обновление геолокации водителя."""
    from src.services.users.dependencies import get_driver_service
    
    service = await get_driver_service()
    await service.update_location(driver_id, location)


@app.get(
    "/api/v1/drivers/nearby",
    response_model=list[DriverDTO],
    tags=["Drivers"],
)
async def get_nearby_drivers(
    lat: float,
    lon: float,
    radius_km: float = 3.0,
    limit: int = 10,
) -> list[DriverDTO]:
    """Получение ближайших онлайн-водителей."""
    from src.services.users.dependencies import get_driver_service
    
    service = await get_driver_service()
    drivers = await service.get_nearby_drivers(lat, lon, radius_km, limit)
    return drivers
