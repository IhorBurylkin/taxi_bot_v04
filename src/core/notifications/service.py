# src/core/notifications/service.py
"""
Сервис уведомлений.
Отправляет уведомления пользователям через Telegram.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.common.constants import TypeMsg
from src.common.logger import log_info, log_error
from src.common.localization import get_text
from src.infra.event_bus import EventBus, DomainEvent, EventTypes


@dataclass
class NotificationData:
    """Данные для уведомления."""
    user_id: int
    message_key: str  # Ключ из lang_dict
    language: str = "ru"
    kwargs: dict[str, Any] | None = None  # Параметры для форматирования
    reply_markup: Any | None = None  # Клавиатура


class NotificationService:
    """
    Сервис уведомлений.
    
    Публикует события уведомлений в шину событий.
    Фактическая отправка происходит в воркере или транспортном слое.
    """
    
    def __init__(self, event_bus: EventBus) -> None:
        """
        Инициализация сервиса.
        
        Args:
            event_bus: Шина событий
        """
        self._event_bus = event_bus
    
    async def send_notification(self, data: NotificationData) -> bool:
        """
        Отправляет уведомление пользователю.
        
        Args:
            data: Данные уведомления
            
        Returns:
            True если событие опубликовано
        """
        try:
            # Формируем текст сообщения
            text = get_text(
                data.message_key,
                data.language,
                **(data.kwargs or {}),
            )
            
            # Публикуем событие
            await self._event_bus.publish(DomainEvent(
                event_type=EventTypes.NOTIFICATION_SEND,
                payload={
                    "user_id": data.user_id,
                    "text": text,
                    "reply_markup": data.reply_markup,
                },
            ))
            
            await log_info(
                f"Уведомление поставлено в очередь: user={data.user_id}, key={data.message_key}",
                type_msg=TypeMsg.DEBUG,
            )
            
            return True
        except Exception as e:
            await log_error(f"Ошибка отправки уведомления: {e}")
            return False
    
    async def notify_order_created(
        self,
        passenger_id: int,
        language: str = "ru",
    ) -> bool:
        """
        Уведомление о создании заказа.
        
        Args:
            passenger_id: ID пассажира
            language: Язык
            
        Returns:
            True если успешно
        """
        return await self.send_notification(NotificationData(
            user_id=passenger_id,
            message_key="ORDER_CREATED",
            language=language,
        ))
    
    async def notify_driver_found(
        self,
        passenger_id: int,
        driver_name: str,
        car_info: str,
        language: str = "ru",
    ) -> bool:
        """
        Уведомление пассажиру о найденном водителе.
        
        Args:
            passenger_id: ID пассажира
            driver_name: Имя водителя
            car_info: Информация об автомобиле
            language: Язык
            
        Returns:
            True если успешно
        """
        return await self.send_notification(NotificationData(
            user_id=passenger_id,
            message_key="ORDER_ACCEPTED",
            language=language,
        ))
    
    async def notify_new_order(
        self,
        driver_id: int,
        pickup: str,
        destination: str,
        fare: float,
        currency: str,
        language: str = "ru",
    ) -> bool:
        """
        Уведомление водителю о новом заказе.
        
        Args:
            driver_id: ID водителя
            pickup: Адрес подачи
            destination: Адрес назначения
            fare: Стоимость
            currency: Валюта
            language: Язык
            
        Returns:
            True если успешно
        """
        return await self.send_notification(NotificationData(
            user_id=driver_id,
            message_key="NEW_ORDER_NOTIFICATION",
            language=language,
            kwargs={
                "pickup": pickup,
                "destination": destination,
                "fare": fare,
                "currency": currency,
            },
        ))
    
    async def notify_driver_arrived(
        self,
        passenger_id: int,
        language: str = "ru",
    ) -> bool:
        """
        Уведомление о прибытии водителя.
        
        Args:
            passenger_id: ID пассажира
            language: Язык
            
        Returns:
            True если успешно
        """
        return await self.send_notification(NotificationData(
            user_id=passenger_id,
            message_key="DRIVER_ARRIVED",
            language=language,
        ))
    
    async def notify_ride_started(
        self,
        passenger_id: int,
        language: str = "ru",
    ) -> bool:
        """
        Уведомление о начале поездки.
        
        Args:
            passenger_id: ID пассажира
            language: Язык
            
        Returns:
            True если успешно
        """
        return await self.send_notification(NotificationData(
            user_id=passenger_id,
            message_key="RIDE_STARTED",
            language=language,
        ))
    
    async def notify_order_completed(
        self,
        user_id: int,
        fare: float,
        currency: str,
        distance_km: float,
        duration_min: int,
        language: str = "ru",
    ) -> bool:
        """
        Уведомление о завершении поездки.
        
        Args:
            user_id: ID пользователя
            fare: Стоимость
            currency: Валюта
            distance_km: Расстояние
            duration_min: Время
            language: Язык
            
        Returns:
            True если успешно
        """
        return await self.send_notification(NotificationData(
            user_id=user_id,
            message_key="FARE_DETAILS",
            language=language,
            kwargs={
                "fare": fare,
                "currency": currency,
                "distance": distance_km,
                "duration": duration_min,
            },
        ))
    
    async def notify_order_cancelled(
        self,
        user_id: int,
        language: str = "ru",
    ) -> bool:
        """
        Уведомление об отмене заказа.
        
        Args:
            user_id: ID пользователя
            language: Язык
            
        Returns:
            True если успешно
        """
        return await self.send_notification(NotificationData(
            user_id=user_id,
            message_key="ORDER_CANCELLED",
            language=language,
        ))
    
    async def notify_no_drivers(
        self,
        passenger_id: int,
        language: str = "ru",
    ) -> bool:
        """
        Уведомление об отсутствии водителей.
        
        Args:
            passenger_id: ID пассажира
            language: Язык
            
        Returns:
            True если успешно
        """
        return await self.send_notification(NotificationData(
            user_id=passenger_id,
            message_key="NO_DRIVERS_AVAILABLE",
            language=language,
        ))
