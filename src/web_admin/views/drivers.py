# src/web/views/drivers.py
"""
Страница управления водителями.
"""

from __future__ import annotations

from nicegui import ui

from src.web.components.header import create_header
from src.web.components.sidebar import create_sidebar


@ui.page("/drivers")
async def drivers_page() -> None:
    """Страница списка водителей."""
    create_header()
    
    with ui.row().classes("w-full"):
        create_sidebar()
        
        with ui.column().classes("flex-grow p-4"):
            ui.label("🚗 Водители").classes("text-2xl font-bold mb-4")
            
            # Фильтры
            with ui.row().classes("gap-4 mb-4"):
                ui.select(
                    ["Все", "Онлайн", "Офлайн", "На заказе"],
                    value="Все",
                    label="Статус",
                )
                ui.input(label="Поиск")
                ui.button("🔍 Найти")
            
            # Таблица водителей
            columns = [
                {"name": "id", "label": "ID", "field": "id", "align": "left"},
                {"name": "name", "label": "Имя", "field": "name"},
                {"name": "status", "label": "Статус", "field": "status"},
                {"name": "car", "label": "Автомобиль", "field": "car"},
                {"name": "rating", "label": "Рейтинг", "field": "rating", "align": "center"},
                {"name": "trips", "label": "Поездок", "field": "trips", "align": "right"},
            ]
            
            # Демо-данные
            rows = [
                {
                    "id": "DRV-001",
                    "name": "Сергей М.",
                    "status": "🟢 Онлайн",
                    "car": "Toyota Camry",
                    "rating": "⭐ 4.9",
                    "trips": "1,234",
                },
                {
                    "id": "DRV-002",
                    "name": "Дмитрий Л.",
                    "status": "🟡 На заказе",
                    "car": "Hyundai Solaris",
                    "rating": "⭐ 4.7",
                    "trips": "856",
                },
            ]
            
            ui.table(columns=columns, rows=rows).classes("w-full")
