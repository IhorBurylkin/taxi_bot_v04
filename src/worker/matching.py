# src/worker/matching.py
"""
Воркер матчинга заказов с водителями.
"""

from __future__ import annotations

from typing import List, Optional

from src.worker.base import BaseWorker
from src.infra.event_bus import DomainEvent, EventTypes
from src.core.matching.service import MatchingService
from src.core.orders.service import OrderService
from src.core.users.service import UserService
from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg, OrderStatus


class MatchingWorker(BaseWorker):
    """
    Воркер для матчинга заказов.
    Подписывается на ORDER_CREATED и ищет подходящих водителей.
    """
    
    @property
    def name(self) -> str:
        return "MatchingWorker"
    
    @property
    def subscriptions(self) -> List[str]:
        return [
            EventTypes.ORDER_CREATED,
            EventTypes.ORDER_DRIVER_DECLINED,
        ]
    
    async def handle_event(self, event: DomainEvent) -> None:
        """Обрабатывает событие."""
        if event.event_type == EventTypes.ORDER_CREATED:
            await self._handle_order_created(event)
        elif event.event_type == EventTypes.ORDER_DRIVER_DECLINED:
            await self._handle_driver_declined(event)
    
    async def _handle_order_created(self, event: DomainEvent) -> None:
        """Обрабатывает создание нового заказа."""
        order_id = event.payload.get("order_id")
        # Поддержка обоих вариантов ключей (для совместимости)
        pickup_lat = event.payload.get("pickup_lat") or event.payload.get("pickup_latitude")
        pickup_lon = event.payload.get("pickup_lon") or event.payload.get("pickup_longitude")
        
        if not all([order_id, pickup_lat, pickup_lon]):
            await log_error(
                f"Неполные данные в событии ORDER_CREATED",
                extra={"payload": event.payload},
            )
            return
        
        await log_info(
            f"Начинаем поиск водителей для заказа {order_id}",
            type_msg=TypeMsg.INFO,
        )
        
        # Создаём сервис матчинга
        matching_service = MatchingService(
            redis=self.redis,
            db=self.db,
        )
        
        # Ищем водителей
        drivers = await matching_service.find_drivers_incrementally(
            latitude=pickup_lat,
            longitude=pickup_lon,
        )
        
        if not drivers:
            await log_info(
                f"Водители не найдены для заказа {order_id}",
                type_msg=TypeMsg.WARNING,
            )
            return
        
        # Отправляем уведомления первым N водителям
        for candidate in drivers[:5]:
            await self.event_bus.publish(DomainEvent(
                event_type=EventTypes.DRIVER_ORDER_OFFERED,
                payload={
                    "order_id": order_id,
                    "driver_id": candidate.driver_id,
                    "distance": candidate.distance_km,
                },
            ))
        
        await log_info(
            f"Заказ {order_id} отправлен {len(drivers[:5])} водителям",
            type_msg=TypeMsg.INFO,
        )
    
    async def _handle_driver_declined(self, event: DomainEvent) -> None:
        """Обрабатывает отклонение заказа водителем."""
        order_id = event.payload.get("order_id")
        driver_id = event.payload.get("driver_id")
        
        await log_info(
            f"Водитель {driver_id} отклонил заказ {order_id}",
            type_msg=TypeMsg.INFO,
        )
        
        # Помечаем водителя как отклонившего
        await self.redis.sadd(
            f"order:{order_id}:declined_drivers",
            str(driver_id),
        )
        
        # Ищем следующего водителя
        # (логика повторного поиска)
