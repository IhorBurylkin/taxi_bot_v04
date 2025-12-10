# src/core/__init__.py
"""
Доменный слой (Core Domain).
Чистая бизнес-логика, независимая от инфраструктуры.
"""

from src.core.users import User, DriverProfile, UserService
from src.core.orders import Order, OrderService
from src.core.matching import MatchingService

__all__ = [
    "User",
    "DriverProfile",
    "UserService",
    "Order",
    "OrderService",
    "MatchingService",
]
