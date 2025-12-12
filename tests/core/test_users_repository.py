# tests/core/test_users_repository.py
"""
Тесты для репозитория пользователей.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

import pytest

from src.common.constants import UserRole, DriverStatus
from src.core.users.models import User, DriverProfile, UserCreateDTO, DriverProfileCreateDTO
from src.core.users.repository import UserRepository


@pytest.fixture
def mock_db() -> MagicMock:
    """Создаёт мок DatabaseManager."""
    db = MagicMock()
    db.fetchrow = AsyncMock()
    db.fetch = AsyncMock()
    db.execute = AsyncMock()
    db.transaction = MagicMock()
    return db


@pytest.fixture
def user_repository(mock_db: MagicMock) -> UserRepository:
    """Создаёт экземпляр UserRepository с моком БД."""
    return UserRepository(db=mock_db)


@pytest.fixture
def sample_user_row() -> Dict[str, Any]:
    """Создаёт примерные данные пользователя из БД."""
    return {
        "id": 123456,
        "username": "test_user",
        "first_name": "Иван",
        "last_name": "Петров",
        "phone": "+380501234567",
        "language": "ru",
        "role": UserRole.PASSENGER.value,
        "rating": 4.8,
        "trips_count": 10,
        "is_blocked": False,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


@pytest.fixture
def sample_driver_row() -> Dict[str, Any]:
    """Создаёт примерные данные профиля водителя из БД."""
    return {
        "user_id": 123456,
        "car_brand": "Toyota",
        "car_model": "Camry",
        "car_color": "Черный",
        "car_plate": "АА1234ВС",
        "license_number": "LIC123456",
        "is_verified": True,
        "is_working": False,
        "current_latitude": None,
        "current_longitude": None,
        "rating": 4.9,
        "trips_count": 50,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


class TestUserRepository:
    """Тесты для UserRepository."""
    
    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        user_repository: UserRepository,
        mock_db: MagicMock,
        sample_user_row: Dict[str, Any],
    ) -> None:
        """Проверяет успешное получение пользователя по ID."""
        # Arrange
        user_id = sample_user_row["id"]
        mock_db.fetchrow.return_value = sample_user_row
        
        # Act
        user = await user_repository.get_by_id(user_id)
        
        # Assert
        assert user is not None
        assert user.id == user_id
        assert user.username == sample_user_row["username"]
        assert user.role == UserRole.PASSENGER
        mock_db.fetchrow.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        user_repository: UserRepository,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет получение несуществующего пользователя."""
        # Arrange
        user_id = 999999
        mock_db.fetchrow.return_value = None
        
        # Act
        user = await user_repository.get_by_id(user_id)
        
        # Assert
        assert user is None
        mock_db.fetchrow.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_id_error(
        self,
        user_repository: UserRepository,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет обработку ошибки при получении пользователя."""
        # Arrange
        user_id = 123456
        mock_db.fetchrow.side_effect = Exception("Database error")
        
        # Act
        with patch("src.core.users.repository.log_error", new_callable=AsyncMock):
            user = await user_repository.get_by_id(user_id)
        
        # Assert
        assert user is None
    
    @pytest.mark.asyncio
    async def test_create_success(
        self,
        user_repository: UserRepository,
        mock_db: MagicMock,
        sample_user_row: Dict[str, Any],
    ) -> None:
        """Проверяет успешное создание пользователя."""
        # Arrange
        dto = UserCreateDTO(
            id=sample_user_row["id"],
            username=sample_user_row["username"],
            first_name=sample_user_row["first_name"],
            last_name=sample_user_row["last_name"],
            language=sample_user_row["language"],
        )
        
        mock_db.fetchrow.return_value = sample_user_row
        
        # Act
        with patch("src.core.users.repository.log_info", new_callable=AsyncMock):
            user = await user_repository.create(dto)
        
        # Assert
        assert user is not None
        assert user.id == dto.id
        assert user.username == dto.username
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_error(
        self,
        user_repository: UserRepository,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет обработку ошибки при создании пользователя."""
        # Arrange
        dto = UserCreateDTO(
            id=123456,
            username="test_user",
            first_name="Иван",
            last_name="Петров",
            language="ru",
        )
        
        mock_db.execute.side_effect = Exception("Database error")
        
        # Act
        with patch("src.core.users.repository.log_error", new_callable=AsyncMock):
            user = await user_repository.create(dto)
        
        # Assert
        assert user is None
    
    @pytest.mark.asyncio
    async def test_update_success(
        self,
        user_repository: UserRepository,
        mock_db: MagicMock,
        sample_user_row: Dict[str, Any],
    ) -> None:
        """Проверяет успешное обновление пользователя."""
        # Arrange
        user = User(
            id=sample_user_row["id"],
            username=sample_user_row["username"],
            first_name=sample_user_row["first_name"],
            last_name=sample_user_row["last_name"],
            phone=sample_user_row["phone"],
            language=sample_user_row["language"],
            role=UserRole.PASSENGER,
            rating=sample_user_row["rating"],
            trips_count=sample_user_row["trips_count"],
            is_blocked=sample_user_row["is_blocked"],
            created_at=sample_user_row["created_at"],
            updated_at=sample_user_row["updated_at"],
        )
        
        # Act
        result = await user_repository.update(user)
        
        # Assert
        assert result is True
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_error(
        self,
        user_repository: UserRepository,
        mock_db: MagicMock,
        sample_user_row: Dict[str, Any],
    ) -> None:
        """Проверяет обработку ошибки при обновлении пользователя."""
        # Arrange
        user = User(
            id=sample_user_row["id"],
            username=sample_user_row["username"],
            first_name=sample_user_row["first_name"],
            last_name=sample_user_row["last_name"],
            role=UserRole.PASSENGER,
        )
        
        mock_db.execute.side_effect = Exception("Database error")
        
        # Act
        with patch("src.core.users.repository.log_error", new_callable=AsyncMock):
            result = await user_repository.update(user)
        
        # Assert
        assert result is False
    
    # Примечание: методы get_driver_profile, create_driver_profile и set_driver_working_status
    # не находятся в UserRepository — они в отдельном DriverProfileRepository.
    # Эти тесты будут добавлены позже в test_driver_profile_repository.py
