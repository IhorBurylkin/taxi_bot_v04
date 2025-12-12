import asyncio
import json
from typing import Optional
from src.infra.event_bus import EventBus
from src.services.order_matching_service.utils import GeoUtils
from src.services.trip_service.service import TripService # We might need to call TripService via HTTP or just use events
from src.common.logger import log_info, log_error
from src.config import settings
import httpx

class OrderMatchingConsumer:
    def __init__(self, event_bus: EventBus, geo_utils: GeoUtils):
        self.event_bus = event_bus
        self.geo_utils = geo_utils
        self.trip_service_url = f"http://localhost:{settings.deployment.TRIP_SERVICE_PORT}/api/v1/trips"
        self.users_service_url = f"http://localhost:{settings.deployment.USERS_SERVICE_PORT}/api/v1/users"
        self.notifications_url = f"http://localhost:{settings.deployment.NOTIFICATIONS_PORT}/api/notify" # Legacy or new?

    async def start(self):
        await self.event_bus.subscribe("trip.created", self.handle_trip_created)
        await log_info("OrderMatchingConsumer started listening to trip.created")

    async def handle_trip_created(self, event_data: dict):
        """
        Handles new trip creation.
        1. Extract trip details.
        2. Find nearby drivers.
        3. Send notifications (offers).
        """
        try:
            trip_id = event_data.get("trip_id")
            pickup_lat = event_data.get("pickup_lat")
            pickup_lon = event_data.get("pickup_lon")
            
            await log_info(f"Processing new trip {trip_id} at {pickup_lat}, {pickup_lon}")
            
            # 1. Find drivers
            drivers = await self.geo_utils.find_drivers_in_radius(
                pickup_lat, 
                pickup_lon, 
                radius_km=settings.search.DRIVER_SEARCH_RADIUS_KM,
                count=10
            )
            
            if not drivers:
                await log_info(f"No drivers found for trip {trip_id}")
                # TODO: Schedule retry or expand radius
                return

            await log_info(f"Found {len(drivers)} drivers for trip {trip_id}")

            # 2. Notify drivers
            for driver_id, distance in drivers:
                await self.send_offer_to_driver(driver_id, trip_id, distance)

        except Exception as e:
            await log_error(f"Error handling trip.created: {e}")

    async def send_offer_to_driver(self, driver_id: int, trip_id: str, distance: float):
        """
        Sends an offer to a driver via Notifications Service (or Bot directly).
        """
        # For now, we'll assume there is a notification service or we use the bot directly.
        # Since we are in microservices, we should call the Notification Service.
        # But wait, the plan says "Отправлять уведомления (через Notifications Service или напрямую в Bot API пока что)".
        # Let's try to use a placeholder for now, logging the action.
        
        await log_info(f"Sending offer for trip {trip_id} to driver {driver_id} (dist: {distance:.2f}km)")
        
        # In a real implementation, we would POST to Notifications Service
        # payload = {
        #     "user_id": driver_id,
        #     "type": "order_offer",
        #     "data": {"trip_id": trip_id, "distance": distance}
        # }
        # async with httpx.AsyncClient() as client:
        #     await client.post(self.notifications_url, json=payload)
