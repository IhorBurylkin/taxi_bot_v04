from __future__ import annotations

from nicegui import ui
from typing import Any, Dict, Optional, Tuple

from src.common.localization import get_text
from src.common.logger import log_info
from src.web_client.components.address_input import AddressInput
from src.web_client.infra.api_clients import TripClient, PricingClient, UsersClient
from src.web_client.services.gmaps_service import fetch_route_info

class OrderPage:
    def __init__(
        self,
        user_id: int,
        user_lang: str,
        role: str,
        on_close: Optional[callable] = None,
        on_nav_click: Optional[callable] = None,
    ):
        self.user_id = user_id
        self.lang = user_lang
        self.role = role
        self.on_close = on_close
        self.on_nav_click = on_nav_click
        
        self.trip_client = TripClient()
        self.pricing_client = PricingClient()
        self.users_client = UsersClient()
        
        self.address_from: Dict[str, Any] = {}
        self.address_to: Dict[str, Any] = {}
        self.price_info: Dict[str, Any] = {}
        self.dialog: Optional[ui.dialog] = None
        self.input_from: Optional[AddressInput] = None
        self.input_to: Optional[AddressInput] = None
        self.price_label: Optional[ui.label] = None
        self.order_btn: Optional[ui.button] = None

    def _t(self, key: str, **kwargs) -> str:
        return get_text(key, self.lang, **kwargs)

    async def show(self):
        with ui.dialog().props('persistent maximized') as self.dialog, ui.card().classes('w-full h-full p-0'):
            with ui.column().classes('w-full h-full p-4'):
                # Header
                with ui.row().classes('w-full items-center justify-between mb-4'):
                    ui.label(self._t("new_order")).classes('text-xl font-bold')
                    ui.button(icon='close', on_click=self.close).props('flat round')

                # Inputs
                self.input_from = AddressInput(
                    label=self._t("address_from"),
                    placeholder=self._t("enter_address"),
                    lang=self.lang,
                    on_change=self._on_from_change,
                    user_id=self.user_id
                )
                self.input_from.render()

                self.input_to = AddressInput(
                    label=self._t("address_to"),
                    placeholder=self._t("enter_address"),
                    lang=self.lang,
                    on_change=self._on_to_change,
                    user_id=self.user_id
                )
                self.input_to.render()

                # Price info
                self.price_label = ui.label().classes('text-lg font-bold mt-4')
                
                # Order button
                self.order_btn = ui.button(self._t("order_taxi"), on_click=self._create_order).classes('w-full mt-auto')
                self.order_btn.disable()

        self.dialog.open()

    async def _on_from_change(self, data: Dict[str, Any]):
        self.address_from = data
        await self._calculate_price()

    async def _on_to_change(self, data: Dict[str, Any]):
        self.address_to = data
        await self._calculate_price()

    async def _calculate_price(self):
        if not self.address_from or not self.address_to:
            return

        try:
            # Calculate price via Pricing Service
            origin = f"{self.address_from['geometry']['location']['lat']},{self.address_from['geometry']['location']['lng']}"
            destination = f"{self.address_to['geometry']['location']['lat']},{self.address_to['geometry']['location']['lng']}"
            
            route_data = {
                "origin": origin,
                "destination": destination,
                "user_id": self.user_id
            }
            
            self.price_info = await self.pricing_client.calculate_price(route_data)
            
            price = self.price_info.get("price", 0)
            currency = self.price_info.get("currency", "EUR")
            
            if self.price_label:
                self.price_label.text = f"{price} {currency}"
            if self.order_btn:
                self.order_btn.enable()
            
        except Exception as e:
            await log_info(f"Error calculating price: {e}", type_msg="error")
            ui.notify("Error calculating price", type="negative")

    async def _create_order(self):
        try:
            order_data = {
                "user_id": self.user_id,
                "from_address": self.address_from,
                "to_address": self.address_to,
                "price": self.price_info.get("price"),
                # ... other fields
            }
            await self.trip_client.create_order(order_data)
            ui.notify(self._t("order_created"), type="positive")
            self.close()
            if self.on_nav_click:
                self.on_nav_click('ride') # Navigate to ride screen
        except Exception as e:
            await log_info(f"Error creating order: {e}", type_msg="error")
            ui.notify("Error creating order", type="negative")

    def close(self):
        if self.dialog:
            self.dialog.close()
        if self.on_close:
            self.on_close()
