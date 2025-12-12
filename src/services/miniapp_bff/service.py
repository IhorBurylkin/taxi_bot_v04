# src/services/miniapp_bff/service.py
"""
Бизнес-логика MiniApp BFF.
Агрегация данных из микросервисов.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from src.services.miniapp_bff.telegram_auth import TelegramInitData

if TYPE_CHECKING:
    from src.infra.redis_client import RedisClient


class MiniAppService:
    """
    Сервис для Telegram Mini App.
    
    Агрегирует данные из:
    - users_service
    - trip_service
    - pricing_service
    - payments_service
    """
    
    def __init__(
        self,
        redis: "RedisClient",
        users_service_url: str = "http://localhost:8084",
        trips_service_url: str = "http://localhost:8085",
        pricing_service_url: str = "http://localhost:8086",
        payments_service_url: str = "http://localhost:8087",
    ) -> None:
        self.redis = redis
        self.users_url = users_service_url
        self.trips_url = trips_service_url
        self.pricing_url = pricing_service_url
        self.payments_url = payments_service_url
        
        # HTTP клиент с таймаутами
        self.http = httpx.AsyncClient(timeout=10.0)
    
    async def close(self) -> None:
        """Закрыть HTTP клиент."""
        await self.http.aclose()
    
    # === ГЛАВНЫЙ ЭКРАН ===
    
    async def get_home_data(self, user_id: int) -> dict[str, Any]:
        """
        Получить данные для главного экрана Mini App.
        
        Агрегирует:
        - Профиль пользователя
        - Активную поездку (если есть)
        - Избранные адреса
        - Баланс (для водителей)
        """
        # Параллельные запросы к сервисам
        profile_task = self._get_user_profile(user_id)
        active_trip_task = self._get_active_trip_rider(user_id)
        
        profile = await profile_task
        active_trip = await active_trip_task
        
        result = {
            "user": profile,
            "active_trip": active_trip,
            "favorites": [],  # TODO: Получить из users_service
            "promotions": [],  # TODO: Акции и скидки
        }
        
        # Если водитель — добавляем баланс
        if profile and profile.get("is_driver"):
            balance = await self._get_driver_balance(user_id)
            result["balance"] = balance
            result["driver_status"] = await self._get_driver_status(user_id)
        
        return result
    
    # === ЗАКАЗ ПОЕЗДКИ ===
    
    async def calculate_fare(
        self,
        pickup_lat: float,
        pickup_lon: float,
        dropoff_lat: float,
        dropoff_lon: float,
        vehicle_class: str = "standard",
    ) -> dict[str, Any]:
        """
        Рассчитать стоимость поездки.
        
        Возвращает цену в EUR и Stars для разных классов авто.
        """
        try:
            response = await self.http.post(
                f"{self.pricing_url}/api/v1/pricing/calculate",
                json={
                    "pickup_lat": pickup_lat,
                    "pickup_lon": pickup_lon,
                    "dropoff_lat": dropoff_lat,
                    "dropoff_lon": dropoff_lon,
                    "vehicle_class": vehicle_class,
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def create_trip(
        self,
        user_id: int,
        pickup_lat: float,
        pickup_lon: float,
        pickup_address: str,
        dropoff_lat: float,
        dropoff_lon: float,
        dropoff_address: str,
        vehicle_class: str = "standard",
        payment_method: str = "stars",
    ) -> dict[str, Any]:
        """
        Создать заказ поездки.
        
        1. Создаёт поездку в trips_service
        2. Запускает поиск водителя
        """
        try:
            response = await self.http.post(
                f"{self.trips_url}/api/v1/trips",
                json={
                    "rider_id": user_id,
                    "pickup_location": {
                        "lat": pickup_lat,
                        "lon": pickup_lon,
                        "address": pickup_address,
                    },
                    "dropoff_location": {
                        "lat": dropoff_lat,
                        "lon": dropoff_lon,
                        "address": dropoff_address,
                    },
                    "vehicle_class": vehicle_class,
                    "payment_method": payment_method,
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def get_trip_status(self, trip_id: str) -> dict[str, Any]:
        """Получить статус поездки."""
        try:
            response = await self.http.get(
                f"{self.trips_url}/api/v1/trips/{trip_id}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def cancel_trip(self, trip_id: str, reason: str | None = None) -> dict[str, Any]:
        """Отменить поездку."""
        try:
            response = await self.http.post(
                f"{self.trips_url}/api/v1/trips/{trip_id}/cancel",
                json={"reason": reason},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # === ИСТОРИЯ И ПРОФИЛЬ ===
    
    async def get_trip_history(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Получить историю поездок."""
        try:
            response = await self.http.get(
                f"{self.trips_url}/api/v1/trips",
                params={
                    "rider_id": user_id,
                    "limit": limit,
                    "offset": offset,
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "trips": []}
    
    async def update_profile(
        self,
        user_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Обновить профиль пользователя."""
        try:
            response = await self.http.patch(
                f"{self.users_url}/api/v1/users/{user_id}",
                json=data,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # === ВОДИТЕЛЬ ===
    
    async def driver_go_online(self, driver_id: int) -> dict[str, Any]:
        """Водитель выходит на линию."""
        try:
            response = await self.http.post(
                f"{self.users_url}/api/v1/drivers/{driver_id}/online"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def driver_go_offline(self, driver_id: int) -> dict[str, Any]:
        """Водитель уходит с линии."""
        try:
            response = await self.http.post(
                f"{self.users_url}/api/v1/drivers/{driver_id}/offline"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def update_driver_location(
        self,
        driver_id: int,
        lat: float,
        lon: float,
    ) -> dict[str, Any]:
        """Обновить геолокацию водителя."""
        try:
            response = await self.http.post(
                f"{self.users_url}/api/v1/drivers/{driver_id}/location",
                json={"lat": lat, "lon": lon},
            )
            response.raise_for_status()
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}
    
    async def accept_trip(self, trip_id: str, driver_id: int) -> dict[str, Any]:
        """Водитель принимает заказ."""
        try:
            response = await self.http.post(
                f"{self.trips_url}/api/v1/trips/{trip_id}/accept",
                params={"driver_id": driver_id},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def start_trip(self, trip_id: str) -> dict[str, Any]:
        """Начать поездку."""
        try:
            response = await self.http.post(
                f"{self.trips_url}/api/v1/trips/{trip_id}/start"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def complete_trip(self, trip_id: str) -> dict[str, Any]:
        """Завершить поездку."""
        try:
            response = await self.http.post(
                f"{self.trips_url}/api/v1/trips/{trip_id}/complete"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # === ПРИВАТНЫЕ МЕТОДЫ ===
    
    async def _get_user_profile(self, user_id: int) -> dict[str, Any] | None:
        """Получить профиль пользователя."""
        try:
            response = await self.http.get(
                f"{self.users_url}/api/v1/users/{user_id}"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
    
    async def _get_active_trip_rider(self, user_id: int) -> dict[str, Any] | None:
        """Получить активную поездку пассажира."""
        try:
            response = await self.http.get(
                f"{self.trips_url}/api/v1/trips/active/rider/{user_id}"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
    
    async def _get_driver_balance(self, driver_id: int) -> dict[str, Any] | None:
        """Получить баланс водителя."""
        try:
            response = await self.http.get(
                f"{self.payments_url}/api/v1/balances/{driver_id}"
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
    
    async def _get_driver_status(self, driver_id: int) -> dict[str, Any] | None:
        """Получить статус водителя (online/offline)."""
        try:
            response = await self.http.get(
                f"{self.users_url}/api/v1/drivers/{driver_id}"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return {
                "is_online": data.get("is_working", False),
                "status": data.get("status"),
            }
        except Exception:
            return None
