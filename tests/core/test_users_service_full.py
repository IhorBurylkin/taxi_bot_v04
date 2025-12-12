import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.users.service import UserService
from src.core.users.models import User, DriverProfile, UserCreateDTO, DriverProfileCreateDTO, DriverLocationDTO
from src.common.constants import UserRole, DriverStatus
from src.infra.event_bus import EventTypes

@pytest.fixture
def mock_settings():
    with patch("src.config.settings") as mock:
        mock.redis_ttl.PROFILE_TTL = 300
        mock.redis_ttl.LAST_SEEN_TTL = 300
        
        # Logger
        mock.logging.LOG_LEVEL = "DEBUG"
        mock.logging.LOG_FORMAT = "colored"
        mock.logging.LOG_TO_FILE = False
        mock.logging.LOG_FILE_PATH = "logs/app.log"
        mock.logging.LOG_MAX_BYTES = 10485760
        mock.logging.LOG_BACKUP_COUNT = 5
        mock.system.ENVIRONMENT = "development"
        
        yield mock

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def mock_event_bus():
    return AsyncMock()

@pytest.fixture
def user_service(mock_db, mock_redis, mock_event_bus, mock_settings):
    # Patch Repositories
    with patch("src.core.users.service.UserRepository") as user_repo_cls, \
         patch("src.core.users.service.DriverRepository") as driver_repo_cls:
        
        user_repo_mock = AsyncMock()
        driver_repo_mock = AsyncMock()
        
        user_repo_cls.return_value = user_repo_mock
        driver_repo_cls.return_value = driver_repo_mock
        
        service = UserService(mock_db, mock_redis, mock_event_bus)
        service._user_repo = user_repo_mock
        service._driver_repo = driver_repo_mock
        
        return service

# =============================================================================
# User Tests
# =============================================================================

@pytest.mark.asyncio
async def test_get_user_cache_hit(user_service, mock_redis):
    user = User(id=1, telegram_id=1, username="test", first_name="Test", role=UserRole.PASSENGER)
    mock_redis.get_model.return_value = user
    
    result = await user_service.get_user(1)
    assert result == user
    mock_redis.get_model.assert_called_once()
    user_service._user_repo.get_by_id.assert_not_called()

@pytest.mark.asyncio
async def test_get_user_cache_miss(user_service, mock_redis):
    user = User(id=1, telegram_id=1, username="test", first_name="Test", role=UserRole.PASSENGER)
    mock_redis.get_model.return_value = None
    user_service._user_repo.get_by_id.return_value = user
    
    result = await user_service.get_user(1)
    assert result == user
    mock_redis.get_model.assert_called_once()
    user_service._user_repo.get_by_id.assert_called_once_with(1)
    mock_redis.set_model.assert_called_once()

@pytest.mark.asyncio
async def test_register_user(user_service, mock_redis):
    dto = UserCreateDTO(id=1, username="test", first_name="Test")
    user = User(id=1, telegram_id=1, username="test", first_name="Test", role=UserRole.PASSENGER)
    user_service._user_repo.create.return_value = user
    
    result = await user_service.register_user(dto)
    assert result == user
    user_service._user_repo.create.assert_called_once_with(dto)
    mock_redis.delete.assert_called_once()

@pytest.mark.asyncio
async def test_update_user(user_service, mock_redis):
    user = User(id=1, telegram_id=1, username="test", first_name="Test", role=UserRole.PASSENGER)
    user_service._user_repo.update.return_value = True
    
    result = await user_service.update_user(user)
    assert result is True
    user_service._user_repo.update.assert_called_once_with(user)
    mock_redis.delete.assert_called_once()

@pytest.mark.asyncio
async def test_set_user_role(user_service, mock_redis):
    user_service._user_repo.set_role.return_value = True
    
    result = await user_service.set_user_role(1, UserRole.DRIVER)
    assert result is True
    user_service._user_repo.set_role.assert_called_once_with(1, UserRole.DRIVER)
    mock_redis.delete.assert_called_once()

# =============================================================================
# Driver Tests
# =============================================================================

@pytest.mark.asyncio
async def test_get_driver_profile_cache_hit(user_service, mock_redis):
    profile = DriverProfile(user_id=1, car_brand="Tesla", car_model="Model S", car_color="White", car_plate="A111AA", is_verified=True)
    mock_redis.get_model.return_value = profile
    
    result = await user_service.get_driver_profile(1)
    assert result == profile
    mock_redis.get_model.assert_called_once()
    user_service._driver_repo.get_by_user_id.assert_not_called()

