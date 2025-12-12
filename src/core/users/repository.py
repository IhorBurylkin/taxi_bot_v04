# src/core/users/repository.py
"""
Репозиторий для работы с пользователями в БД.
Реализует паттерн Repository для абстракции доступа к данным.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.common.constants import UserRole, DriverStatus
from src.common.logger import log_error, log_info
from src.common.constants import TypeMsg
from src.core.users.models import User, DriverProfile, UserCreateDTO, DriverProfileCreateDTO
from src.infra.database import DatabaseManager


class UserRepository:
    """Репозиторий пользователей."""
    
    def __init__(self, db: DatabaseManager) -> None:
        """
        Инициализация репозитория.
        
        Args:
            db: Менеджер базы данных (Dependency Injection)
        """
        self._db = db
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Получает пользователя по ID.
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            Пользователь или None
        """
        try:
            row = await self._db.fetchrow(
                """
                SELECT id, username, first_name, last_name, phone, language,
                       role, rating, trips_count, is_blocked, created_at, updated_at
                FROM users
                WHERE id = $1
                """,
                user_id,
            )
            
            if row is None:
                return None
            
            return User(
                id=row["id"],
                username=row["username"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                phone=row["phone"],
                language=row["language"],
                role=UserRole(row["role"]),
                rating=row["rating"],
                trips_count=row["trips_count"],
                is_blocked=row["is_blocked"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        except Exception as e:
            await log_error(f"Ошибка получения пользователя {user_id}: {e}")
            return None
    
    async def create(self, dto: UserCreateDTO) -> Optional[User]:
        """
        Создаёт нового пользователя.
        
        Args:
            dto: Данные для создания
            
        Returns:
            Созданный пользователь или None
        """
        try:
            now = datetime.now(timezone.utc)
            
            await self._db.execute(
                """
                INSERT INTO users (id, username, first_name, last_name, language, role,
                                   rating, trips_count, is_blocked, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    updated_at = EXCLUDED.updated_at
                """,
                dto.id,
                dto.username,
                dto.first_name,
                dto.last_name,
                dto.language,
                UserRole.PASSENGER.value,
                5.0,
                0,
                False,
                now,
                now,
            )
            
            await log_info(f"Пользователь {dto.id} создан/обновлён", type_msg=TypeMsg.DEBUG)
            
            return await self.get_by_id(dto.id)
        except Exception as e:
            await log_error(f"Ошибка создания пользователя {dto.id}: {e}")
            return None
    
    async def update(self, user: User) -> bool:
        """
        Обновляет пользователя.
        
        Args:
            user: Обновлённые данные пользователя
            
        Returns:
            True если успешно
        """
        try:
            await self._db.execute(
                """
                UPDATE users
                SET username = $2, first_name = $3, last_name = $4, phone = $5,
                    language = $6, role = $7, rating = $8, trips_count = $9,
                    is_blocked = $10, updated_at = $11
                WHERE id = $1
                """,
                user.id,
                user.username,
                user.first_name,
                user.last_name,
                user.phone,
                user.language,
                user.role.value,
                user.rating,
                user.trips_count,
                user.is_blocked,
                datetime.now(timezone.utc),
            )
            
            return True
        except Exception as e:
            await log_error(f"Ошибка обновления пользователя {user.id}: {e}")
            return False
    
    async def set_role(self, user_id: int, role: UserRole) -> bool:
        """
        Устанавливает роль пользователя.
        
        Args:
            user_id: ID пользователя
            role: Новая роль
            
        Returns:
            True если успешно
        """
        try:
            await self._db.execute(
                """
                UPDATE users
                SET role = $2, updated_at = $3
                WHERE id = $1
                """,
                user_id,
                role.value,
                datetime.now(timezone.utc),
            )
            
            return True
        except Exception as e:
            await log_error(f"Ошибка установки роли для пользователя {user_id}: {e}")
            return False


class DriverRepository:
    """Репозиторий профилей водителей."""
    
    def __init__(self, db: DatabaseManager) -> None:
        """
        Инициализация репозитория.
        
        Args:
            db: Менеджер базы данных (Dependency Injection)
        """
        self._db = db
    
    async def get_by_user_id(self, user_id: int) -> Optional[DriverProfile]:
        """
        Получает профиль водителя по ID пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Профиль водителя или None
        """
        try:
            row = await self._db.fetchrow(
                """
                SELECT user_id, car_brand, car_model, car_color, car_plate, car_year,
                       license_number, license_expiry, status, is_verified,
                       completed_orders, cancelled_orders, total_earnings,
                       last_latitude, last_longitude, last_seen, balance_stars,
                       created_at, updated_at
                FROM driver_profiles
                WHERE user_id = $1
                """,
                user_id,
            )
            
            if row is None:
                return None
            
            return DriverProfile(
                user_id=row["user_id"],
                car_brand=row["car_brand"],
                car_model=row["car_model"],
                car_color=row["car_color"],
                car_plate=row["car_plate"],
                car_year=row["car_year"],
                license_number=row["license_number"],
                license_expiry=row["license_expiry"],
                status=DriverStatus(row["status"]),
                is_verified=row["is_verified"],
                completed_orders=row["completed_orders"],
                cancelled_orders=row["cancelled_orders"],
                total_earnings=row["total_earnings"],
                last_latitude=row["last_latitude"],
                last_longitude=row["last_longitude"],
                last_seen=row["last_seen"],
                balance_stars=row["balance_stars"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        except Exception as e:
            await log_error(f"Ошибка получения профиля водителя {user_id}: {e}")
            return None
    
    async def create(self, dto: DriverProfileCreateDTO) -> Optional[DriverProfile]:
        """
        Создаёт профиль водителя.
        
        Args:
            dto: Данные для создания
            
        Returns:
            Созданный профиль или None
        """
        try:
            now = datetime.now(timezone.utc)
            
            await self._db.execute(
                """
                INSERT INTO driver_profiles (user_id, car_brand, car_model, car_color,
                                            car_plate, car_year, status, is_verified,
                                            completed_orders, cancelled_orders, total_earnings,
                                            balance_stars, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (user_id) DO UPDATE SET
                    car_brand = EXCLUDED.car_brand,
                    car_model = EXCLUDED.car_model,
                    car_color = EXCLUDED.car_color,
                    car_plate = EXCLUDED.car_plate,
                    car_year = EXCLUDED.car_year,
                    updated_at = EXCLUDED.updated_at
                """,
                dto.user_id,
                dto.car_brand,
                dto.car_model,
                dto.car_color,
                dto.car_plate,
                dto.car_year,
                DriverStatus.OFFLINE.value,
                False,
                0,
                0,
                0.0,
                0,
                now,
                now,
            )
            
            await log_info(f"Профиль водителя {dto.user_id} создан/обновлён", type_msg=TypeMsg.DEBUG)
            
            return await self.get_by_user_id(dto.user_id)
        except Exception as e:
            await log_error(f"Ошибка создания профиля водителя {dto.user_id}: {e}")
            return None
    
    async def update_status(self, user_id: int, status: DriverStatus) -> bool:
        """
        Обновляет статус водителя.
        
        Args:
            user_id: ID пользователя
            status: Новый статус
            
        Returns:
            True если успешно
        """
        try:
            await self._db.execute(
                """
                UPDATE driver_profiles
                SET status = $2, updated_at = $3
                WHERE user_id = $1
                """,
                user_id,
                status.value,
                datetime.now(timezone.utc),
            )
            
            return True
        except Exception as e:
            await log_error(f"Ошибка обновления статуса водителя {user_id}: {e}")
            return False
    
    async def update_location(
        self,
        user_id: int,
        latitude: float,
        longitude: float,
    ) -> bool:
        """
        Обновляет геолокацию водителя.
        
        Args:
            user_id: ID пользователя
            latitude: Широта
            longitude: Долгота
            
        Returns:
            True если успешно
        """
        try:
            now = datetime.now(timezone.utc)
            
            await self._db.execute(
                """
                UPDATE driver_profiles
                SET last_latitude = $2, last_longitude = $3, last_seen = $4, updated_at = $4
                WHERE user_id = $1
                """,
                user_id,
                latitude,
                longitude,
                now,
            )
            
            return True
        except Exception as e:
            await log_error(f"Ошибка обновления локации водителя {user_id}: {e}")
            return False
    
    async def get_online_drivers(self) -> list[DriverProfile]:
        """
        Получает список онлайн водителей.
        
        Returns:
            Список профилей водителей
        """
        try:
            rows = await self._db.fetch(
                """
                SELECT user_id, car_brand, car_model, car_color, car_plate, car_year,
                       license_number, license_expiry, status, is_verified,
                       completed_orders, cancelled_orders, total_earnings,
                       last_latitude, last_longitude, last_seen, balance_stars,
                       created_at, updated_at
                FROM driver_profiles
                WHERE status = $1 AND is_verified = TRUE
                """,
                DriverStatus.ONLINE.value,
            )
            
            return [
                DriverProfile(
                    user_id=row["user_id"],
                    car_brand=row["car_brand"],
                    car_model=row["car_model"],
                    car_color=row["car_color"],
                    car_plate=row["car_plate"],
                    car_year=row["car_year"],
                    license_number=row["license_number"],
                    license_expiry=row["license_expiry"],
                    status=DriverStatus(row["status"]),
                    is_verified=row["is_verified"],
                    completed_orders=row["completed_orders"],
                    cancelled_orders=row["cancelled_orders"],
                    total_earnings=row["total_earnings"],
                    last_latitude=row["last_latitude"],
                    last_longitude=row["last_longitude"],
                    last_seen=row["last_seen"],
                    balance_stars=row["balance_stars"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
        except Exception as e:
            await log_error(f"Ошибка получения онлайн водителей: {e}")
            return []
