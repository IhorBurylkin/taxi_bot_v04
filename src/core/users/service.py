# src/core/users/service.py
"""
Сервис для работы с пользователями.
Координирует бизнес-логику, кэширование и события.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.common.constants import UserRole, DriverStatus, TypeMsg
from src.common.logger import log_info, log_error
from src.core.users.models import (
    User,
    DriverProfile,
    UserCreateDTO,
    DriverProfileCreateDTO,
    DriverLocationDTO,
)
from src.core.users.repository import UserRepository, DriverRepository
from src.infra.database import DatabaseManager
from src.infra.redis_client import RedisClient
from src.infra.event_bus import EventBus, DomainEvent, EventTypes


class UserService:
    """
    Сервис пользователей.
    Реализует бизнес-логику с кэшированием и публикацией событий.
    """
    
    def __init__(
        self,
        db: DatabaseManager,
        redis: RedisClient,
        event_bus: EventBus,
    ) -> None:
        """
        Инициализация сервиса.
        
        Args:
            db: Менеджер базы данных
            redis: Клиент Redis
            event_bus: Шина событий
        """
        self._user_repo = UserRepository(db)
        self._driver_repo = DriverRepository(db)
        self._redis = redis
        self._event_bus = event_bus
    
    def _user_cache_key(self, user_id: int) -> str:
        """Генерирует ключ кэша для пользователя."""
        return f"user:{user_id}"
    
    def _driver_cache_key(self, user_id: int) -> str:
        """Генерирует ключ кэша для водителя."""
        return f"driver:{user_id}"
    
    # =========================================================================
    # ПОЛЬЗОВАТЕЛИ
    # =========================================================================
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """
        Получает пользователя по ID.
        Использует Cache-Aside паттерн.
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            Пользователь или None
        """
        cache_key = self._user_cache_key(user_id)
        
        # Проверяем кэш
        cached = await self._redis.get_model(cache_key, User)
        if cached is not None:
            return cached
        
        # Читаем из БД
        user = await self._user_repo.get_by_id(user_id)
        
        if user is not None:
            # Кэшируем результат
            from src.config import settings
            await self._redis.set_model(
                cache_key,
                user,
                ttl=settings.redis_ttl.PROFILE_TTL,
            )
        
        return user
    
    async def register_user(self, dto: UserCreateDTO) -> Optional[User]:
        """
        Регистрирует нового пользователя или обновляет существующего.
        
        Args:
            dto: Данные пользователя
            
        Returns:
            Созданный/обновлённый пользователь
        """
        user = await self._user_repo.create(dto)
        
        if user is not None:
            # Инвалидируем кэш
            await self._redis.delete(self._user_cache_key(user.id))
            
            await log_info(
                f"Пользователь зарегистрирован: {user.id} ({user.display_name})",
                type_msg=TypeMsg.INFO,
            )
        
        return user
    
    async def update_user(self, user: User) -> bool:
        """
        Обновляет данные пользователя.
        
        Args:
            user: Обновлённые данные
            
        Returns:
            True если успешно
        """
        # Сначала пишем в БД
        success = await self._user_repo.update(user)
        
        if success:
            # Потом инвалидируем кэш
            await self._redis.delete(self._user_cache_key(user.id))
        
        return success
    
    async def set_user_role(self, user_id: int, role: UserRole) -> bool:
        """
        Устанавливает роль пользователя.
        
        Args:
            user_id: ID пользователя
            role: Новая роль
            
        Returns:
            True если успешно
        """
        success = await self._user_repo.set_role(user_id, role)
        
        if success:
            await self._redis.delete(self._user_cache_key(user_id))
            
            await log_info(
                f"Роль пользователя {user_id} изменена на {role.value}",
                type_msg=TypeMsg.INFO,
            )
        
        return success
    
    # =========================================================================
    # ВОДИТЕЛИ
    # =========================================================================
    
    async def get_driver_profile(self, user_id: int) -> Optional[DriverProfile]:
        """
        Получает профиль водителя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Профиль водителя или None
        """
        cache_key = self._driver_cache_key(user_id)
        
        # Проверяем кэш
        cached = await self._redis.get_model(cache_key, DriverProfile)
        if cached is not None:
            return cached
        
        # Читаем из БД
        profile = await self._driver_repo.get_by_user_id(user_id)
        
        if profile is not None:
            from src.config import settings
            await self._redis.set_model(
                cache_key,
                profile,
                ttl=settings.redis_ttl.PROFILE_TTL,
            )
        
        return profile
    
    async def register_driver(self, dto: DriverProfileCreateDTO) -> Optional[DriverProfile]:
        """
        Регистрирует водителя.
        
        Args:
            dto: Данные профиля
            
        Returns:
            Созданный профиль
        """
        # Проверяем, существует ли пользователь
        user = await self.get_user(dto.user_id)
        if user is None:
            await log_error(f"Пользователь {dto.user_id} не найден для регистрации водителя")
            return None
        
        # Создаём профиль водителя
        profile = await self._driver_repo.create(dto)
        
        if profile is not None:
            # Меняем роль на водителя
            await self.set_user_role(dto.user_id, UserRole.DRIVER)
            
            # Инвалидируем кэш
            await self._redis.delete(self._driver_cache_key(dto.user_id))
            
            await log_info(
                f"Водитель зарегистрирован: {dto.user_id}",
                type_msg=TypeMsg.INFO,
            )
        
        return profile
    
    async def set_driver_online(self, user_id: int) -> bool:
        """
        Переводит водителя в статус Online.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если успешно
        """
        profile = await self.get_driver_profile(user_id)
        if profile is None or not profile.is_verified:
            return False
        
        # Обновляем статус в БД
        success = await self._driver_repo.update_status(user_id, DriverStatus.ONLINE)
        
        if success:
            # Инвалидируем кэш
            await self._redis.delete(self._driver_cache_key(user_id))
            
            # Публикуем событие
            try:
                await self._event_bus.publish(DomainEvent(
                    event_type=EventTypes.DRIVER_ONLINE,
                    payload={"driver_id": user_id},
                ))
            except Exception as pub_error:
                await log_error(f"Не удалось опубликовать DRIVER_ONLINE: {pub_error}")
            
            await log_info(f"Водитель {user_id} вышел на линию", type_msg=TypeMsg.INFO)
        
        return success
    
    async def set_driver_offline(self, user_id: int) -> bool:
        """
        Переводит водителя в статус Offline.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если успешно
        """
        # Обновляем статус в БД
        success = await self._driver_repo.update_status(user_id, DriverStatus.OFFLINE)
        
        if success:
            # Инвалидируем кэш
            await self._redis.delete(self._driver_cache_key(user_id))
            
            # Удаляем из geo-индекса
            await self._redis.georem("drivers:locations", str(user_id))
            
            # Публикуем событие
            try:
                await self._event_bus.publish(DomainEvent(
                    event_type=EventTypes.DRIVER_OFFLINE,
                    payload={"driver_id": user_id},
                ))
            except Exception as pub_error:
                await log_error(f"Не удалось опубликовать DRIVER_OFFLINE: {pub_error}")
            
            await log_info(f"Водитель {user_id} ушёл с линии", type_msg=TypeMsg.INFO)
        
        return success
    
    async def update_driver_location(self, dto: DriverLocationDTO) -> bool:
        """
        Обновляет геолокацию водителя.
        
        Args:
            dto: Данные геолокации
            
        Returns:
            True если успешно
        """
        try:
            # Обновляем в БД
            success = await self._driver_repo.update_location(
                dto.driver_id,
                dto.latitude,
                dto.longitude,
            )
            
            if success:
                # Обновляем geo-индекс в Redis
                await self._redis.geoadd(
                    "drivers:locations",
                    dto.longitude,
                    dto.latitude,
                    str(dto.driver_id),
                )
                
                # Обновляем last_seen
                from src.config import settings
                await self._redis.set(
                    f"driver:last_seen:{dto.driver_id}",
                    datetime.now(timezone.utc).isoformat(),
                    ttl=settings.redis_ttl.LAST_SEEN_TTL,
                )
                
                # Инвалидируем кэш профиля
                await self._redis.delete(self._driver_cache_key(dto.driver_id))
                
                await log_info(
                    f"Локация водителя {dto.driver_id} обновлена: {dto.latitude}, {dto.longitude}",
                    type_msg=TypeMsg.DEBUG,
                )
            
            return success
        except Exception as e:
            await log_error(f"Ошибка обновления локации водителя {dto.driver_id}: {e}")
            return False
    
    async def get_online_drivers(self) -> list[DriverProfile]:
        """
        Получает список онлайн водителей.
        
        Returns:
            Список профилей водителей
        """
        return await self._driver_repo.get_online_drivers()
