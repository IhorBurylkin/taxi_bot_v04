from typing import Optional
from src.services.users_service.repository import UserRepository
from src.shared.models.user_dto import UserDTO, CreateUserRequest, DriverProfileDTO, CreateDriverProfileRequest
from src.shared.models.enums import UserRole
from src.common.logger import log_info, TypeMsg

class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def get_user(self, user_id: int) -> Optional[UserDTO]:
        return await self.repository.get_user_by_id(user_id)

    async def register_user(self, user_data: CreateUserRequest) -> UserDTO:
        """
        Регистрирует пользователя или обновляет данные, если он уже существует.
        Аналог sync_user_profile из старой версии.
        """
        existing_user = await self.repository.get_user_by_id(user_data.id)
        
        if existing_user:
            # Если пользователь уже есть, сохраняем его текущую роль, 
            # чтобы случайно не сбросить водителя в пассажира при повторном /start
            user_data.role = existing_user.role
            await log_info(f"Обновление пользователя {user_data.id}", type_msg=TypeMsg.INFO)
        else:
            await log_info(f"Регистрация нового пользователя {user_data.id}", type_msg=TypeMsg.INFO)
            
        return await self.repository.create_or_update_user(user_data)

    async def change_role(self, user_id: int, new_role: UserRole) -> Optional[UserDTO]:
        """Меняет роль пользователя (Passenger <-> Driver)."""
        user = await self.repository.get_user_by_id(user_id)
        if not user:
            return None
            
        if user.role == new_role:
            return user
            
        updated_user = await self.repository.update_user_role(user_id, new_role)
        await log_info(f"Пользователь {user_id} сменил роль на {new_role}", type_msg=TypeMsg.INFO)
        
        # TODO: Emit event UserRoleChanged (RabbitMQ)
        
        return updated_user

    async def get_driver_profile(self, user_id: int) -> Optional[DriverProfileDTO]:
        return await self.repository.get_driver_profile(user_id)

    async def create_driver_profile(self, user_id: int, profile_data: CreateDriverProfileRequest) -> DriverProfileDTO:
        """Создает профиль водителя и автоматически делает пользователя водителем."""
        profile = await self.repository.create_driver_profile(user_id, profile_data)
        
        # Автоматически повышаем роль до водителя
        await self.change_role(user_id, UserRole.DRIVER)
        
        return profile

    async def get_all_users(self, page: int, size: int) -> dict:
        """Возвращает список пользователей с пагинацией."""
        offset = (page - 1) * size
        users = await self.repository.get_all_users(limit=size, offset=offset)
        total = await self.repository.count_users()
        
        return {
            "items": users,
            "total": total,
            "page": page,
            "size": size
        }
