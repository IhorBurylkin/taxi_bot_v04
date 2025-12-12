# src/web_client/components/header.py
"""
Компонент шапки для клиентского интерфейса.
"""

from __future__ import annotations

from nicegui import ui


def create_client_header() -> None:
    """Создаёт шапку страницы для клиента."""
    with ui.header().classes("items-center justify-between bg-blue-600 text-white"):
        with ui.row().classes("items-center gap-4"):
            ui.label("🚕 Taxi Bot").classes("text-xl font-bold")
        
        with ui.row().classes("items-center gap-2"):
            ui.button("Главная", on_click=lambda: ui.open("/")).props("flat color=white")
            ui.button("Заказать", on_click=lambda: ui.open("/order")).props("flat color=white")
            ui.button("Профиль", on_click=lambda: ui.open("/profile")).props("flat color=white")
