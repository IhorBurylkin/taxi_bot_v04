from fastapi import APIRouter, Depends, HTTPException, status
from src.services.users_service.service import UserService
from src.services.users_service.dependencies import get_user_service
from src.shared.models.user_dto import UserDTO, CreateUserRequest, UpdateUserStatusRequest, DriverProfileDTO, CreateDriverProfileRequest
from pydantic import BaseModel
from src.services.users_service.utils import validate_telegram_data
from src.config import settings
from src.shared.models.enums import UserRole

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}", response_model=UserDTO)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.post("/", response_model=UserDTO)
async def register_user(
    user_data: CreateUserRequest,
    service: UserService = Depends(get_user_service)
):
    return await service.register_user(user_data)

@router.patch("/{user_id}/role", response_model=UserDTO)
async def change_role(
    user_id: int,
    request: UpdateUserStatusRequest,
    service: UserService = Depends(get_user_service)
):
    user = await service.change_role(user_id, request.role)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.get("/{user_id}/driver_profile", response_model=DriverProfileDTO)
async def get_driver_profile(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    profile = await service.get_driver_profile(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")
    return profile

@router.post("/{user_id}/driver_profile", response_model=DriverProfileDTO)
async def create_driver_profile(
    user_id: int,
    profile_data: CreateDriverProfileRequest,
    service: UserService = Depends(get_user_service)
):
    # Проверяем, существует ли пользователь
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    return await service.create_driver_profile(user_id, profile_data)

@router.get("/", response_model=dict)
async def get_all_users(
    page: int = 1,
    size: int = 20,
    service: UserService = Depends(get_user_service)
):
    return await service.get_all_users(page, size)

class TelegramAuthRequest(BaseModel):
    init_data: str

@router.post("/auth/telegram", response_model=UserDTO)
async def auth_telegram(
    request: TelegramAuthRequest,
    service: UserService = Depends(get_user_service)
):
    """
    Validates Telegram WebApp initData and returns (or creates) the user.
    """
    # 1. Validate initData
    # Note: We use settings.telegram.BOT_TOKEN. 
    # Ensure it is available in the service environment.
    validated_data = validate_telegram_data(request.init_data, settings.telegram.BOT_TOKEN)
    
    if not validated_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid Telegram initData"
        )
        
    # 2. Extract user info
    tg_user = validated_data.get("user")
    if not tg_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No user data in initData"
        )
        
    user_id = tg_user.get("id")
    username = tg_user.get("username")
    first_name = tg_user.get("first_name")
    last_name = tg_user.get("last_name")
    language_code = tg_user.get("language_code", "en")
    
    # 3. Create or update user
    user_request = CreateUserRequest(
        id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language=language_code,
        role=UserRole.PASSENGER # Default role
    )
    
    user = await service.register_user(user_request)
    return user
