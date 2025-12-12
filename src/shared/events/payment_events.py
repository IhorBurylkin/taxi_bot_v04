# src/shared/events/payment_events.py
"""
События домена платежей.
Поддержка Telegram Stars (валюта XTR).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.shared.events.base import DomainEvent


class PaymentRequested(DomainEvent):
    """Событие: запрос на оплату."""
    
    event_type: Literal["payment.requested"] = "payment.requested"
    
    payment_id: str
    trip_id: str
    payer_id: int  # user_id (rider)
    payee_id: int  # user_id (driver)
    amount: float
    currency: str = "XTR"  # XTR для Telegram Stars, EUR для обычных платежей
    payment_method: str = "stars"  # stars, card, cash


class PaymentSucceeded(DomainEvent):
    """Событие: оплата успешна."""
    
    event_type: Literal["payment.succeeded"] = "payment.succeeded"
    
    payment_id: str
    trip_id: str
    payer_id: int
    payee_id: int
    amount: float
    currency: str = "XTR"
    platform_commission: float = 0.0
    driver_payout: float = 0.0
    telegram_payment_charge_id: str | None = None


class PaymentFailed(DomainEvent):
    """Событие: оплата не удалась."""
    
    event_type: Literal["payment.failed"] = "payment.failed"
    
    payment_id: str
    trip_id: str
    payer_id: int
    error_code: str | None = None
    error_message: str | None = None


class RefundRequested(DomainEvent):
    """Событие: запрос на возврат средств."""
    
    event_type: Literal["refund.requested"] = "refund.requested"
    
    refund_id: str
    payment_id: str
    trip_id: str
    amount: float
    currency: str = "XTR"
    reason: str | None = None
    requested_by: int  # admin_id или system


class RefundCompleted(DomainEvent):
    """Событие: возврат средств выполнен."""
    
    event_type: Literal["refund.completed"] = "refund.completed"
    
    refund_id: str
    payment_id: str
    amount: float
    currency: str = "XTR"
    telegram_refund_id: str | None = None
