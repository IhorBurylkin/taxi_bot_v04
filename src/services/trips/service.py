# src/services/trips/service.py
"""
Бизнес-логика Trip Service.
State machine для управления жизненным циклом поездки.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.common.constants import TypeMsg
from src.common.logger import log_info, log_error
from src.config import settings
from src.infra.database import DatabaseManager
from src.infra.redis_client import RedisClient
from src.infra.event_bus import EventBus
from src.shared.models.common import PaginationParams
from src.shared.models.trip import (
    TripDTO,
    TripStatus,
    TripCreateRequest,
    TripSearchParams,
    LocationDTO,
    FareDTO,
)
from src.shared.events.trip_events import (
    TripCreated,
    TripStatusChanged,
    TripCompleted,
    TripCancelled,
    MatchRequested,
    DriverArrived,
    RideStarted,
)


class TripStateMachine:
    """
    State machine для переходов между статусами поездки.
    
    Допустимые переходы:
    - pending → matching → accepted → driver_arrived → in_progress → completed
    - pending → cancelled
    - matching → cancelled, expired
    - accepted → cancelled, driver_arrived
    - driver_arrived → cancelled, in_progress
    - in_progress → completed, cancelled
    """
    
    VALID_TRANSITIONS: dict[TripStatus, list[TripStatus]] = {
        TripStatus.PENDING: [TripStatus.MATCHING, TripStatus.CANCELLED],
        TripStatus.MATCHING: [TripStatus.ACCEPTED, TripStatus.CANCELLED, TripStatus.EXPIRED],
        TripStatus.ACCEPTED: [TripStatus.DRIVER_ARRIVED, TripStatus.CANCELLED],
        TripStatus.DRIVER_ARRIVED: [TripStatus.IN_PROGRESS, TripStatus.CANCELLED],
        TripStatus.IN_PROGRESS: [TripStatus.COMPLETED, TripStatus.CANCELLED],
        TripStatus.COMPLETED: [],
        TripStatus.CANCELLED: [],
        TripStatus.EXPIRED: [],
    }
    
    @classmethod
    def can_transition(cls, from_status: TripStatus, to_status: TripStatus) -> bool:
        """Проверяет, допустим ли переход."""
        allowed = cls.VALID_TRANSITIONS.get(from_status, [])
        return to_status in allowed
    
    @classmethod
    def validate_transition(cls, from_status: TripStatus, to_status: TripStatus) -> None:
        """Проверяет переход и выбрасывает исключение при ошибке."""
        if not cls.can_transition(from_status, to_status):
            raise ValueError(
                f"Недопустимый переход: {from_status.value} → {to_status.value}"
            )


class TripService:
    """Сервис управления поездками."""
    
    def __init__(
        self,
        db: DatabaseManager,
        redis: RedisClient,
        event_bus: EventBus,
    ) -> None:
        self._db = db
        self._redis = redis
        self._event_bus = event_bus
    
    def _cache_key(self, trip_id: str) -> str:
        """Ключ кэша для поездки."""
        return f"trip:{trip_id}"
    
    async def _save_trip_event(
        self,
        trip_id: str,
        event_type: str,
        data: dict,
    ) -> None:
        """Сохранение события в историю поездки."""
        query = """
            INSERT INTO trip_events (trip_id, event_type, event_data, created_at)
            VALUES ($1, $2, $3, NOW())
        """
        import json
        await self._db.execute(query, trip_id, event_type, json.dumps(data))
    
    async def get_trip(self, trip_id: str) -> Optional[TripDTO]:
        """Получение поездки по ID."""
        cache_key = self._cache_key(trip_id)
        
        # Проверяем кэш
        cached = await self._redis.get(cache_key)
        if cached:
            return TripDTO.model_validate_json(cached)
        
        query = """
            SELECT id, rider_id, driver_id,
                   pickup_lat, pickup_lon, pickup_address,
                   dropoff_lat, dropoff_lon, dropoff_address,
                   distance_km, duration_minutes,
                   base_fare, distance_fare, time_fare, pickup_fare,
                   waiting_fare, surge_multiplier, total_fare, currency,
                   status, created_at, accepted_at, driver_arrived_at,
                   started_at, completed_at, cancelled_at,
                   rider_rating, driver_rating
            FROM trips
            WHERE id = $1
        """
        
        row = await self._db.fetchrow(query, trip_id)
        
        if not row:
            return None
        
        trip = self._row_to_dto(row)
        
        # Кэшируем активные поездки
        if trip.status not in [TripStatus.COMPLETED, TripStatus.CANCELLED, TripStatus.EXPIRED]:
            await self._redis.set_model(
                cache_key,
                trip,
                ttl=settings.redis_ttl.ORDER_TTL,
            )
        
        return trip
    
    def _row_to_dto(self, row: dict) -> TripDTO:
        """Преобразование строки БД в DTO."""
        fare = None
        if row.get("total_fare") is not None:
            fare = FareDTO(
                base_fare=row.get("base_fare", 0) or 0,
                distance_fare=row.get("distance_fare", 0) or 0,
                time_fare=row.get("time_fare", 0) or 0,
                pickup_fare=row.get("pickup_fare", 0) or 0,
                waiting_fare=row.get("waiting_fare", 0) or 0,
                surge_multiplier=row.get("surge_multiplier", 1.0) or 1.0,
                total_fare=row.get("total_fare", 0) or 0,
                currency=row.get("currency", "EUR") or "EUR",
            )
        
        return TripDTO(
            id=row["id"],
            rider_id=row["rider_id"],
            driver_id=row.get("driver_id"),
            pickup=LocationDTO(
                latitude=row["pickup_lat"],
                longitude=row["pickup_lon"],
                address=row.get("pickup_address"),
            ),
            dropoff=LocationDTO(
                latitude=row["dropoff_lat"],
                longitude=row["dropoff_lon"],
                address=row.get("dropoff_address"),
            ),
            distance_km=row.get("distance_km"),
            duration_minutes=row.get("duration_minutes"),
            fare=fare,
            status=TripStatus(row["status"]),
            created_at=row.get("created_at"),
            accepted_at=row.get("accepted_at"),
            driver_arrived_at=row.get("driver_arrived_at"),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            cancelled_at=row.get("cancelled_at"),
            rider_rating=row.get("rider_rating"),
            driver_rating=row.get("driver_rating"),
        )
    
    async def create_trip(self, request: TripCreateRequest) -> TripDTO:
        """Создание новой поездки."""
        trip_id = str(uuid4())
        
        query = """
            INSERT INTO trips (
                id, rider_id, 
                pickup_lat, pickup_lon, pickup_address,
                dropoff_lat, dropoff_lon, dropoff_address,
                distance_km, duration_minutes,
                status, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'pending', NOW())
            RETURNING id, rider_id, driver_id,
                      pickup_lat, pickup_lon, pickup_address,
                      dropoff_lat, dropoff_lon, dropoff_address,
                      distance_km, duration_minutes,
                      base_fare, distance_fare, time_fare, pickup_fare,
                      waiting_fare, surge_multiplier, total_fare, currency,
                      status, created_at, accepted_at, driver_arrived_at,
                      started_at, completed_at, cancelled_at,
                      rider_rating, driver_rating
        """
        
        row = await self._db.fetchrow(
            query,
            trip_id,
            request.rider_id,
            request.pickup.latitude,
            request.pickup.longitude,
            request.pickup.address,
            request.dropoff.latitude,
            request.dropoff.longitude,
            request.dropoff.address,
            request.distance_km,
            request.duration_minutes,
        )
        
        trip = self._row_to_dto(row)
        
        # Сохраняем событие
        await self._save_trip_event(trip_id, "trip.created", {
            "rider_id": request.rider_id,
            "pickup": request.pickup.model_dump(),
            "dropoff": request.dropoff.model_dump(),
        })
        
        # Публикуем событие в RabbitMQ
        event = TripCreated(
            trip_id=trip_id,
            rider_id=request.rider_id,
            pickup_lat=request.pickup.latitude,
            pickup_lon=request.pickup.longitude,
            pickup_address=request.pickup.address,
            dropoff_lat=request.dropoff.latitude,
            dropoff_lon=request.dropoff.longitude,
            dropoff_address=request.dropoff.address,
            distance_km=request.distance_km,
            duration_minutes=request.duration_minutes,
        )
        await self._event_bus.publish(event.event_type, event.to_json())
        
        await log_info(f"Поездка создана: {trip_id}", type_msg=TypeMsg.INFO)
        
        return trip
    
    async def list_trips(
        self,
        params: TripSearchParams,
        pagination: PaginationParams,
    ) -> list[TripDTO]:
        """Список поездок с фильтрацией."""
        conditions = ["1=1"]
        values = []
        idx = 1
        
        if params.rider_id:
            conditions.append(f"rider_id = ${idx}")
            values.append(params.rider_id)
            idx += 1
        
        if params.driver_id:
            conditions.append(f"driver_id = ${idx}")
            values.append(params.driver_id)
            idx += 1
        
        if params.status:
            conditions.append(f"status = ${idx}")
            values.append(params.status.value)
            idx += 1
        
        query = f"""
            SELECT id, rider_id, driver_id,
                   pickup_lat, pickup_lon, pickup_address,
                   dropoff_lat, dropoff_lon, dropoff_address,
                   distance_km, duration_minutes,
                   base_fare, distance_fare, time_fare, pickup_fare,
                   waiting_fare, surge_multiplier, total_fare, currency,
                   status, created_at, accepted_at, driver_arrived_at,
                   started_at, completed_at, cancelled_at,
                   rider_rating, driver_rating
            FROM trips
            WHERE {" AND ".join(conditions)}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        values.extend([pagination.limit, pagination.offset])
        
        rows = await self._db.fetch(query, *values)
        return [self._row_to_dto(row) for row in rows]
    
    async def get_active_trip_for_rider(self, rider_id: int) -> Optional[TripDTO]:
        """Получение активной поездки пассажира."""
        active_statuses = [
            TripStatus.PENDING.value,
            TripStatus.MATCHING.value,
            TripStatus.ACCEPTED.value,
            TripStatus.DRIVER_ARRIVED.value,
            TripStatus.IN_PROGRESS.value,
        ]
        
        query = """
            SELECT id FROM trips
            WHERE rider_id = $1 AND status = ANY($2)
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        row = await self._db.fetchrow(query, rider_id, active_statuses)
        
        if not row:
            return None
        
        return await self.get_trip(row["id"])
    
    async def get_active_trip_for_driver(self, driver_id: int) -> Optional[TripDTO]:
        """Получение активной поездки водителя."""
        active_statuses = [
            TripStatus.ACCEPTED.value,
            TripStatus.DRIVER_ARRIVED.value,
            TripStatus.IN_PROGRESS.value,
        ]
        
        query = """
            SELECT id FROM trips
            WHERE driver_id = $1 AND status = ANY($2)
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        row = await self._db.fetchrow(query, driver_id, active_statuses)
        
        if not row:
            return None
        
        return await self.get_trip(row["id"])
    
    async def _update_status(
        self,
        trip_id: str,
        new_status: TripStatus,
        extra_updates: dict | None = None,
    ) -> Optional[TripDTO]:
        """Обновление статуса поездки с валидацией перехода."""
        trip = await self.get_trip(trip_id)
        if not trip:
            return None
        
        # Валидируем переход
        TripStateMachine.validate_transition(trip.status, new_status)
        
        # Формируем запрос
        updates = ["status = $2"]
        values = [trip_id, new_status.value]
        idx = 3
        
        # Добавляем timestamp для соответствующего статуса
        timestamp_field = {
            TripStatus.ACCEPTED: "accepted_at",
            TripStatus.DRIVER_ARRIVED: "driver_arrived_at",
            TripStatus.IN_PROGRESS: "started_at",
            TripStatus.COMPLETED: "completed_at",
            TripStatus.CANCELLED: "cancelled_at",
        }.get(new_status)
        
        if timestamp_field:
            updates.append(f"{timestamp_field} = NOW()")
        
        # Дополнительные обновления
        if extra_updates:
            for key, value in extra_updates.items():
                updates.append(f"{key} = ${idx}")
                values.append(value)
                idx += 1
        
        query = f"""
            UPDATE trips
            SET {", ".join(updates)}
            WHERE id = $1
            RETURNING id, rider_id, driver_id,
                      pickup_lat, pickup_lon, pickup_address,
                      dropoff_lat, dropoff_lon, dropoff_address,
                      distance_km, duration_minutes,
                      base_fare, distance_fare, time_fare, pickup_fare,
                      waiting_fare, surge_multiplier, total_fare, currency,
                      status, created_at, accepted_at, driver_arrived_at,
                      started_at, completed_at, cancelled_at,
                      rider_rating, driver_rating
        """
        
        row = await self._db.fetchrow(query, *values)
        
        if not row:
            return None
        
        updated_trip = self._row_to_dto(row)
        
        # Инвалидируем кэш
        await self._redis.delete(self._cache_key(trip_id))
        
        # Сохраняем событие
        await self._save_trip_event(trip_id, f"trip.{new_status.value}", {
            "old_status": trip.status.value,
            "new_status": new_status.value,
            **(extra_updates or {}),
        })
        
        # Публикуем событие
        event = TripStatusChanged(
            trip_id=trip_id,
            old_status=trip.status.value,
            new_status=new_status.value,
            driver_id=updated_trip.driver_id,
        )
        await self._event_bus.publish(event.event_type, event.to_json())
        
        return updated_trip
    
    async def accept_trip(self, trip_id: str, driver_id: int) -> Optional[TripDTO]:
        """Водитель принимает заказ."""
        return await self._update_status(
            trip_id,
            TripStatus.ACCEPTED,
            extra_updates={"driver_id": driver_id},
        )
    
    async def driver_arrived(self, trip_id: str) -> Optional[TripDTO]:
        """Водитель прибыл к точке посадки."""
        trip = await self._update_status(trip_id, TripStatus.DRIVER_ARRIVED)
        
        if trip:
            event = DriverArrived(
                trip_id=trip_id,
                driver_id=trip.driver_id,
                arrival_lat=trip.pickup.latitude,
                arrival_lon=trip.pickup.longitude,
            )
            await self._event_bus.publish(event.event_type, event.to_json())
        
        return trip
    
    async def start_trip(self, trip_id: str) -> Optional[TripDTO]:
        """Начало поездки."""
        trip = await self._update_status(trip_id, TripStatus.IN_PROGRESS)
        
        if trip:
            event = RideStarted(
                trip_id=trip_id,
                driver_id=trip.driver_id,
                rider_id=trip.rider_id,
                start_lat=trip.pickup.latitude,
                start_lon=trip.pickup.longitude,
            )
            await self._event_bus.publish(event.event_type, event.to_json())
        
        return trip
    
    async def complete_trip(
        self,
        trip_id: str,
        final_fare: float | None = None,
    ) -> Optional[TripDTO]:
        """Завершение поездки."""
        extra = {}
        if final_fare is not None:
            extra["total_fare"] = final_fare
        
        trip = await self._update_status(
            trip_id,
            TripStatus.COMPLETED,
            extra_updates=extra if extra else None,
        )
        
        if trip:
            event = TripCompleted(
                trip_id=trip_id,
                rider_id=trip.rider_id,
                driver_id=trip.driver_id,
                final_fare=trip.fare.total_fare if trip.fare else 0,
                currency=trip.fare.currency if trip.fare else "EUR",
                distance_km=trip.distance_km or 0,
                duration_minutes=trip.duration_minutes or 0,
            )
            await self._event_bus.publish(event.event_type, event.to_json())
            
            await log_info(f"Поездка завершена: {trip_id}", type_msg=TypeMsg.INFO)
        
        return trip
    
    async def cancel_trip(
        self,
        trip_id: str,
        cancelled_by: str = "rider",
        reason: str | None = None,
    ) -> Optional[TripDTO]:
        """Отмена поездки."""
        trip = await self._update_status(trip_id, TripStatus.CANCELLED)
        
        if trip:
            event = TripCancelled(
                trip_id=trip_id,
                cancelled_by=cancelled_by,
                cancellation_reason=reason,
            )
            await self._event_bus.publish(event.event_type, event.to_json())
            
            await log_info(
                f"Поездка отменена: {trip_id} (by {cancelled_by})",
                type_msg=TypeMsg.WARNING,
            )
        
        return trip
    
    async def get_trip_events(self, trip_id: str) -> list[dict]:
        """Получение истории событий поездки."""
        query = """
            SELECT event_type, event_data, created_at
            FROM trip_events
            WHERE trip_id = $1
            ORDER BY created_at ASC
        """
        
        rows = await self._db.fetch(query, trip_id)
        
        import json
        return [
            {
                "event_type": row["event_type"],
                "data": json.loads(row["event_data"]) if row["event_data"] else {},
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]
