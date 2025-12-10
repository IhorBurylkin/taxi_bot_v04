# src/web/views/orders.py
"""
Страница управления заказами.
"""

from __future__ import annotations

from nicegui import ui

from src.web.components.header import create_header
from src.web.components.sidebar import create_sidebar


@ui.page("/orders")
async def orders_page() -> None:
    """Страница списка заказов."""
    create_header()
    
    with ui.row().classes("w-full"):
        create_sidebar()
        
        with ui.column().classes("flex-grow p-4"):
            ui.label("📋 Заказы").classes("text-2xl font-bold mb-4")
            
            # Фильтры
            with ui.row().classes("gap-4 mb-4"):
                ui.select(
                    ["Все", "Активные", "Завершённые", "Отменённые"],
                    value="Все",
                    label="Статус",
                )
                ui.input(label="Поиск по ID")
                ui.button("🔍 Найти")
            
            # Таблица заказов
            columns = [
                {"name": "id", "label": "ID", "field": "id", "align": "left"},
                {"name": "status", "label": "Статус", "field": "status"},
                {"name": "passenger", "label": "Пассажир", "field": "passenger"},
                {"name": "driver", "label": "Водитель", "field": "driver"},
                {"name": "fare", "label": "Стоимость", "field": "fare", "align": "right"},
                {"name": "created", "label": "Создан", "field": "created"},
            ]
            
            # Демо-данные
            rows = [
                {
                    "id": "ORD-001",
                    "status": "🟢 Активен",
                    "passenger": "Иван П.",
                    "driver": "Сергей М.",
                    "fare": "₽ 350",
                    "created": "12:34",
                },
                {
                    "id": "ORD-002",
                    "status": "✅ Завершён",
                    "passenger": "Мария К.",
                    "driver": "Дмитрий Л.",
                    "fare": "₽ 520",
                    "created": "11:22",
                },
            ]
            
            ui.table(columns=columns, rows=rows).classes("w-full")
