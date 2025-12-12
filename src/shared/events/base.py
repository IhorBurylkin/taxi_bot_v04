# src/shared/events/base.py
"""
Базовые классы для доменных событий.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field


class EventMetadata(BaseModel):
    """Метаданные события для трассировки и дедупликации."""
    
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None
    causation_id: str | None = None
    source_service: str = ""
    version: int = 1
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat().replace("+00:00", "Z")
        }


class DomainEvent(BaseModel):
    """
    Базовый класс для всех доменных событий.
    
    Все события должны быть:
    - Иммутабельными
    - Сериализуемыми в JSON
    - Идемпотентными при обработке (по event_id)
    """
    
    event_type: str = ""
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    
    def to_json(self) -> str:
        """Сериализует событие в JSON."""
        return self.model_dump_json()
    
    @classmethod
    def from_json(cls, data: str | bytes) -> "DomainEvent":
        """Десериализует событие из JSON."""
        return cls.model_validate_json(data)
    
    @property
    def event_id(self) -> str:
        """Уникальный идентификатор события."""
        return self.metadata.event_id
    
    @property
    def timestamp(self) -> datetime:
        """Время создания события."""
        return self.metadata.timestamp


# Тип для generic-событий
EventT = TypeVar("EventT", bound=DomainEvent)
