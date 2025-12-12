from typing import Optional, List
from asyncpg import Connection, Record
from src.infra.database import DatabaseManager
from src.shared.models.user_dto import UserDTO, DriverProfileDTO, CreateUserRequest, CreateDriverProfileRequest
from src.shared.models.enums import UserRole
from src.common.logger import log_info, log_error, TypeMsg

class UserRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def get_user_by_id(self, user_id: int) -> Optional[UserDTO]:
        """Получает пользователя по ID."""
        query = """
            SELECT 
                id, username, first_name, last_name, phone, language, 
                role, is_active, is_blocked, created_at, updated_at
            FROM users_schema.users
            WHERE id = $1
        """
        async with self.db.acquire() as conn:
            record = await conn.fetchrow(query, user_id)
            if record:
                return UserDTO(**dict(record))
            return None

    async def create_or_update_user(self, user: CreateUserRequest) -> UserDTO:
        """Создает или обновляет пользователя (upsert)."""
        query = """
            INSERT INTO users_schema.users (id, username, first_name, last_name, language, role)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                language = EXCLUDED.language,
                updated_at = NOW()
            RETURNING id, username, first_name, last_name, phone, language, 
                      role, is_active, is_blocked, created_at, updated_at
        """
        async with self.db.acquire() as conn:
            record = await conn.fetchrow(
                query,
                user.id,
                user.username,
                user.first_name,
                user.last_name,
                user.language,
                user.role.value
            )
            return UserDTO(**dict(record))

    async def update_user_role(self, user_id: int, role: UserRole) -> Optional[UserDTO]:
        """Обновляет роль пользователя."""
        query = """
            UPDATE users_schema.users
            SET role = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING id, username, first_name, last_name, phone, language, 
                      role, is_active, is_blocked, created_at, updated_at
        """
        async with self.db.acquire() as conn:
            record = await conn.fetchrow(query, user_id, role.value)
            if record:
                return UserDTO(**dict(record))
            return None

    async def get_driver_profile(self, user_id: int) -> Optional[DriverProfileDTO]:
        """Получает профиль водителя."""
        query = """
            SELECT 
                user_id, car_brand, car_model, car_color, car_plate,
                is_verified, is_working, rating, total_trips,
                created_at, updated_at
            FROM users_schema.driver_profiles
            WHERE user_id = $1
        """
        async with self.db.acquire() as conn:
            record = await conn.fetchrow(query, user_id)
            if record:
                return DriverProfileDTO(**dict(record))
            return None

    async def create_driver_profile(self, user_id: int, profile: CreateDriverProfileRequest) -> DriverProfileDTO:
        """Создает профиль водителя."""
        query = """
            INSERT INTO users_schema.driver_profiles (
                user_id, car_brand, car_model, car_color, car_plate
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE SET
                car_brand = EXCLUDED.car_brand,
                car_model = EXCLUDED.car_model,
                car_color = EXCLUDED.car_color,
                car_plate = EXCLUDED.car_plate,
                updated_at = NOW()
            RETURNING 
                user_id, car_brand, car_model, car_color, car_plate,
                is_verified, is_working, rating, total_trips,
                created_at, updated_at
        """
        async with self.db.acquire() as conn:
            record = await conn.fetchrow(
                query,
                user_id,
                profile.car_brand,
                profile.car_model,
                profile.car_color,
                profile.car_plate
            )
            return DriverProfileDTO(**dict(record))

    async def get_all_users(self, limit: int, offset: int) -> List[UserDTO]:
        """Получает список пользователей с пагинацией."""
        query = """
            SELECT 
                id, username, first_name, last_name, phone, language, 
                role, is_active, is_blocked, created_at, updated_at
            FROM users_schema.users
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        async with self.db.acquire() as conn:
            records = await conn.fetch(query, limit, offset)
            return [UserDTO(**dict(record)) for record in records]

    async def count_users(self) -> int:
        """Возвращает общее количество пользователей."""
        query = "SELECT COUNT(*) FROM users_schema.users"
        async with self.db.acquire() as conn:
            return await conn.fetchval(query)
