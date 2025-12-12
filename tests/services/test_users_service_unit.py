import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.users_service.service import UserService
from src.services.users_service.repository import UserRepository
from src.shared.models.user_dto import CreateUserRequest, UserDTO
from src.shared.models.enums import UserRole

@pytest.mark.asyncio
async def test_register_user():
    # Mock Repository
    repo = MagicMock(spec=UserRepository)
    repo.get_user_by_id = AsyncMock(return_value=None)
    
    expected_user = UserDTO(
        id=123,
        username="test",
        first_name="Test",
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00"
    )
    repo.create_or_update_user = AsyncMock(return_value=expected_user)
    
    # Service
    service = UserService(repo)
    
    # Request
    request = CreateUserRequest(id=123, username="test", first_name="Test")
    
    # Action
    result = await service.register_user(request)
    
    # Assert
    assert result == expected_user
    repo.get_user_by_id.assert_called_once_with(123)
    repo.create_or_update_user.assert_called_once()

@pytest.mark.asyncio
async def test_change_role():
    # Mock Repository
    repo = MagicMock(spec=UserRepository)
    
    existing_user = UserDTO(
        id=123,
        role=UserRole.PASSENGER,
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00"
    )
    repo.get_user_by_id = AsyncMock(return_value=existing_user)
    
    updated_user = existing_user.model_copy(update={"role": UserRole.DRIVER})
    repo.update_user_role = AsyncMock(return_value=updated_user)
    
    # Service
    service = UserService(repo)
    
    # Action
    result = await service.change_role(123, UserRole.DRIVER)
    
    # Assert
    assert result.role == UserRole.DRIVER
    repo.update_user_role.assert_called_once_with(123, UserRole.DRIVER)
