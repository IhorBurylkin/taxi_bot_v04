# src/web_client/views/tracking.py
"""
Страница отслеживания текущей поездки.
"""

from __future__ import annotations

from nicegui import ui

from src.web_client.components.header import create_client_header


@ui.page("/tracking")
async def tracking_page() -> None:
    """Страница отслеживания поездки."""
    create_client_header()
    
    with ui.column().classes("w-full max-w-2xl mx-auto p-4"):
        ui.label("📍 Отслеживание поездки").classes("text-3xl font-bold mb-6")
        
        # Статус заказа
        with ui.card().classes("w-full p-6 mb-6"):
            ui.label("Статус: Поиск водителя...").classes("text-xl font-semibold mb-4")
            
            ui.linear_progress(indeterminate=True).classes("mb-4")
            
            ui.label("⏱️ Ожидайте, водитель скоро будет назначен").classes("text-gray-600")
        
        # Информация о маршруте
        with ui.card().classes("w-full p-6"):
            ui.label("Маршрут").classes("text-xl font-bold mb-4")
            
            with ui.row().classes("items-center mb-2"):
                ui.label("📍").classes("text-2xl mr-2")
                ui.label("Откуда: [Адрес загружается...]").classes("text-lg")
            
            with ui.row().classes("items-center"):
                ui.label("🏁").classes("text-2xl mr-2")
                ui.label("Куда: [Адрес загружается...]").classes("text-lg")
        
        # Кнопка отмены
        ui.button(
            "❌ Отменить заказ",
            on_click=lambda: _cancel_order()
        ).classes("w-full mt-6").props("color=negative")


async def _cancel_order() -> None:
    """Отменяет текущий заказ."""
    # TODO: Интеграция с OrderService
    ui.notify("Заказ отменён", type="warning")
    ui.open("/")
