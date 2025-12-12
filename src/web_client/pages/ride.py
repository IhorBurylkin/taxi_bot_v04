from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from nicegui import ui, background_tasks
import websockets

from src.common.localization import get_text
from src.common.logger import log_info
from src.web_client.components.map_component import MapComponent
from src.web_client.infra.api_clients import TripClient
from src.config import settings

class RidePage:
    def __init__(self, user_id: int, user_lang: str, role: str, on_nav_click: Any | None = None):
        self.user_id = user_id
        self.lang = user_lang
        self.role = role
        self.on_nav_click = on_nav_click
        self.trip_client = TripClient()
        self.map_component = MapComponent()
        self.active_trip = None
        self.ws_task = None
        self.status_label: Optional[ui.label] = None
        self.driver_label: Optional[ui.label] = None

    def _t(self, key: str, **kwargs) -> str:
        return get_text(key, self.lang, **kwargs)

    async def mount(self):
        try:
            self.active_trip = await self.trip_client.get_active_trip(self.user_id)
            
            if not self.active_trip:
                with ui.column().classes('w-full h-full items-center justify-center'):
                    ui.icon('directions_car', size='4rem', color='gray-400')
                    ui.label(self._t("no_active_rides")).classes('text-xl text-gray-500')
                    if self.on_nav_click:
                        ui.button(self._t("back_to_main"), on_click=lambda: self.on_nav_click('main'))
                return

            # Layout
            with ui.column().classes('w-full h-full p-0 relative'):
                self.map_component.render()
                
                # Status card
                with ui.card().classes('absolute bottom-4 left-4 right-4 p-4 z-10'):
                    self.status_label = ui.label(f"Status: {self.active_trip.status}").classes('text-lg font-bold')
                    self.driver_label = ui.label("Driver: ...")
            
            # Start WebSocket connection
            self.ws_task = background_tasks.create(self._ws_loop(), name="ride_ws_loop")
            
        except Exception as e:
            await log_info(f"Error mounting RidePage: {e}", type_msg="error")
            ui.notify("Error loading ride", type="negative")

    async def _ws_loop(self):
        uri = f"ws://realtime_ws_gateway:{settings.deployment.REALTIME_WS_GATEWAY_PORT}/ws/clients/{self.user_id}"
        while True:
            try:
                async with websockets.connect(uri) as websocket:
                    await log_info(f"Connected to WS: {uri}", type_msg="info")
                    while True:
                        msg = await websocket.recv()
                        data = json.loads(msg)
                        await self._handle_ws_message(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await log_info(f"WS Error: {e}", type_msg="error")
                await asyncio.sleep(5) # Retry delay

    async def _handle_ws_message(self, data: dict):
        event_type = data.get("type")
        payload = data.get("data", {})
        
        if event_type == "trip_update":
            status = payload.get("status")
            if self.status_label:
                self.status_label.text = f"Status: {status}"
            
            if status == "finished":
                ui.notify("Ride finished!")
                # Redirect to rating or main
                if self.on_nav_click:
                    self.on_nav_click('main')

        elif event_type == "location_update":
            lat = payload.get("lat")
            lng = payload.get("lng")
            if lat and lng:
                await self.map_component.set_driver_marker(lat, lng)

    async def shutdown(self):
        if self.ws_task:
            self.ws_task.cancel()
        await self.trip_client.close()
