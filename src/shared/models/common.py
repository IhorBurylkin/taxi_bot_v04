# src/shared/models/common.py
"""
Общие модели для всех сервисов.
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar, Any

from pydantic import BaseModel, Field


T = TypeVar("T")


class PaginationParams(BaseModel):
    """Параметры пагинации."""
    
    page: int = Field(default=1, ge=1, description="Номер страницы")
    page_size: int = Field(default=20, ge=1, le=100, description="Размер страницы")
    
    @property
    def offset(self) -> int:
        """Смещение для SQL-запроса."""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """Лимит для SQL-запроса."""
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Пагинированный ответ."""
    
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        pagination: PaginationParams,
    ) -> "PaginatedResponse[T]":
        """Создаёт пагинированный ответ."""
        total_pages = (total + pagination.page_size - 1) // pagination.page_size
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )


class ErrorResponse(BaseModel):
    """Стандартный ответ с ошибкой."""
    
    error_code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class HealthStatus(BaseModel):
    """Статус здоровья сервиса."""
    
    service: str
    status: str = "healthy"  # healthy, degraded, unhealthy
    version: str | None = None
    uptime_seconds: float | None = None
    dependencies: dict[str, str] = Field(default_factory=dict)
    # dependencies: {"postgres": "healthy", "redis": "healthy", "rabbitmq": "healthy"}
