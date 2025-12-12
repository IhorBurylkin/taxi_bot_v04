from enum import Enum

class OrderStatus(str, Enum):
    """Статусы заказа."""
    DRAFT = "draft"
    NEW = "new"
    SEARCHING = "searching"
    ON_WAY = "on_way"
    ARRIVED = "arrived"
    STARTED = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value

class UserRole(str, Enum):
    """Роли пользователей."""
    DRIVER = "driver"
    PASSENGER = "passenger"
    ADMIN = "admin"

    def __str__(self) -> str:
        return self.value

class VerificationStatus(str, Enum):
    """Статусы верификации водителя."""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

    def __str__(self) -> str:
        return self.value

class TransactionDirection(str, Enum):
    """Направление транзакции."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"

    def __str__(self) -> str:
        return self.value

class TransactionStatus(str, Enum):
    """Статус транзакции."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    PROCESSING = "processing"

    def __str__(self) -> str:
        return self.value

class PaymentMethod(str, Enum):
    """Способы оплаты."""
    CASH = "cash"
    STARS = "stars"
    CARD = "card"

    def __str__(self) -> str:
        return self.value
