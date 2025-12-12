# src/web_client/views/order.py
"""
Страница создания заказа такси.
"""

from __future__ import annotations

from nicegui import ui

from src.web_client.components.header import create_client_header


@ui.page("/order")
async def order_page() -> None:
    """Страница создания заказа."""
    create_client_header()
    
    with ui.column().classes("w-full max-w-2xl mx-auto p-4"):
        ui.label("🗺️ Новый заказ").classes("text-3xl font-bold mb-6")
        
        # Форма заказа
        with ui.card().classes("w-full p-6"):
            ui.label("Откуда").classes("font-semibold mb-2")
            from_input = ui.input(
                placeholder="Введите адрес отправления",
                validation={"Обязательное поле": lambda value: len(value) > 0}
            ).classes("w-full mb-4")
            
            ui.label("Куда").classes("font-semibold mb-2")
            to_input = ui.input(
                placeholder="Введите адрес назначения",
                validation={"Обязательное поле": lambda value: len(value) > 0}
            ).classes("w-full mb-4")
            
            ui.label("Комментарий (опционально)").classes("font-semibold mb-2")
            comment_input = ui.textarea(
                placeholder="Дополнительные пожелания",
            ).classes("w-full mb-4")
            
            # Кнопка создания заказа
            ui.button(
                "🚕 Заказать такси",
                on_click=lambda: _create_order(from_input.value, to_input.value, comment_input.value)
            ).classes("w-full")
        
        # Информация о тарифах
        with ui.card().classes("w-full p-6 mt-6"):
            ui.label("📊 Тарифы").classes("text-xl font-bold mb-4")
            ui.label("• Базовая стоимость: 10 EUR").classes("mb-2")
            ui.label("• За километр: 1 EUR").classes("mb-2")
            ui.label("• За минуту: 3 EUR").classes("mb-2")
            ui.label("• Подача: 30 EUR").classes("mb-2")


async def _create_order(from_address: str, to_address: str, comment: str) -> None:
    """Создаёт новый заказ."""
    if not from_address or not to_address:
        ui.notify("Заполните адреса отправления и назначения", type="warning")
        return
    
    # TODO: Интеграция с OrderService
    ui.notify(f"Заказ создан! {from_address} → {to_address}", type="positive")
    ui.open("/tracking")
