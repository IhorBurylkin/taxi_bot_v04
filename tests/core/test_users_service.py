# tests/core/test_users_service.py
"""
Тесты для сервиса пользователей.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.common.constants import UserRole, DriverStatus
from src.core.users.models import User, DriverProfile, UserCreateDTO, DriverProfileCreateDTO
from src.core.users.service import UserService


class TestUserService:
    """Тесты для сервиса пользователей."""
    
    @pytest.fixture
    def user_service(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_event_bus: AsyncMock,
    ) -> UserService:
        """Создаёт сервис с моками."""
        return UserService(
            db=mock_db,
            redis=mock_redis,
            event_bus=mock_event_bus,
        )
    
    def test_user_cache_key(self, user_service: UserService) -> None:
        """Проверяет формирование ключа кэша пользователя."""
        key = user_service._user_cache_key(123456789)
        assert key == "user:123456789"
    
    def test_driver_cache_key(self, user_service: UserService) -> None:
        """Проверяет формирование ключа кэша водителя."""
        key = user_service._driver_cache_key(987654321)
        assert key == "driver:987654321"
    
    @pytest.mark.asyncio
    async def test_get_user_from_cache(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
        sample_user_data: dict,
    ) -> None:
        """Проверяет получение пользователя из кэша."""
        user = User(**sample_user_data)
        mock_redis.get_model.return_value = user
        
        result = await user_service.get_user(123456789)
        
        assert result is not None
        assert result.id == 123456789
        mock_redis.get_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_cache_miss(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
        sample_user_data: dict,
    ) -> None:
        """Проверяет получение пользователя при промахе кэша."""
        # Кэш пустой
        mock_redis.get_model.return_value = None
        
        # Мок репозитория возвращает пользователя
        user = User(**sample_user_data)
        
        with patch.object(
            user_service._user_repo, 'get_by_id',
            new_callable=AsyncMock,
            return_value=user
        ):
            with patch("src.config.settings") as mock_settings:
                mock_settings.redis_ttl.PROFILE_TTL = 300
                
                result = await user_service.get_user(123456789)
        
        assert result is not None
        assert result.id == 123456789
        # Проверяем, что данные были записаны в кэш
        mock_redis.set_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_not_found(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет случай, когда пользователь не найден."""
        mock_redis.get_model = AsyncMock(return_value=None)
        
        with patch.object(
            user_service._user_repo, 'get_by_id',
            new_callable=AsyncMock,
            return_value=None
        ):
            with patch("src.common.logger.log_info", new_callable=AsyncMock):
                result = await user_service.get_user(999999999)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_register_user(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
        sample_user_data: dict,
    ) -> None:
        """Проверяет регистрацию пользователя."""
        mock_redis.delete = AsyncMock()
        
        dto = UserCreateDTO(
            id=sample_user_data["id"],
            username=sample_user_data["username"],
            first_name=sample_user_data["first_name"],
            last_name=sample_user_data["last_name"],
            language=sample_user_data["language"],
        )
        
        user = User(**sample_user_data)
        
        with patch.object(
            user_service._user_repo, 'create',
            new_callable=AsyncMock,
            return_value=user
        ):
            result = await user_service.register_user(dto)
        
        assert result is not None
        assert result.id == dto.id
        # Проверяем, что кэш был инвалидирован
        assert mock_redis.delete.called
    
    @pytest.mark.asyncio
    async def test_update_user(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
        sample_user_data: dict,
    ) -> None:
        """Проверяет обновление пользователя."""
        user = User(**sample_user_data)
        
        with patch.object(
            user_service._user_repo, 'update',
            new_callable=AsyncMock,
            return_value=True
        ):
            result = await user_service.update_user(user)
        
        assert result is True
        # Проверяем, что кэш был инвалидирован
        mock_redis.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_set_user_role(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет изменение роли пользователя."""
        with patch.object(
            user_service._user_repo, 'set_role',
            new_callable=AsyncMock,
            return_value=True
        ):
            result = await user_service.set_user_role(123456789, UserRole.DRIVER)
        
        assert result is True
        mock_redis.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_driver_profile_from_cache(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
        sample_driver_data: dict,
    ) -> None:
        """Проверяет получение профиля водителя из кэша."""
        profile = DriverProfile(**sample_driver_data)
        mock_redis.get_model.return_value = profile
        
        result = await user_service.get_driver_profile(987654321)
        
        assert result is not None
        assert result.user_id == 987654321
        mock_redis.get_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_driver_profile_cache_miss(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
        sample_driver_data: dict,
    ) -> None:
        """Проверяет получение профиля водителя при промахе кэша."""
        mock_redis.get_model.return_value = None
        
        profile = DriverProfile(**sample_driver_data)
        
        with patch.object(
            user_service._driver_repo, 'get_by_user_id',
            new_callable=AsyncMock,
            return_value=profile
        ):
            with patch("src.config.settings") as mock_settings:
                mock_settings.redis_ttl.PROFILE_TTL = 300
                
                result = await user_service.get_driver_profile(987654321)
        
        assert result is not None
        mock_redis.set_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_driver_profile_not_found(
        self,
        user_service: UserService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет случай, когда профиль водителя не найден."""
        mock_redis.get_model.return_value = None
        
        with patch.object(
            user_service._driver_repo, 'get_by_user_id',
            new_callable=AsyncMock,
            return_value=None
        ):
            result = await user_service.get_driver_profile(999999999)
        
        assert result is None
