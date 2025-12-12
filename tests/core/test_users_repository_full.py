import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from src.core.users.repository import UserRepository, DriverRepository
from src.core.users.models import User, DriverProfile, UserCreateDTO, DriverProfileCreateDTO
from src.common.constants import UserRole, DriverStatus

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.fetchrow = AsyncMock()
    db.execute = AsyncMock()
    db.fetch = AsyncMock()
    return db

@pytest.fixture
def user_repo(mock_db):
    return UserRepository(mock_db)

@pytest.fixture
def driver_repo(mock_db):
    return DriverRepository(mock_db)

@pytest.mark.asyncio
async def test_user_get_by_id_success(user_repo, mock_db):
    mock_db.fetchrow.return_value = {
        "id": 123,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "phone": "1234567890",
        "language": "ru",
        "role": "passenger",
        "rating": 5.0,
        "trips_count": 10,
        "is_blocked": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    user = await user_repo.get_by_id(123)
    
    assert user is not None
    assert user.id == 123
    assert user.role == UserRole.PASSENGER
    mock_db.fetchrow.assert_called_once()

@pytest.mark.asyncio
async def test_user_get_by_id_not_found(user_repo, mock_db):
    mock_db.fetchrow.return_value = None
    
    user = await user_repo.get_by_id(123)
    
    assert user is None

@pytest.mark.asyncio
async def test_user_create_success(user_repo, mock_db):
    dto = UserCreateDTO(
        id=123,
        username="testuser",
        first_name="Test",
        last_name="User",
        language="ru"
    )
    
    # Mock get_by_id to return the created user
    user_repo.get_by_id = AsyncMock(return_value=User(
        id=123,
        username="testuser",
        first_name="Test",
        last_name="User",
        role=UserRole.PASSENGER,
        rating=5.0,
        trips_count=0,
        is_blocked=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    ))
    
    user = await user_repo.create(dto)
    
    assert user is not None
    assert user.id == 123
    mock_db.execute.assert_called_once()

@pytest.mark.asyncio
async def test_user_update_success(user_repo, mock_db):
    user = User(
        id=123,
        username="updated",
        first_name="Updated",
        role=UserRole.PASSENGER,
        rating=5.0,
        trips_count=0,
        is_blocked=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    result = await user_repo.update(user)
    
    assert result is True
    mock_db.execute.assert_called_once()

@pytest.mark.asyncio
async def test_user_set_role_success(user_repo, mock_db):
    result = await user_repo.set_role(123, UserRole.DRIVER)
    
    assert result is True
    mock_db.execute.assert_called_once()

@pytest.mark.asyncio
async def test_driver_get_by_user_id_success(driver_repo, mock_db):
    mock_db.fetchrow.return_value = {
        "user_id": 123,
        "car_brand": "Toyota",
        "car_model": "Camry",
        "car_color": "White",
        "car_plate": "A123AA",
        "car_year": 2020,
        "license_number": "123456",
        "license_expiry": None,
        "status": "offline",
        "is_verified": True,
        "completed_orders": 10,
        "cancelled_orders": 0,
        "total_earnings": 1000.0,
        "last_latitude": 1.0,
        "last_longitude": 1.0,
        "last_seen": datetime.now(timezone.utc),
        "balance_stars": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    profile = await driver_repo.get_by_user_id(123)
    
    assert profile is not None
    assert profile.user_id == 123
    assert profile.car_brand == "Toyota"
    mock_db.fetchrow.assert_called_once()

@pytest.mark.asyncio
async def test_driver_create_success(driver_repo, mock_db):
    dto = DriverProfileCreateDTO(
        user_id=123,
        car_brand="Toyota",
        car_model="Camry",
        car_color="White",
        car_plate="A123AA",
        car_year=2020
    )
    
    driver_repo.get_by_user_id = AsyncMock(return_value=DriverProfile(
        user_id=123,
        car_brand="Toyota",
        car_model="Camry",
        car_color="White",
        car_plate="A123AA",
        car_year=2020,
        status=DriverStatus.OFFLINE,
        is_verified=False,
        completed_orders=0,
        cancelled_orders=0,
        total_earnings=0.0,
        balance_stars=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    ))
    
    profile = await driver_repo.create(dto)
    
    assert profile is not None
    assert profile.user_id == 123
    mock_db.execute.assert_called_once()

@pytest.mark.asyncio
async def test_driver_update_status_success(driver_repo, mock_db):
    result = await driver_repo.update_status(123, DriverStatus.ONLINE)
    
    assert result is True
    mock_db.execute.assert_called_once()

@pytest.mark.asyncio
async def test_driver_update_location_success(driver_repo, mock_db):
    result = await driver_repo.update_location(123, 1.0, 2.0)
    
    assert result is True
    mock_db.execute.assert_called_once()

@pytest.mark.asyncio
async def test_driver_get_online_drivers_success(driver_repo, mock_db):
    mock_db.fetch.return_value = [
        {
            "user_id": 123,
            "car_brand": "Toyota",
            "car_model": "Camry",
            "car_color": "White",
            "car_plate": "A123AA",
            "car_year": 2020,
            "license_number": "123456",
            "license_expiry": None,
            "status": "online",
            "is_verified": True,
            "completed_orders": 10,
            "cancelled_orders": 0,
            "total_earnings": 1000.0,
            "last_latitude": 1.0,
            "last_longitude": 1.0,
            "last_seen": datetime.now(timezone.utc),
            "balance_stars": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    ]
    
    drivers = await driver_repo.get_online_drivers()
    
    assert len(drivers) == 1
    assert drivers[0].user_id == 123
    mock_db.fetch.assert_called_once()
