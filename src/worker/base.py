# src/worker/base.py
"""
Базовый класс для воркеров.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.infra.event_bus import EventBus, DomainEvent, get_event_bus
from src.infra.database import DatabaseManager, get_db
from src.infra.redis_client import RedisClient, get_redis
from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg


class BaseWorker(ABC):
    """
    Базовый класс для всех воркеров.
    Подписывается на события и обрабатывает их.
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        db: Optional[DatabaseManager] = None,
        redis: Optional[RedisClient] = None,
    ) -> None:
        """
        Инициализирует воркер.
        
        Args:
            event_bus: Шина событий
            db: Менеджер БД
            redis: Redis клиент
        """
        self.event_bus = event_bus or get_event_bus()
        self.db = db or get_db()
        self.redis = redis or get_redis()
        self._running = False
        self._tasks: List[asyncio.Task] = []
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Имя воркера."""
        pass
    
    @property
    @abstractmethod
    def subscriptions(self) -> List[str]:
        """Список типов событий для подписки."""
        pass
    
    @abstractmethod
    async def handle_event(self, event: DomainEvent) -> None:
        """
        Обрабатывает событие.
        
        Args:
            event: Доменное событие
        """
        pass
    
    async def start(self) -> None:
        """Запускает воркер."""
        if self._running:
            return
        
        self._running = True
        await log_info(f"Воркер {self.name} запускается...", type_msg=TypeMsg.INFO)
        
        # Подписываемся на события
        for event_type in self.subscriptions:
            await self.event_bus.subscribe(
                event_type=event_type,
                callback=self._on_event,
            )
            await log_info(
                f"Воркер {self.name} подписан на {event_type}",
                type_msg=TypeMsg.DEBUG,
            )
        
        await log_info(f"Воркер {self.name} запущен", type_msg=TypeMsg.INFO)
    
    async def stop(self) -> None:
        """Останавливает воркер."""
        if not self._running:
            return
        
        self._running = False
        
        # Отменяем все задачи
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        await log_info(f"Воркер {self.name} остановлен", type_msg=TypeMsg.INFO)
    
    async def _on_event(self, event: DomainEvent) -> None:
        """
        Обработчик события.
        
        Args:
            event: Доменное событие
        """
        if not self._running:
            return
        
        try:
            await log_info(
                f"Воркер {self.name} получил событие {event.event_type}",
                type_msg=TypeMsg.DEBUG,
            )
            await self.handle_event(event)
        except Exception as e:
            await log_error(
                f"Ошибка в воркере {self.name}: {e}",
                extra={"event_type": event.event_type, "payload": event.payload},
            )
