# src/shared/models/payment.py
"""
DTO для платежей.
Поддержка Telegram Stars (валюта XTR).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PaymentMethod(str, Enum):
    """Способ оплаты."""
    STARS = "stars"  # Telegram Stars (XTR)
    CARD = "card"  # Банковская карта (планируется)
    CASH = "cash"  # Наличные (планируется)


class PaymentStatus(str, Enum):
    """Статус платежа."""
    PENDING = "pending"  # Ожидает оплаты
    PROCESSING = "processing"  # В обработке
    SUCCEEDED = "succeeded"  # Успешно
    FAILED = "failed"  # Ошибка
    REFUNDED = "refunded"  # Возврат
    CANCELLED = "cancelled"  # Отменён


class PaymentDTO(BaseModel):
    """DTO платежа для межсервисного взаимодействия."""
    
    id: str  # UUID
    trip_id: str
    payer_id: int  # telegram_id плательщика (rider)
    payee_id: int  # telegram_id получателя (driver)
    
    # Сумма
    amount: float
    currency: str = "XTR"  # XTR для Stars, EUR для обычных
    
    # В Stars (для Telegram Payments)
    amount_stars: int | None = None
    
    # Метод и статус
    method: PaymentMethod = PaymentMethod.STARS
    status: PaymentStatus = PaymentStatus.PENDING
    
    # Комиссии
    platform_commission: float = 0.0
    driver_payout: float = 0.0
    
    # Telegram Payments
    telegram_payment_charge_id: str | None = None
    provider_payment_charge_id: str | None = None
    
    # Временные метки
    created_at: datetime | None = None
    paid_at: datetime | None = None
    
    class Config:
        from_attributes = True


class PaymentCreateRequest(BaseModel):
    """Запрос на создание платежа."""
    
    trip_id: str
    payer_id: int
    payee_id: int
    amount: float
    currency: str = "XTR"
    method: PaymentMethod = PaymentMethod.STARS


class StarsInvoiceRequest(BaseModel):
    """Запрос на создание инвойса для Telegram Stars."""
    
    user_id: int  # telegram_id
    amount_stars: int
    title: str
    description: str
    payload: str  # JSON с данными (trip_id, etc.)
    
    # Опционально
    photo_url: str | None = None
    photo_width: int | None = None
    photo_height: int | None = None


class StarsPaymentResult(BaseModel):
    """Результат оплаты через Telegram Stars."""
    
    success: bool
    telegram_payment_charge_id: str | None = None
    provider_payment_charge_id: str | None = None
    amount_stars: int = 0
    error_message: str | None = None


class BalanceDTO(BaseModel):
    """DTO баланса пользователя."""
    
    user_id: int
    balance_stars: int = 0
    pending_stars: int = 0  # заблокировано для вывода
    total_earned_stars: int = 0
    total_spent_stars: int = 0
