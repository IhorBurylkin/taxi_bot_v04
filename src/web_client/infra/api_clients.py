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
        print(f"DEBUG: UsersClient base_url={base_url}")
        super().__init__(base_url)

    async def get_me(self, user_id: int) -> UserDTO:
        data = await self._get(f"/{user_id}")
        return UserDTO(**data)

    async def update_status(self, user_id: int, status: str) -> UserDTO:
        data = await self._put(f"/{user_id}/status", json={"status": status})
        return UserDTO(**data)
    
    async def auth_telegram(self, init_data: str) -> Dict[str, Any]:
        """Валидация initData от Telegram WebApp"""
        return await self._post("/auth/telegram", json={"init_data": init_data})

    async def update_profile(self, user_id: int, data: Dict[str, Any]) -> UserDTO:
        response_data = await self._put(f"/{user_id}", json=data)
        return UserDTO(**response_data)

class TripClient(BaseClient):
    def __init__(self):
        base_url = f"http://{settings.deployment.TRIP_SERVICE_HOST}:{settings.deployment.TRIP_SERVICE_PORT}/api/v1/trips"
        super().__init__(base_url)

    async def create_order(self, order_data: Dict[str, Any]) -> TripDTO:
        # TODO: Use CreateTripRequest DTO when available/confirmed
        data = await self._post("/", json=order_data)
        return TripDTO(**data)
    
    async def get_active_trip(self, user_id: int) -> Optional[TripDTO]:
        try:
            data = await self._get(f"/active/{user_id}")
            return TripDTO(**data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

class PricingClient(BaseClient):
    def __init__(self):
        base_url = f"http://{settings.deployment.PRICING_SERVICE_HOST}:{settings.deployment.PRICING_SERVICE_PORT}/api/v1/pricing"
        super().__init__(base_url)

    async def calculate_price(self, route_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post("/calculate", json=route_data)
