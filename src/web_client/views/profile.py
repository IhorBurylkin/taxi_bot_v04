# src/web_client/views/profile.py
"""
Страница профиля пользователя.
"""

from __future__ import annotations

from nicegui import ui

from src.web_client.components.header import create_client_header


@ui.page("/profile")
async def profile_page() -> None:
    """Страница профиля пользователя."""
    create_client_header()
    
    with ui.column().classes("w-full max-w-2xl mx-auto p-4"):
        ui.label("👤 Мой профиль").classes("text-3xl font-bold mb-6")
        
        # Информация о пользователе
        with ui.card().classes("w-full p-6 mb-6"):
            ui.label("Личные данные").classes("text-xl font-bold mb-4")
            
            ui.label("Имя").classes("font-semibold mb-2")
            ui.input(placeholder="Имя пользователя", value="Загрузка...").classes("w-full mb-4").props("readonly")
            
            ui.label("Телефон").classes("font-semibold mb-2")
            ui.input(placeholder="+49 123 456789", value="Загрузка...").classes("w-full mb-4").props("readonly")
            
            ui.label("Язык").classes("font-semibold mb-2")
            ui.select(["Русский", "English", "Deutsch"], value="Русский").classes("w-full")
        
        # История поездок
        with ui.card().classes("w-full p-6"):
            ui.label("📋 История поездок").classes("text-xl font-bold mb-4")
            
            ui.label("У вас пока нет завершённых поездок").classes("text-gray-600 text-center")
        
        # Кнопка выхода
        ui.button(
            "🚪 Выйти из аккаунта",
            on_click=lambda: _logout()
        ).classes("w-full mt-6").props("color=negative")


async def _logout() -> None:
    """Выход из аккаунта."""
    # TODO: Интеграция с системой авторизации
    ui.notify("Вы вышли из аккаунта", type="info")
    ui.open("/")
