# tests/core/test_users_models.py
"""
Тесты для моделей пользователей.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.common.constants import UserRole, DriverStatus
from src.core.users.models import (
    User,
    DriverProfile,
    UserCreateDTO,
    DriverProfileCreateDTO,
    DriverLocationDTO,
)


class TestUser:
    """Тесты для модели User."""
    
    def test_create_user(self, sample_user_data: dict) -> None:
        """Проверяет создание пользователя."""
        user = User(**sample_user_data)
        
        assert user.id == sample_user_data["id"]
        assert user.username == sample_user_data["username"]
        assert user.first_name == sample_user_data["first_name"]
        assert user.last_name == sample_user_data["last_name"]
        assert user.language == sample_user_data["language"]
    
    def test_user_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        user = User(id=123, first_name="Тест")
        
        assert user.username is None
        assert user.last_name is None
        assert user.phone is None
        assert user.language == "ru"
        assert user.role == UserRole.PASSENGER
        assert user.rating == 5.0
        assert user.trips_count == 0
        assert user.is_blocked is False
    
    def test_user_full_name_with_last_name(self) -> None:
        """Проверяет полное имя с фамилией."""
        user = User(id=123, first_name="Иван", last_name="Петров")
        
        assert user.full_name == "Иван Петров"
    
    def test_user_full_name_without_last_name(self) -> None:
        """Проверяет полное имя без фамилии."""
        user = User(id=123, first_name="Иван")
        
        assert user.full_name == "Иван"
    
    def test_user_display_name_with_username(self) -> None:
        """Проверяет отображаемое имя с username."""
        user = User(id=123, first_name="Иван", username="ivan_test")
        
        assert user.display_name == "@ivan_test"
    
    def test_user_display_name_without_username(self) -> None:
        """Проверяет отображаемое имя без username."""
        user = User(id=123, first_name="Иван", last_name="Петров")
        
        assert user.display_name == "Иван Петров"
    
    def test_user_rating_bounds(self) -> None:
        """Проверяет границы рейтинга."""
        # Минимальный рейтинг
        user = User(id=123, first_name="Тест", rating=1.0)
        assert user.rating == 1.0
        
        # Максимальный рейтинг
        user = User(id=123, first_name="Тест", rating=5.0)
        assert user.rating == 5.0
    
    def test_user_rating_validation(self) -> None:
        """Проверяет валидацию рейтинга."""
        with pytest.raises(ValueError):
            User(id=123, first_name="Тест", rating=0.5)  # Меньше минимума
        
        with pytest.raises(ValueError):
            User(id=123, first_name="Тест", rating=5.5)  # Больше максимума
    
    def test_user_roles(self) -> None:
        """Проверяет разные роли пользователя."""
        passenger = User(id=1, first_name="Тест", role=UserRole.PASSENGER)
        driver = User(id=2, first_name="Тест", role=UserRole.DRIVER)
        admin = User(id=3, first_name="Тест", role=UserRole.ADMIN)
        
        assert passenger.role == UserRole.PASSENGER
        assert driver.role == UserRole.DRIVER
        assert admin.role == UserRole.ADMIN


class TestDriverProfile:
    """Тесты для модели DriverProfile."""
    
    def test_create_driver_profile(self, sample_driver_data: dict) -> None:
        """Проверяет создание профиля водителя."""
        profile = DriverProfile(**sample_driver_data)
        
        assert profile.user_id == sample_driver_data["user_id"]
        assert profile.car_brand == sample_driver_data["car_brand"]
        assert profile.car_model == sample_driver_data["car_model"]
        assert profile.car_color == sample_driver_data["car_color"]
        assert profile.car_plate == sample_driver_data["car_plate"]
    
    def test_driver_profile_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        profile = DriverProfile(
            user_id=123,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
        )
        
        assert profile.status == DriverStatus.OFFLINE
        assert profile.is_verified is False
        assert profile.completed_orders == 0
        assert profile.cancelled_orders == 0
        assert profile.total_earnings == 0.0
        assert profile.balance_stars == 0
    
    def test_driver_car_info(self) -> None:
        """Проверяет информацию об автомобиле."""
        profile = DriverProfile(
            user_id=123,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
        )
        
        assert profile.car_info == "Toyota Camry (Белый), АА1234ВВ"
    
    def test_driver_is_online(self) -> None:
        """Проверяет свойство is_online."""
        offline_driver = DriverProfile(
            user_id=1,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
            status=DriverStatus.OFFLINE,
        )
        
        online_driver = DriverProfile(
            user_id=2,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
            status=DriverStatus.ONLINE,
        )
        
        assert offline_driver.is_online is False
        assert online_driver.is_online is True
    
    def test_driver_is_available(self) -> None:
        """Проверяет свойство is_available."""
        # Офлайн и не верифицирован
        profile1 = DriverProfile(
            user_id=1,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
            status=DriverStatus.OFFLINE,
            is_verified=False,
        )
        
        # Онлайн, но не верифицирован
        profile2 = DriverProfile(
            user_id=2,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
            status=DriverStatus.ONLINE,
            is_verified=False,
        )
        
        # Онлайн и верифицирован
        profile3 = DriverProfile(
            user_id=3,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
            status=DriverStatus.ONLINE,
            is_verified=True,
        )
        
        # Занят
        profile4 = DriverProfile(
            user_id=4,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
            status=DriverStatus.BUSY,
            is_verified=True,
        )
        
        assert profile1.is_available is False
        assert profile2.is_available is False
        assert profile3.is_available is True
        assert profile4.is_available is False


class TestUserCreateDTO:
    """Тесты для DTO создания пользователя."""
    
    def test_create_dto(self) -> None:
        """Проверяет создание DTO."""
        dto = UserCreateDTO(
            id=123,
            username="test_user",
            first_name="Тест",
            last_name="Пользователь",
            language="uk",
        )
        
        assert dto.id == 123
        assert dto.username == "test_user"
        assert dto.first_name == "Тест"
        assert dto.last_name == "Пользователь"
        assert dto.language == "uk"
    
    def test_dto_defaults(self) -> None:
        """Проверяет значения по умолчанию в DTO."""
        dto = UserCreateDTO(id=123, first_name="Тест")
        
        assert dto.username is None
        assert dto.last_name is None
        assert dto.language == "ru"
    
    def test_dto_minimal(self) -> None:
        """Проверяет минимальное создание DTO."""
        dto = UserCreateDTO(id=123, first_name="Тест")
        
        assert dto.id == 123
        assert dto.first_name == "Тест"


class TestDriverProfileCreateDTO:
    """Тесты для DTO создания профиля водителя."""
    
    def test_create_dto(self) -> None:
        """Проверяет создание DTO."""
        dto = DriverProfileCreateDTO(
            user_id=123,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
            car_year=2020,
        )
        
        assert dto.user_id == 123
        assert dto.car_brand == "Toyota"
        assert dto.car_model == "Camry"
        assert dto.car_color == "Белый"
        assert dto.car_plate == "АА1234ВВ"
        assert dto.car_year == 2020
    
    def test_dto_optional_year(self) -> None:
        """Проверяет опциональность года выпуска."""
        dto = DriverProfileCreateDTO(
            user_id=123,
            car_brand="Toyota",
            car_model="Camry",
            car_color="Белый",
            car_plate="АА1234ВВ",
        )
        
        assert dto.car_year is None


class TestDriverLocationDTO:
    """Тесты для DTO геолокации водителя."""
    
    def test_create_dto(self) -> None:
        """Проверяет создание DTO."""
        dto = DriverLocationDTO(
            driver_id=123,
            latitude=50.4501,
            longitude=30.5234,
        )
        
        assert dto.driver_id == 123
        assert dto.latitude == 50.4501
        assert dto.longitude == 30.5234
