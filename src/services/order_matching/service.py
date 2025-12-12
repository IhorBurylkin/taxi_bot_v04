# src/services/order_matching/service.py
"""
Бизнес-логика матчинга заказов с водителями.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.shared.events.trip_events import (
    MatchRequested,
    OfferCreated,
    OfferAccepted,
    OfferExpired,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from src.infra.event_bus import EventBus


class OfferStatus(str, Enum):
    """Статус предложения водителю."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class DriverOffer:
    """Предложение водителю."""
    offer_id: str
    trip_id: str
    driver_id: int
    distance_km: float
    fare_amount: float
    pickup_address: str
    dropoff_address: str
    status: OfferStatus = OfferStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    responded_at: datetime | None = None


class MatchingService:
    """
    Сервис матчинга заказов с водителями.
    
    Алгоритм:
    1. Получить список ближайших online-водителей
    2. Отфильтровать занятых и отклонивших
    3. Отправить предложение ближайшему
    4. Ждать ответа (таймаут 30 сек)
    5. Если отклонил/таймаут — следующему
    6. Расширить радиус если нужно
    """
    
    # Ключи Redis
    NOTIFIED_DRIVERS_KEY = "trip:{trip_id}:notified"
    REJECTED_DRIVERS_KEY = "trip:{trip_id}:rejected"
    ACTIVE_OFFER_KEY = "trip:{trip_id}:active_offer"
    DRIVER_CURRENT_OFFER_KEY = "driver:{driver_id}:current_offer"
    
    # Константы из конфига
    OFFER_TIMEOUT_SECONDS = 30
    MAX_DRIVERS_TO_NOTIFY = 10
    SEARCH_RADIUS_MIN_KM = 1.0
    SEARCH_RADIUS_MAX_KM = 10.0
    SEARCH_RADIUS_STEP_KM = 1.0
    MAX_SEARCH_RETRIES = 3
    
    def __init__(
        self,
        redis: "Redis",
        event_bus: "EventBus",
        location_service_url: str = "http://localhost:8090",
        users_service_url: str = "http://localhost:8084",
        trips_service_url: str = "http://localhost:8085",
    ) -> None:
        self._redis = redis
        self._event_bus = event_bus
        self._location_url = location_service_url
        self._users_url = users_service_url
        self._trips_url = trips_service_url
        
        # HTTP клиент
        import httpx
        self._http = httpx.AsyncClient(timeout=10.0)
        
        # Активные задачи матчинга
        self._matching_tasks: dict[str, asyncio.Task] = {}
    
    async def close(self) -> None:
        """Закрыть ресурсы."""
        await self._http.aclose()
        
        # Отменяем все задачи
        for task in self._matching_tasks.values():
            task.cancel()
    
    async def start_matching(
        self,
        trip_id: str,
        pickup_lat: float,
        pickup_lon: float,
        pickup_address: str,
        dropoff_address: str,
        fare_amount: float,
        vehicle_class: str = "standard",
    ) -> str:
        """
        Начать поиск водителя для заказа.
        
        Запускает асинхронную задачу матчинга.
        
        Returns:
            matching_id для отслеживания
        """
        matching_id = str(uuid.uuid4())
        
        # Публикуем событие начала поиска
        event = MatchRequested(
            trip_id=trip_id,
            pickup_lat=pickup_lat,
            pickup_lon=pickup_lon,
            vehicle_class=vehicle_class,
        )
        await self._event_bus.publish("match.requested", event.model_dump())
        
        # Запускаем задачу матчинга
        task = asyncio.create_task(
            self._matching_loop(
                trip_id=trip_id,
                pickup_lat=pickup_lat,
                pickup_lon=pickup_lon,
                pickup_address=pickup_address,
                dropoff_address=dropoff_address,
                fare_amount=fare_amount,
                vehicle_class=vehicle_class,
            )
        )
        self._matching_tasks[trip_id] = task
        
        return matching_id
    
    async def cancel_matching(self, trip_id: str) -> None:
        """Отменить поиск водителя."""
        if trip_id in self._matching_tasks:
            self._matching_tasks[trip_id].cancel()
            del self._matching_tasks[trip_id]
        
        # Очищаем данные в Redis
        await self._redis.delete(
            self.NOTIFIED_DRIVERS_KEY.format(trip_id=trip_id),
            self.REJECTED_DRIVERS_KEY.format(trip_id=trip_id),
            self.ACTIVE_OFFER_KEY.format(trip_id=trip_id),
        )
    
    async def handle_driver_response(
        self,
        trip_id: str,
        driver_id: int,
        accepted: bool,
    ) -> dict[str, Any]:
        """
        Обработать ответ водителя на предложение.
        
        Returns:
            Результат обработки
        """
        # Проверяем что предложение активно
        offer_key = self.ACTIVE_OFFER_KEY.format(trip_id=trip_id)
        offer_data = await self._redis.hgetall(offer_key)
        
        if not offer_data:
            return {"error": "No active offer", "status": "failed"}
        
        offer_driver_id = int(offer_data.get(b"driver_id", 0))
        if offer_driver_id != driver_id:
            return {"error": "Offer not for this driver", "status": "failed"}
        
        offer_id = offer_data.get(b"offer_id", b"").decode()
        
        if accepted:
            # Водитель принял заказ
            await self._accept_offer(trip_id, driver_id, offer_id)
            return {"status": "accepted", "trip_id": trip_id, "driver_id": driver_id}
        else:
            # Водитель отклонил
            await self._reject_offer(trip_id, driver_id, offer_id)
            return {"status": "rejected", "trip_id": trip_id}
    
    async def get_offer_for_driver(self, driver_id: int) -> dict[str, Any] | None:
        """Получить текущее предложение для водителя."""
        offer_key = self.DRIVER_CURRENT_OFFER_KEY.format(driver_id=driver_id)
        data = await self._redis.hgetall(offer_key)
        
        if not data:
            return None
        
        return {
            "offer_id": data.get(b"offer_id", b"").decode(),
            "trip_id": data.get(b"trip_id", b"").decode(),
            "pickup_address": data.get(b"pickup_address", b"").decode(),
            "dropoff_address": data.get(b"dropoff_address", b"").decode(),
            "fare_amount": float(data.get(b"fare_amount", 0)),
            "distance_km": float(data.get(b"distance_km", 0)),
            "expires_at": data.get(b"expires_at", b"").decode(),
        }
    
    # === ПРИВАТНЫЕ МЕТОДЫ ===
    
    async def _matching_loop(
        self,
        trip_id: str,
        pickup_lat: float,
        pickup_lon: float,
        pickup_address: str,
        dropoff_address: str,
        fare_amount: float,
        vehicle_class: str,
    ) -> None:
        """Основной цикл поиска водителя."""
        current_radius = self.SEARCH_RADIUS_MIN_KM
        retries = 0
        
        try:
            while retries < self.MAX_SEARCH_RETRIES:
                # 1. Получаем ближайших водителей
                drivers = await self._get_nearby_drivers(
                    pickup_lat, pickup_lon, current_radius
                )
                
                # 2. Фильтруем уже уведомлённых и отклонивших
                available_drivers = await self._filter_available_drivers(
                    trip_id, drivers
                )
                
                if not available_drivers:
                    # Расширяем радиус
                    current_radius = min(
                        current_radius + self.SEARCH_RADIUS_STEP_KM,
                        self.SEARCH_RADIUS_MAX_KM,
                    )
                    retries += 1
                    await asyncio.sleep(5)  # Пауза перед следующей попыткой
                    continue
                
                # 3. Отправляем предложение ближайшему
                driver = available_drivers[0]
                offer_accepted = await self._send_offer(
                    trip_id=trip_id,
                    driver_id=driver["driver_id"],
                    distance_km=driver["distance_km"],
                    pickup_address=pickup_address,
                    dropoff_address=dropoff_address,
                    fare_amount=fare_amount,
                )
                
                if offer_accepted:
                    # Водитель найден!
                    return
                
                # Продолжаем поиск
                retries = 0  # Сбрасываем счётчик если были водители
                
        except asyncio.CancelledError:
            pass
        finally:
            # Очищаем задачу
            if trip_id in self._matching_tasks:
                del self._matching_tasks[trip_id]
    
    async def _get_nearby_drivers(
        self,
        lat: float,
        lon: float,
        radius_km: float,
    ) -> list[dict[str, Any]]:
        """Получить ближайших водителей через Location Ingest."""
        try:
            response = await self._http.get(
                f"{self._location_url}/api/v1/location/nearby",
                params={
                    "lat": lat,
                    "lon": lon,
                    "radius_km": radius_km,
                    "limit": self.MAX_DRIVERS_TO_NOTIFY,
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return []
    
    async def _filter_available_drivers(
        self,
        trip_id: str,
        drivers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Отфильтровать недоступных водителей."""
        if not drivers:
            return []
        
        notified_key = self.NOTIFIED_DRIVERS_KEY.format(trip_id=trip_id)
        rejected_key = self.REJECTED_DRIVERS_KEY.format(trip_id=trip_id)
        
        notified = await self._redis.smembers(notified_key)
        rejected = await self._redis.smembers(rejected_key)
        
        excluded = {int(d) for d in notified | rejected}
        
        return [d for d in drivers if d["driver_id"] not in excluded]
    
    async def _send_offer(
        self,
        trip_id: str,
        driver_id: int,
        distance_km: float,
        pickup_address: str,
        dropoff_address: str,
        fare_amount: float,
    ) -> bool:
        """
        Отправить предложение водителю и ждать ответа.
        
        Returns:
            True если водитель принял, False если отклонил/таймаут
        """
        offer_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(seconds=self.OFFER_TIMEOUT_SECONDS)
        
        # Сохраняем предложение в Redis
        offer_data = {
            "offer_id": offer_id,
            "trip_id": trip_id,
            "driver_id": str(driver_id),
            "distance_km": str(distance_km),
            "pickup_address": pickup_address,
            "dropoff_address": dropoff_address,
            "fare_amount": str(fare_amount),
            "expires_at": expires_at.isoformat(),
            "status": OfferStatus.PENDING.value,
        }
        
        pipe = self._redis.pipeline()
        
        # Активное предложение для поездки
        offer_key = self.ACTIVE_OFFER_KEY.format(trip_id=trip_id)
        pipe.hset(offer_key, mapping=offer_data)
        pipe.expire(offer_key, self.OFFER_TIMEOUT_SECONDS + 5)
        
        # Текущее предложение для водителя
        driver_offer_key = self.DRIVER_CURRENT_OFFER_KEY.format(driver_id=driver_id)
        pipe.hset(driver_offer_key, mapping=offer_data)
        pipe.expire(driver_offer_key, self.OFFER_TIMEOUT_SECONDS + 5)
        
        # Добавляем в список уведомлённых
        notified_key = self.NOTIFIED_DRIVERS_KEY.format(trip_id=trip_id)
        pipe.sadd(notified_key, str(driver_id))
        pipe.expire(notified_key, 86400)  # 24 часа
        
        await pipe.execute()
        
        # Публикуем событие создания предложения
        event = OfferCreated(
            offer_id=offer_id,
            trip_id=trip_id,
            driver_id=driver_id,
            expires_at=expires_at,
        )
        await self._event_bus.publish("offer.created", event.model_dump())
        
        # TODO: Отправить уведомление водителю через Telegram/Push
        
        # Ждём ответа с таймаутом
        for _ in range(self.OFFER_TIMEOUT_SECONDS):
            await asyncio.sleep(1)
            
            # Проверяем статус предложения
            current_status = await self._redis.hget(offer_key, "status")
            if current_status:
                status = current_status.decode()
                if status == OfferStatus.ACCEPTED.value:
                    return True
                if status == OfferStatus.REJECTED.value:
                    return False
        
        # Таймаут — предложение истекло
        await self._expire_offer(trip_id, driver_id, offer_id)
        return False
    
    async def _accept_offer(
        self,
        trip_id: str,
        driver_id: int,
        offer_id: str,
    ) -> None:
        """Обработать принятие предложения."""
        # Обновляем статус в Redis
        offer_key = self.ACTIVE_OFFER_KEY.format(trip_id=trip_id)
        await self._redis.hset(offer_key, "status", OfferStatus.ACCEPTED.value)
        
        # Удаляем предложение у водителя
        driver_offer_key = self.DRIVER_CURRENT_OFFER_KEY.format(driver_id=driver_id)
        await self._redis.delete(driver_offer_key)
        
        # Обновляем поездку через Trip Service
        try:
            await self._http.post(
                f"{self._trips_url}/api/v1/trips/{trip_id}/accept",
                params={"driver_id": driver_id},
            )
        except Exception:
            pass
        
        # Публикуем событие
        event = OfferAccepted(
            offer_id=offer_id,
            trip_id=trip_id,
            driver_id=driver_id,
        )
        await self._event_bus.publish("offer.accepted", event.model_dump())
    
    async def _reject_offer(
        self,
        trip_id: str,
        driver_id: int,
        offer_id: str,
    ) -> None:
        """Обработать отклонение предложения."""
        # Обновляем статус
        offer_key = self.ACTIVE_OFFER_KEY.format(trip_id=trip_id)
        await self._redis.hset(offer_key, "status", OfferStatus.REJECTED.value)
        
        # Добавляем в отклонившие
        rejected_key = self.REJECTED_DRIVERS_KEY.format(trip_id=trip_id)
        await self._redis.sadd(rejected_key, str(driver_id))
        await self._redis.expire(rejected_key, 86400)
        
        # Удаляем предложение у водителя
        driver_offer_key = self.DRIVER_CURRENT_OFFER_KEY.format(driver_id=driver_id)
        await self._redis.delete(driver_offer_key)
    
    async def _expire_offer(
        self,
        trip_id: str,
        driver_id: int,
        offer_id: str,
    ) -> None:
        """Обработать истечение предложения."""
        # Обновляем статус
        offer_key = self.ACTIVE_OFFER_KEY.format(trip_id=trip_id)
        await self._redis.hset(offer_key, "status", OfferStatus.EXPIRED.value)
        
        # Удаляем предложение у водителя
        driver_offer_key = self.DRIVER_CURRENT_OFFER_KEY.format(driver_id=driver_id)
        await self._redis.delete(driver_offer_key)
        
        # Публикуем событие
        event = OfferExpired(
            offer_id=offer_id,
            trip_id=trip_id,
            driver_id=driver_id,
        )
        await self._event_bus.publish("offer.expired", event.model_dump())
