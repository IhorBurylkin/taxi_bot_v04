from __future__ import annotations

from nicegui import ui
from typing import Any, Optional

from src.common.localization import get_text
from src.common.logger import log_info
from src.web_client.components.map_component import MapComponent
from src.web_client.infra.api_clients import UsersClient

class MainPage:
    """
    Главная страница с картой и кнопками заказа.
    """

    def __init__(self, user_id: int, user_lang: str, role: str, on_nav_click: Any | None = None):
        self.user_id = user_id
        self.lang = user_lang
        self.role = role
        self.on_nav_click = on_nav_click
        self.map_component = MapComponent()
        self.users_client = UsersClient()
        self.is_working = True
        self.city_coords: tuple[float, float] | None = None

    def _t(self, key: str, **kwargs: Any) -> str:
        return get_text(key, self.lang, **kwargs)

    async def mount(self):
        """Отображает главную страницу."""
        try:
            # Загружаем данные пользователя
            user_data = await self.users_client.get_me(self.user_id)
            
            if user_data:
                if user_data.city_lat is not None and user_data.city_lng is not None:
                    self.city_coords = (float(user_data.city_lat), float(user_data.city_lng))
                    self.map_component.center = self.city_coords
            
            # TODO: Handle driver is_working status (need DriverProfileDTO or similar)
            # For now, assume True or fetch from separate endpoint if needed

            # Полноэкранный контейнер
            with ui.column().classes('w-full h-full p-0 m-0 relative overflow-hidden'):
                
                # Слой карты
                self.map_component.render()
                
                # Запрашиваем актуальное местоположение
                await self.map_component.center_on_user()
                
                # Кнопка центрирования
                if self.role == 'passenger':
                    with ui.button(icon='near_me', on_click=self.map_component.center_on_user).classes('absolute bottom-20 right-4 z-[100] bg-white text-black shadow-lg rounded-full w-10 h-10'):
                        pass

                # Кнопка "Заказать" (для пассажира)
                if self.role == 'passenger':
                    with ui.button(self._t("order_taxi"), on_click=lambda: self.on_nav_click('order') if self.on_nav_click else None).classes('absolute bottom-4 left-4 right-4 z-[100] h-12 text-lg'):
                        pass

        except Exception as e:
            await log_info(f"Error mounting MainPage: {e}", type_msg="error")
            ui.notify("Error loading map", type="negative")

    async def shutdown(self):
        await self.users_client.close()
