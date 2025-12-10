# src/core/billing/__init__.py
"""
Домен биллинга.
Работа с оплатой, Stars, балансами.
"""

from src.core.billing.service import BillingService

__all__ = [
    "BillingService",
]
