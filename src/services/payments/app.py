# src/services/payments/app.py
"""
FastAPI приложение для Payments Service.

Endpoints:
- POST /api/v1/payments - создать платёж
- GET /api/v1/payments/{id} - получить платёж
- POST /api/v1/payments/{id}/process-stars - обработать оплату Stars
- POST /api/v1/payments/{id}/refund - запросить возврат
- GET /api/v1/payments/trip/{trip_id} - платежи по поездке
- GET /api/v1/payments/user/{user_id} - платежи пользователя
- GET /api/v1/balances/{driver_id} - баланс водителя
- POST /api/v1/withdrawals - запросить вывод
- GET /api/v1/withdrawals/{driver_id} - история выводов
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel

from src.shared.models.common import ErrorResponse, HealthStatus
from src.shared.models.payment import (
    PaymentDTO,
    PaymentCreateRequest,
    StarsPaymentResult,
)
from src.services.payments.dependencies import (
    init_dependencies,
    cleanup_dependencies,
    get_payment_service,
    get_withdrawal_service,
)
from src.services.payments.service import PaymentService, WithdrawalService


# === REQUEST/RESPONSE MODELS ===

class RefundRequest(BaseModel):
    """Запрос на возврат."""
    reason: str | None = None
    requested_by: int = 0  # admin_id или 0 для system


class WithdrawalRequest(BaseModel):
    """Запрос на вывод средств."""
    amount_stars: int
    method: str = "telegram"


class WithdrawalResponse(BaseModel):
    """Ответ на запрос вывода."""
    withdrawal_id: str
    driver_id: int
    amount_stars: int
    amount_eur: float
    method: str
    status: str
    created_at: str


class BalanceResponse(BaseModel):
    """Баланс водителя."""
    driver_id: int
    total_earned: int
    available: int
    pending: int
    withdrawn: int


# === LIFESPAN ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения."""
    # Startup
    from src.infra.database import DatabaseManager
    from src.infra.redis_client import RedisClient
    from src.infra.event_bus import EventBus
    
    db = DatabaseManager()
    redis = RedisClient()
    event_bus = EventBus()
    
    await db.connect()
    await redis.connect()
    await event_bus.connect()
    
    await init_dependencies(db, redis, event_bus)
    
    yield
    
    # Shutdown
    await cleanup_dependencies()
    await event_bus.disconnect()
    await redis.disconnect()
    await db.disconnect()


# === APP ===

app = FastAPI(
    title="Payments Service",
    description="Сервис платежей и балансов. Поддержка Telegram Stars (XTR).",
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
        service="payments_service",
        version="0.5.0",
    )


# === PAYMENTS ENDPOINTS ===

@app.post(
    "/api/v1/payments",
    response_model=PaymentDTO,
    tags=["Payments"],
    summary="Создать платёж",
)
async def create_payment(
    request: PaymentCreateRequest,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentDTO:
    """
    Создать новый платёж.
    
    Рассчитывает комиссию платформы и сумму к выплате водителю.
    Публикует событие `payment.requested`.
    """
    try:
        return await service.create_payment(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/v1/payments/{payment_id}",
    response_model=PaymentDTO,
    responses={404: {"model": ErrorResponse}},
    tags=["Payments"],
    summary="Получить платёж",
)
async def get_payment(
    payment_id: str,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentDTO:
    """Получить платёж по ID."""
    payment = await service.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    return payment


@app.post(
    "/api/v1/payments/{payment_id}/process-stars",
    response_model=PaymentDTO,
    responses={404: {"model": ErrorResponse}},
    tags=["Payments"],
    summary="Обработать оплату Stars",
)
async def process_stars_payment(
    payment_id: str,
    result: StarsPaymentResult,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentDTO:
    """
    Обработать результат оплаты через Telegram Stars.
    
    Вызывается после получения `successful_payment` от Telegram.
    При успехе начисляет баланс водителю.
    """
    try:
        return await service.process_stars_payment(payment_id, result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post(
    "/api/v1/payments/{payment_id}/refund",
    responses={404: {"model": ErrorResponse}},
    tags=["Payments"],
    summary="Запросить возврат",
)
async def request_refund(
    payment_id: str,
    request: RefundRequest,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> dict:
    """
    Запросить возврат средств по платежу.
    
    Возвращает `refund_id` для отслеживания.
    """
    try:
        refund_id = await service.request_refund(
            payment_id=payment_id,
            reason=request.reason,
            requested_by=request.requested_by,
        )
        return {"refund_id": refund_id, "status": "requested"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/v1/payments/trip/{trip_id}",
    response_model=list[PaymentDTO],
    tags=["Payments"],
    summary="Платежи по поездке",
)
async def get_payments_by_trip(
    trip_id: str,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> list[PaymentDTO]:
    """Получить все платежи по поездке."""
    return await service.get_payments_by_trip(trip_id)


@app.get(
    "/api/v1/payments/user/{user_id}",
    response_model=list[PaymentDTO],
    tags=["Payments"],
    summary="Платежи пользователя",
)
async def get_payments_by_user(
    user_id: int,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    role: str = Query(default="payer", regex="^(payer|payee)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[PaymentDTO]:
    """
    Получить платежи пользователя.
    
    - `role=payer` — где пользователь платил (rider)
    - `role=payee` — где пользователь получал (driver)
    """
    return await service.get_payments_by_user(user_id, role, limit, offset)


# === BALANCES ENDPOINTS ===

@app.get(
    "/api/v1/balances/{driver_id}",
    response_model=BalanceResponse,
    tags=["Balances"],
    summary="Баланс водителя",
)
async def get_driver_balance(
    driver_id: int,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> BalanceResponse:
    """
    Получить баланс водителя.
    
    Возвращает:
    - `total_earned` — общий заработок (Stars)
    - `available` — доступно для вывода
    - `pending` — ожидает подтверждения
    - `withdrawn` — уже выведено
    """
    balance = await service.get_driver_balance(driver_id)
    return BalanceResponse(**balance)


# === WITHDRAWALS ENDPOINTS ===

@app.post(
    "/api/v1/withdrawals",
    response_model=WithdrawalResponse,
    tags=["Withdrawals"],
    summary="Запросить вывод",
)
async def request_withdrawal(
    driver_id: int,
    request: WithdrawalRequest,
    service: Annotated[WithdrawalService, Depends(get_withdrawal_service)],
) -> WithdrawalResponse:
    """
    Запросить вывод средств.
    
    Проверяет:
    - Достаточный баланс
    - Минимальную сумму вывода (500 Stars по умолчанию)
    """
    try:
        result = await service.request_withdrawal(
            driver_id=driver_id,
            amount_stars=request.amount_stars,
            method=request.method,
        )
        return WithdrawalResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/v1/withdrawals/{driver_id}",
    response_model=list[WithdrawalResponse],
    tags=["Withdrawals"],
    summary="История выводов",
)
async def get_withdrawals(
    driver_id: int,
    service: Annotated[WithdrawalService, Depends(get_withdrawal_service)],
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[WithdrawalResponse]:
    """Получить историю выводов водителя."""
    withdrawals = await service.get_withdrawals(driver_id, status, limit)
    return [WithdrawalResponse(**w) for w in withdrawals]


# === STARTUP ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087)
