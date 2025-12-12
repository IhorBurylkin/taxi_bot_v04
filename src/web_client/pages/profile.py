from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from nicegui import ui

from src.common.localization import get_text
from src.common.logger import log_info
from src.web_client.infra.api_clients import UsersClient
from src.shared.models.user_dto import UserDTO

class ProfilePage:
    """Вкладка профиля пользователя с возможностью редактирования данных."""

    def __init__(
        self, 
        user_id: int, 
        user_lang: str, 
        on_nav_click: Any | None = None,
    ) -> None:
        self.user_id = user_id
        self.lang = user_lang
        self.on_nav_click = on_nav_click
        self.users_client = UsersClient()
        self.user_data: Optional[UserDTO] = None
        self.content_container: Optional[ui.column] = None

    def _t(self, key: str, **kwargs: Any) -> str:
        """Получение локализованной строки."""
        return get_text(key, self.lang, **kwargs)

    async def mount(self) -> None:
        """Монтирует интерфейс профиля."""
        try:
            await log_info("открытие профиля", extra={"user_id": self.user_id})
            
            # Загрузка данных через API Client
            self.user_data = await self.users_client.get_me(self.user_id)
            
            self._build_layout()
            
        except Exception as error:
            await log_info(f"ошибка отображения профиля: {error}", extra={"user_id": self.user_id})
            ui.notify(self._t("profile_empty_hint"), type="negative")

    def _build_layout(self) -> None:
        """Строит layout профиля."""
        if not self.user_data:
            return

        with ui.column().classes('w-full h-full p-4 gap-4') as self.content_container:
            # Заголовок
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(self._t("profile_title")).classes('text-2xl font-bold text-gray-800')
                
                # Кнопка выхода/назад
                if self.on_nav_click:
                    ui.button(icon='arrow_back', on_click=lambda: self.on_nav_click('main')).props('flat round')

            # Карточка пользователя
            with ui.card().classes('w-full p-4'):
                with ui.row().classes('items-center gap-4'):
                    # Аватар (заглушка пока)
                    ui.avatar('person', color='primary', text_color='white').classes('text-2xl')
                    
                    with ui.column().classes('gap-1'):
                        name = f"{self.user_data.first_name or ''} {self.user_data.last_name or ''}".strip()
                        ui.label(name or self._t("unknown_user")).classes('text-lg font-medium')
                        ui.label(self.user_data.phone or "").classes('text-gray-500')

            # Информация
            with ui.card().classes('w-full p-4 gap-2'):
                ui.label(self._t("details")).classes('text-lg font-medium mb-2')
                
                with ui.grid(columns=2).classes('w-full gap-2'):
                    ui.label(self._t("role") + ":").classes('text-gray-600')
                    ui.label(self.user_data.role.value).classes('font-medium')
                    
                    ui.label(self._t("language") + ":").classes('text-gray-600')
                    ui.label(self.user_data.language).classes('font-medium')
                    
                    ui.label("ID:").classes('text-gray-600')
                    ui.label(str(self.user_data.id)).classes('font-medium')

            # Кнопки действий (пример)
            with ui.row().classes('w-full justify-center mt-4'):
                ui.button(self._t("edit"), icon='edit').props('outline').classes('w-full')

    async def shutdown(self) -> None:
        """Очистка ресурсов."""
        await self.users_client.close()
