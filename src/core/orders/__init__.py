# src/core/orders/__init__.py
"""
Домен заказов.
Модели и сервисы для работы с заказами.
"""

from src.core.orders.models import Order, OrderCreateDTO
from src.core.orders.service import OrderService
from src.core.orders.repository import OrderRepository

__all__ = [
    "Order",
    "OrderCreateDTO",
    "OrderService",
    "OrderRepository",
]
