# src/services/users/service.py
"""
Бизнес-логика Users Service.
Адаптирована из src/core/users/service.py.
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
from src.infra.event_bus import EventBus, DomainEvent, EventTypes
from src.shared.models.user import (
    UserDTO,
    DriverDTO,
    UserRole,
    DriverStatus,
    UserCreateRequest,
    DriverCreateRequest,
    DriverLocationUpdate,
)
from src.shared.events.user_events import (
    UserRegistered,
    UserProfileUpdated,
    UserBlocked,
    UserUnblocked,
    DriverStatusChanged,
)


class UserService:
    """Сервис управления пользователями."""
    
    def __init__(
        self,
        db: DatabaseManager,
        redis: RedisClient,
        event_bus: EventBus,
    ) -> None:
        self._db = db
        self._redis = redis
        self._event_bus = event_bus
    
    def _cache_key(self, telegram_id: int) -> str:
        """Ключ кэша для пользователя."""
        return f"user:{telegram_id}"
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserDTO]:
        """Получение пользователя по telegram_id с кэшированием."""
        cache_key = self._cache_key(telegram_id)
        
        # Проверяем кэш
        cached = await self._redis.get(cache_key)
        if cached:
            return UserDTO.model_validate_json(cached)
        
        # Читаем из БД
        query = """
            SELECT id, telegram_id, username, first_name, last_name,
                   phone, language_code, role, is_active, is_blocked,
                   created_at, updated_at
            FROM users
            WHERE telegram_id = $1
        """
        row = await self._db.fetchrow(query, telegram_id)
        
        if not row:
            return None
        
        user = UserDTO(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            language_code=row["language_code"],
            role=UserRole(row["role"]),
            is_active=row["is_active"],
            is_blocked=row["is_blocked"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        
        # Кэшируем
        await self._redis.set(
            cache_key,
            user.model_dump_json(),
            ex=settings.redis_ttl.PROFILE_TTL,
        )
        
        return user
    
    async def create_user(self, request: UserCreateRequest) -> UserDTO:
        """Создание нового пользователя."""
        query = """
            INSERT INTO users (telegram_id, username, first_name, last_name, 
                              phone, language_code, role, is_active, is_blocked,
                              created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, true, false, NOW(), NOW())
            RETURNING id, telegram_id, username, first_name, last_name,
                      phone, language_code, role, is_active, is_blocked,
                      created_at, updated_at
        """
        
        row = await self._db.fetchrow(
            query,
            request.telegram_id,
            request.username,
            request.first_name,
            request.last_name,
            request.phone,
            request.language_code,
            request.role.value,
        )
        
        user = UserDTO(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            language_code=row["language_code"],
            role=UserRole(row["role"]),
            is_active=row["is_active"],
            is_blocked=row["is_blocked"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        
        # Публикуем событие
        event = UserRegistered(
            user_id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
            role=user.role.value,
        )
        await self._event_bus.publish(event.event_type, event.to_json())
        
        await log_info(
            f"Пользователь создан: {user.telegram_id}",
            type_msg=TypeMsg.INFO,
        )
        
        return user
    
    async def update_user(
        self,
        telegram_id: int,
        updates: dict,
    ) -> Optional[UserDTO]:
        """Обновление профиля пользователя."""
        if not updates:
            return await self.get_by_telegram_id(telegram_id)
        
        # Формируем SET clause
        set_parts = []
        values = []
        idx = 1
        
        allowed_fields = {"username", "first_name", "last_name", "phone", "language_code"}
        for key, value in updates.items():
            if key in allowed_fields:
                set_parts.append(f"{key} = ${idx}")
                values.append(value)
                idx += 1
        
        if not set_parts:
            return await self.get_by_telegram_id(telegram_id)
        
        set_parts.append(f"updated_at = NOW()")
        values.append(telegram_id)
        
        query = f"""
            UPDATE users
            SET {", ".join(set_parts)}
            WHERE telegram_id = ${idx}
            RETURNING id, telegram_id, username, first_name, last_name,
                      phone, language_code, role, is_active, is_blocked,
                      created_at, updated_at
        """
        
        row = await self._db.fetchrow(query, *values)
        
        if not row:
            return None
        
        user = UserDTO(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            language_code=row["language_code"],
            role=UserRole(row["role"]),
            is_active=row["is_active"],
            is_blocked=row["is_blocked"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        
        # Инвалидируем кэш
        await self._redis.delete(self._cache_key(telegram_id))
        
        # Публикуем событие
        event = UserProfileUpdated(
            user_id=user.id,
            updated_fields=updates,
        )
        await self._event_bus.publish(event.event_type, event.to_json())
        
        return user
    
    async def block_user(
        self,
        telegram_id: int,
        reason: str | None = None,
    ) -> Optional[UserDTO]:
        """Блокировка пользователя."""
        query = """
            UPDATE users
            SET is_blocked = true, updated_at = NOW()
            WHERE telegram_id = $1
            RETURNING id, telegram_id, username, first_name, last_name,
                      phone, language_code, role, is_active, is_blocked,
                      created_at, updated_at
        """
        
        row = await self._db.fetchrow(query, telegram_id)
        
        if not row:
            return None
        
        user = UserDTO(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            language_code=row["language_code"],
            role=UserRole(row["role"]),
            is_active=row["is_active"],
            is_blocked=row["is_blocked"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        
        # Инвалидируем кэш
        await self._redis.delete(self._cache_key(telegram_id))
        
        # Публикуем событие
        event = UserBlocked(
            user_id=user.id,
            reason=reason,
        )
        await self._event_bus.publish(event.event_type, event.to_json())
        
        await log_info(
            f"Пользователь заблокирован: {telegram_id}",
            type_msg=TypeMsg.WARNING,
        )
        
        return user
    
    async def unblock_user(self, telegram_id: int) -> Optional[UserDTO]:
        """Разблокировка пользователя."""
        query = """
            UPDATE users
            SET is_blocked = false, updated_at = NOW()
            WHERE telegram_id = $1
            RETURNING id, telegram_id, username, first_name, last_name,
                      phone, language_code, role, is_active, is_blocked,
                      created_at, updated_at
        """
        
        row = await self._db.fetchrow(query, telegram_id)
        
        if not row:
            return None
        
        user = UserDTO(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            language_code=row["language_code"],
            role=UserRole(row["role"]),
            is_active=row["is_active"],
            is_blocked=row["is_blocked"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        
        # Инвалидируем кэш
        await self._redis.delete(self._cache_key(telegram_id))
        
        # Публикуем событие
        event = UserUnblocked(user_id=user.id)
        await self._event_bus.publish(event.event_type, event.to_json())
        
        return user


class DriverService:
    """Сервис управления водителями."""
    
    def __init__(
        self,
        db: DatabaseManager,
        redis: RedisClient,
        event_bus: EventBus,
    ) -> None:
        self._db = db
        self._redis = redis
        self._event_bus = event_bus
    
    def _cache_key(self, driver_id: int) -> str:
        """Ключ кэша для водителя."""
        return f"driver:{driver_id}"
    
    def _geo_key(self) -> str:
        """Ключ Redis GEO для локаций водителей."""
        return "drivers:locations"
    
    async def get_driver(self, driver_id: int) -> Optional[DriverDTO]:
        """Получение информации о водителе."""
        cache_key = self._cache_key(driver_id)
        
        # Проверяем кэш
        cached = await self._redis.get(cache_key)
        if cached:
            return DriverDTO.model_validate_json(cached)
        
        query = """
            SELECT u.id as user_id, u.telegram_id, u.username, u.first_name, 
                   u.last_name, u.phone,
                   d.status, d.is_verified, d.is_working,
                   d.current_lat, d.current_lon, d.last_location_update,
                   d.car_model, d.car_color, d.car_number,
                   d.rating, d.total_trips, d.balance_stars
            FROM users u
            JOIN drivers d ON u.id = d.user_id
            WHERE u.id = $1
        """
        
        row = await self._db.fetchrow(query, driver_id)
        
        if not row:
            return None
        
        driver = DriverDTO(
            user_id=row["user_id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            status=DriverStatus(row["status"]) if row["status"] else DriverStatus.OFFLINE,
            is_verified=row["is_verified"],
            is_working=row["is_working"],
            current_lat=row["current_lat"],
            current_lon=row["current_lon"],
            last_location_update=row["last_location_update"],
            car_model=row["car_model"],
            car_color=row["car_color"],
            car_number=row["car_number"],
            rating=row["rating"] or 5.0,
            total_trips=row["total_trips"] or 0,
            balance_stars=row["balance_stars"] or 0,
        )
        
        # Кэшируем
        await self._redis.set(
            cache_key,
            driver.model_dump_json(),
            ex=settings.redis_ttl.PROFILE_TTL,
        )
        
        return driver
    
    async def register_driver(self, request: DriverCreateRequest) -> DriverDTO:
        """Регистрация водителя."""
        # Обновляем роль пользователя
        await self._db.execute(
            "UPDATE users SET role = 'driver' WHERE id = $1",
            request.user_id,
        )
        
        # Создаём запись водителя
        query = """
            INSERT INTO drivers (user_id, car_model, car_color, car_number,
                                status, is_verified, is_working, rating,
                                total_trips, balance_stars, created_at)
            VALUES ($1, $2, $3, $4, 'offline', false, false, 5.0, 0, 0, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET car_model = EXCLUDED.car_model,
                car_color = EXCLUDED.car_color,
                car_number = EXCLUDED.car_number
            RETURNING user_id
        """
        
        await self._db.execute(
            query,
            request.user_id,
            request.car_model,
            request.car_color,
            request.car_number,
        )
        
        return await self.get_driver(request.user_id)
    
    async def set_online(self, driver_id: int) -> Optional[DriverDTO]:
        """Перевести водителя в онлайн."""
        query = """
            UPDATE drivers
            SET status = 'online', is_working = true
            WHERE user_id = $1
            RETURNING user_id
        """
        
        row = await self._db.fetchrow(query, driver_id)
        if not row:
            return None
        
        # Инвалидируем кэш
        await self._redis.delete(self._cache_key(driver_id))
        
        # Публикуем событие
        event = DriverStatusChanged(
            driver_id=driver_id,
            old_status="offline",
            new_status="online",
        )
        await self._event_bus.publish(event.event_type, event.to_json())
        
        return await self.get_driver(driver_id)
    
    async def set_offline(self, driver_id: int) -> Optional[DriverDTO]:
        """Перевести водителя в оффлайн."""
        query = """
            UPDATE drivers
            SET status = 'offline', is_working = false
            WHERE user_id = $1
            RETURNING user_id
        """
        
        row = await self._db.fetchrow(query, driver_id)
        if not row:
            return None
        
        # Удаляем из GEO-индекса
        await self._redis.zrem(self._geo_key(), str(driver_id))
        
        # Инвалидируем кэш
        await self._redis.delete(self._cache_key(driver_id))
        
        # Публикуем событие
        event = DriverStatusChanged(
            driver_id=driver_id,
            old_status="online",
            new_status="offline",
        )
        await self._event_bus.publish(event.event_type, event.to_json())
        
        return await self.get_driver(driver_id)
    
    async def update_location(
        self,
        driver_id: int,
        location: DriverLocationUpdate,
    ) -> None:
        """Обновление геолокации водителя."""
        # Обновляем в БД (периодически, не каждые 3 сек)
        # Основное хранилище — Redis GEO
        
        # Добавляем/обновляем в Redis GEO
        await self._redis.geoadd(
            self._geo_key(),
            location.longitude,
            location.latitude,
            str(driver_id),
        )
        
        # Сохраняем last_seen
        await self._redis.set(
            f"driver:{driver_id}:last_seen",
            datetime.now(timezone.utc).isoformat(),
            ex=settings.redis_ttl.LAST_SEEN_TTL,
        )
        
        # Публикуем в Redis Pub/Sub для realtime_ws_gateway
        location_data = {
            "driver_id": driver_id,
            "lat": location.latitude,
            "lon": location.longitude,
            "heading": location.heading,
            "speed": location.speed,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await self._redis.publish(
            "driver_locations",
            str(location_data),
        )
    
    async def get_nearby_drivers(
        self,
        lat: float,
        lon: float,
        radius_km: float = 3.0,
        limit: int = 10,
    ) -> list[DriverDTO]:
        """Получение ближайших онлайн-водителей."""
        # Поиск через Redis GEO
        results = await self._redis.georadius(
            self._geo_key(),
            lon,
            lat,
            radius_km,
            unit="km",
            withdist=True,
            sort="ASC",
            count=limit,
        )
        
        drivers = []
        for item in results:
            driver_id = int(item[0])
            driver = await self.get_driver(driver_id)
            if driver and driver.status == DriverStatus.ONLINE:
                drivers.append(driver)
        
        return drivers
