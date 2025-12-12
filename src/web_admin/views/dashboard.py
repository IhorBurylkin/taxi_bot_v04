# src/web/views/dashboard.py
"""
Главная страница (дашборд) админ-панели.
"""

from __future__ import annotations

from nicegui import ui

from src.web.components.header import create_header
from src.web.components.sidebar import create_sidebar


@ui.page("/")
async def dashboard_page() -> None:
    """Главная страница дашборда."""
    create_header()
    
    with ui.row().classes("w-full"):
        create_sidebar()
        
        with ui.column().classes("flex-grow p-4"):
            ui.label("📊 Дашборд").classes("text-2xl font-bold mb-4")
            
            # Карточки статистики
            with ui.row().classes("gap-4 mb-4"):
                await _create_stat_card("🚕", "Активные заказы", "12")
                await _create_stat_card("👤", "Онлайн водители", "45")
                await _create_stat_card("💰", "Выручка сегодня", "₽ 15,420")
                await _create_stat_card("⭐", "Средний рейтинг", "4.8")
            
            # График активности
            with ui.card().classes("w-full"):
                ui.label("📈 Активность за день").classes("text-lg font-semibold mb-2")
                ui.label("(График будет добавлен позже)").classes("text-gray-500")


async def _create_stat_card(
    icon: str,
    title: str,
    value: str,
) -> None:
    """Создаёт карточку статистики."""
    with ui.card().classes("p-4"):
        ui.label(f"{icon} {title}").classes("text-sm text-gray-600")
        ui.label(value).classes("text-2xl font-bold")