@pytest.mark.asyncio
async def test_get_driver_profile_cache_miss(user_service, mock_redis):
    profile = DriverProfile(user_id=1, car_brand="Tesla", car_model="Model S", car_color="White", car_plate="A111AA", is_verified=True)
    mock_redis.get_model.return_value = None
    user_service._driver_repo.get_by_user_id.return_value = profile
    
    result = await user_service.get_driver_profile(1)
    assert result == profile
    mock_redis.get_model.assert_called_once()
    user_service._driver_repo.get_by_user_id.assert_called_once_with(1)
    mock_redis.set_model.assert_called_once()

@pytest.mark.asyncio
async def test_register_driver_success(user_service, mock_redis):
    dto = DriverProfileCreateDTO(user_id=1, car_brand="Tesla", car_model="Model S", car_color="White", car_plate="A111AA")
    user = User(id=1, telegram_id=1, username="test", first_name="Test", role=UserRole.PASSENGER)
    profile = DriverProfile(user_id=1, car_brand="Tesla", car_model="Model S", car_color="White", car_plate="A111AA", is_verified=False)
    
    user_service.get_user = AsyncMock(return_value=user)
    user_service._driver_repo.create.return_value = profile
    user_service.set_user_role = AsyncMock(return_value=True)
    
    result = await user_service.register_driver(dto)
    assert result == profile
    user_service._driver_repo.create.assert_called_once_with(dto)
    user_service.set_user_role.assert_called_once_with(1, UserRole.DRIVER)
    mock_redis.delete.assert_called_once()

@pytest.mark.asyncio
async def test_register_driver_user_not_found(user_service):
    dto = DriverProfileCreateDTO(user_id=1, car_brand="Tesla", car_model="Model S", car_color="White", car_plate="A111AA")
    user_service.get_user = AsyncMock(return_value=None)
    
    result = await user_service.register_driver(dto)
    assert result is None
    user_service._driver_repo.create.assert_not_called()

@pytest.mark.asyncio
async def test_set_driver_online_success(user_service, mock_redis, mock_event_bus):
    profile = DriverProfile(user_id=1, car_brand="Tesla", car_model="Model S", car_color="White", car_plate="A111AA", is_verified=True)
    user_service.get_driver_profile = AsyncMock(return_value=profile)
    user_service._driver_repo.update_status.return_value = True
    
    result = await user_service.set_driver_online(1)
    assert result is True
    user_service._driver_repo.update_status.assert_called_once_with(1, DriverStatus.ONLINE)
    mock_redis.delete.assert_called_once()
    mock_event_bus.publish.assert_called_once()
    assert mock_event_bus.publish.call_args[0][0].event_type == EventTypes.DRIVER_ONLINE

@pytest.mark.asyncio
async def test_set_driver_online_not_verified(user_service):
    profile = DriverProfile(user_id=1, car_brand="Tesla", car_model="Model S", car_color="White", car_plate="A111AA", is_verified=False)
    user_service.get_driver_profile = AsyncMock(return_value=profile)
    
    result = await user_service.set_driver_online(1)
    assert result is False
    user_service._driver_repo.update_status.assert_not_called()

@pytest.mark.asyncio
async def test_set_driver_offline(user_service, mock_redis, mock_event_bus):
    user_service._driver_repo.update_status.return_value = True
    
    result = await user_service.set_driver_offline(1)
    assert result is True
    user_service._driver_repo.update_status.assert_called_once_with(1, DriverStatus.OFFLINE)
    mock_redis.delete.assert_called_once()
    mock_redis.georem.assert_called_once()
    mock_event_bus.publish.assert_called_once()
    assert mock_event_bus.publish.call_args[0][0].event_type == EventTypes.DRIVER_OFFLINE

@pytest.mark.asyncio
async def test_update_driver_location(user_service, mock_redis):
    dto = DriverLocationDTO(driver_id=1, latitude=10.0, longitude=20.0)
    user_service._driver_repo.update_location.return_value = True
    
    result = await user_service.update_driver_location(dto)
    assert result is True
    user_service._driver_repo.update_location.assert_called_once_with(1, 10.0, 20.0)
    mock_redis.geoadd.assert_called_once()
    mock_redis.set.assert_called_once()
    mock_redis.delete.assert_called_once()

@pytest.mark.asyncio
async def test_get_online_drivers(user_service):
    user_service._driver_repo.get_online_drivers.return_value = []
    result = await user_service.get_online_drivers()
    assert result == []
    user_service._driver_repo.get_online_drivers.assert_called_once()
