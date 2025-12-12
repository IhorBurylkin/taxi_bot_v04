# src/web_client/views/home.py
"""
Главная страница клиентского интерфейса.
"""

from __future__ import annotations

from nicegui import ui

from src.web_client.components.header import create_client_header
from src.common.localization import get_text


@ui.page("/")
async def home_page() -> None:
    """Главная страница клиента."""
    create_client_header()
    
    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        # Заголовок
        ui.label("🚕 Taxi Bot").classes("text-4xl font-bold mb-2 text-center")
        ui.label("Быстрый и удобный заказ такси").classes("text-xl text-gray-600 mb-8 text-center")
        
        # Карточки действий
        with ui.row().classes("gap-4 w-full justify-center"):
            await _create_action_card(
                "🗺️",
                "Заказать такси",
                "Создать новый заказ",
                "/order"
            )
            await _create_action_card(
                "📍",
                "Отследить поездку",
                "Посмотреть текущую поездку",
                "/tracking"
            )
            await _create_action_card(
                "👤",
                "Мой профиль",
                "Управление профилем",
                "/profile"
            )
        
        # Преимущества
        ui.label("Почему выбирают нас?").classes("text-2xl font-bold mt-12 mb-6 text-center")
        
        with ui.row().classes("gap-4 w-full"):
            await _create_feature_card("⚡", "Быстро", "Поиск водителя за секунды")
            await _create_feature_card("💰", "Выгодно", "Прозрачные цены без скрытых комиссий")
            await _create_feature_card("🔒", "Безопасно", "Проверенные водители и защита данных")


async def _create_action_card(
    icon: str,
    title: str,
    description: str,
    link: str,
) -> None:
    """Создаёт карточку действия."""
    with ui.card().classes("p-6 cursor-pointer hover:shadow-lg transition-shadow").on("click", lambda: ui.open(link)):
        ui.label(icon).classes("text-6xl text-center mb-4")
        ui.label(title).classes("text-xl font-bold text-center mb-2")
        ui.label(description).classes("text-sm text-gray-600 text-center")


async def _create_feature_card(
    icon: str,
    title: str,
    description: str,
) -> None:
    """Создаёт карточку преимущества."""
    with ui.card().classes("p-4 flex-1"):
        ui.label(icon).classes("text-4xl mb-2")
        ui.label(title).classes("text-lg font-semibold mb-1")
        ui.label(description).classes("text-sm text-gray-600")
