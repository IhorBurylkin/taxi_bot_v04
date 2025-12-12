import httpx
from typing import Optional, List, Dict, Any
from src.config import settings
from src.shared.models.user_dto import UserDTO
from src.shared.models.trip_dto import TripDTO

class BaseClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def close(self):
        await self.client.aclose()

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        response = await self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def _post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        response = await self.client.post(path, json=json)
        response.raise_for_status()
        return response.json()
    
    async def _put(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        response = await self.client.put(path, json=json)
        response.raise_for_status()
        return response.json()

class UsersClient(BaseClient):
    def __init__(self):
        base_url = f"http://{settings.deployment.USERS_SERVICE_HOST}:{settings.deployment.USERS_SERVICE_PORT}/api/v1/users"
        super().__init__(base_url)

    async def get_user(self, user_id: int) -> UserDTO:
        data = await self._get(f"/{user_id}")
        return UserDTO(**data)

    async def get_all_users(self, page: int = 1, size: int = 20) -> Dict[str, Any]:
        """
        Возвращает список пользователей с пагинацией.
        Ожидается ответ вида: { "items": [...], "total": 100, "page": 1, "size": 20 }
        """
        return await self._get("/", params={"page": page, "size": size})

    async def block_user(self, user_id: int, reason: str) -> UserDTO:
        data = await self._post(f"/{user_id}/block", json={"reason": reason})
        return UserDTO(**data)

    async def unblock_user(self, user_id: int) -> UserDTO:
        data = await self._post(f"/{user_id}/unblock")
        return UserDTO(**data)

class TripClient(BaseClient):
    def __init__(self):
        base_url = f"http://{settings.deployment.TRIP_SERVICE_HOST}:{settings.deployment.TRIP_SERVICE_PORT}/api/v1/trips"
        super().__init__(base_url)

    async def get_trip(self, trip_id: str) -> TripDTO:
        data = await self._get(f"/{trip_id}")
        return TripDTO(**data)
    
    async def get_all_trips(self, page: int = 1, size: int = 20) -> Dict[str, Any]:
        return await self._get("/", params={"page": page, "size": size})

    async def cancel_trip(self, trip_id: str, reason: str) -> TripDTO:
        data = await self._post(f"/{trip_id}/cancel", json={"reason": reason})
        return TripDTO(**data)
