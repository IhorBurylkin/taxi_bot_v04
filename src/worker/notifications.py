# src/worker/notifications.py
"""
Воркер отправки уведомлений.
"""

from __future__ import annotations

from typing import List, Optional

from aiogram import Bot

from src.worker.base import BaseWorker
from src.infra.event_bus import DomainEvent, EventTypes
from src.config import settings
from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg


class NotificationWorker(BaseWorker):
    """
    Воркер для отправки уведомлений.
    Подписывается на события и отправляет Telegram-сообщения.
    """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._bot: Optional[Bot] = None
    
    @property
    def name(self) -> str:
        return "NotificationWorker"
    
    @property
    def subscriptions(self) -> List[str]:
        return [
            EventTypes.DRIVER_ORDER_OFFERED,
            EventTypes.ORDER_ACCEPTED,
            EventTypes.ORDER_CANCELLED,
            EventTypes.ORDER_COMPLETED,
            EventTypes.DRIVER_ARRIVED,
            EventTypes.RIDE_STARTED,
        ]
    
    async def start(self) -> None:
        """Запускает воркер с инициализацией бота."""
        self._bot = Bot(token=settings.telegram.bot_token)
        await super().start()
    
    async def stop(self) -> None:
        """Останавливает воркер."""
        await super().stop()
        if self._bot:
            await self._bot.session.close()
    
    async def handle_event(self, event: DomainEvent) -> None:
        """Обрабатывает событие."""
        handlers = {
            EventTypes.DRIVER_ORDER_OFFERED: self._notify_driver_new_order,
            EventTypes.ORDER_ACCEPTED: self._notify_order_accepted,
            EventTypes.ORDER_CANCELLED: self._notify_order_cancelled,
            EventTypes.ORDER_COMPLETED: self._notify_order_completed,
            EventTypes.DRIVER_ARRIVED: self._notify_driver_arrived,
            EventTypes.RIDE_STARTED: self._notify_ride_started,
        }
        
        handler = handlers.get(event.event_type)
        if handler:
            await handler(event.payload)
    
    async def _send_message(
        self,
        chat_id: int,
        text: str,
        **kwargs,
    ) -> bool:
        """
        Отправляет сообщение в Telegram.
        
        Args:
            chat_id: ID чата
            text: Текст сообщения
            **kwargs: Дополнительные параметры
            
        Returns:
            True если успешно
        """
        if not self._bot:
            await log_error("Bot не инициализирован")
            return False
        
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                **kwargs,
            )
            return True
        except Exception as e:
            await log_error(
                f"Ошибка отправки сообщения: {e}",
                extra={"chat_id": chat_id},
            )
            return False
    
    async def _notify_driver_new_order(self, payload: dict) -> None:
        """Уведомляет водителя о новом заказе."""
        driver_id = payload.get("driver_id")
        order_id = payload.get("order_id")
        distance = payload.get("distance", 0)
        
        text = (
            f"🚕 Новый заказ!\n\n"
            f"📍 Расстояние до точки: {distance:.1f} км\n"
            f"ID заказа: {order_id}\n\n"
            f"Принять заказ?"
        )
        
        await self._send_message(driver_id, text)
    
    async def _notify_order_accepted(self, payload: dict) -> None:
        """Уведомляет пассажира о принятии заказа."""
        passenger_id = payload.get("passenger_id")
        driver_name = payload.get("driver_name", "Водитель")
        car_info = payload.get("car_info", "")
        eta = payload.get("eta", 5)
        
        text = (
            f"✅ Заказ принят!\n\n"
            f"🚗 Водитель: {driver_name}\n"
            f"🚙 {car_info}\n"
            f"⏱ Примерное время прибытия: {eta} мин"
        )
        
        await self._send_message(passenger_id, text)
    
    async def _notify_order_cancelled(self, payload: dict) -> None:
        """Уведомляет о отмене заказа."""
        user_ids = payload.get("notify_users", [])
        reason = payload.get("reason", "")
        
        text = f"❌ Заказ отменён\n{reason}" if reason else "❌ Заказ отменён"
        
        for user_id in user_ids:
            await self._send_message(user_id, text)
    
    async def _notify_order_completed(self, payload: dict) -> None:
        """Уведомляет о завершении заказа."""
        passenger_id = payload.get("passenger_id")
        driver_id = payload.get("driver_id")
        fare = payload.get("fare", 0)
        
        passenger_text = (
            f"✅ Поездка завершена!\n\n"
            f"💰 Стоимость: {fare} ₽\n\n"
            f"Спасибо, что выбрали нас! ⭐"
        )
        
        driver_text = (
            f"✅ Поездка завершена!\n\n"
            f"💰 Заработано: {fare} ₽"
        )
        
        if passenger_id:
            await self._send_message(passenger_id, passenger_text)
        if driver_id:
            await self._send_message(driver_id, driver_text)
    
    async def _notify_driver_arrived(self, payload: dict) -> None:
        """Уведомляет пассажира о прибытии водителя."""
        passenger_id = payload.get("passenger_id")
        
        text = "📍 Водитель прибыл и ожидает вас!"
        
        if passenger_id:
            await self._send_message(passenger_id, text)
    
    async def _notify_ride_started(self, payload: dict) -> None:
        """Уведомляет о начале поездки."""
        passenger_id = payload.get("passenger_id")
        destination = payload.get("destination", "")
        
        text = f"🚀 Поездка началась!\n📍 Направление: {destination}"
        
        if passenger_id:
            await self._send_message(passenger_id, text)
