# src/shared/models/__init__.py
"""
Общие DTO и Pydantic-модели для межсервисного взаимодействия.
"""

from src.shared.models.user import (
    UserDTO,
    DriverDTO,
    UserRole,
    DriverStatus,
)
from src.shared.models.trip import (
    TripDTO,
    TripStatus,
    LocationDTO,
    FareDTO,
)
from src.shared.models.payment import (
    PaymentDTO,
    PaymentStatus,
    PaymentMethod,
)
from src.shared.models.common import (
    PaginationParams,
    PaginatedResponse,
    ErrorResponse,
    HealthStatus,
)

__all__ = [
    # User
    "UserDTO",
    "DriverDTO",
    "UserRole",
    "DriverStatus",
    # Trip
    "TripDTO",
    "TripStatus",
    "LocationDTO",
    "FareDTO",
    # Payment
    "PaymentDTO",
    "PaymentStatus",
    "PaymentMethod",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "ErrorResponse",
    "HealthStatus",
]
