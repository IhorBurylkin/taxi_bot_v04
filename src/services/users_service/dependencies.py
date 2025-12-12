from src.infra.database import DatabaseManager
from src.services.users_service.repository import UserRepository
from src.services.users_service.service import UserService

def get_database() -> DatabaseManager:
    return DatabaseManager()

def get_user_repository() -> UserRepository:
    db = get_database()
    return UserRepository(db)

def get_user_service() -> UserService:
    repo = get_user_repository()
    return UserService(repo)
