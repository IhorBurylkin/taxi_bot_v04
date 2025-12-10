# src/common/constants.py
"""
Общие константы и перечисления.
"""

from enum import Enum


class TypeMsg(str, Enum):
    """Типы сообщений для логирования."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class UserRole(str, Enum):
    """Роли пользователей."""
    PASSENGER = "passenger"
    DRIVER = "driver"
    ADMIN = "admin"


class OrderStatus(str, Enum):
    """Статусы заказа."""
    CREATED = "created"
    SEARCHING = "searching"
    ACCEPTED = "accepted"
    DRIVER_ARRIVED = "driver_arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class DriverStatus(str, Enum):
    """Статусы водителя."""
    OFFLINE = "offline"
    ONLINE = "online"
    BUSY = "busy"


class PaymentStatus(str, Enum):
    """Статусы оплаты."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """Способы оплаты."""
    CASH = "cash"
    CARD = "card"
    STARS = "stars"
