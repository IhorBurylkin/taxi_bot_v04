# src/web/components/header.py
"""
Компонент заголовка страницы.
"""

from __future__ import annotations

from nicegui import ui


def create_header() -> None:
    """Создаёт заголовок страницы."""
    with ui.header().classes("bg-blue-600 text-white"):
        ui.label("🚕 Taxi Bot Admin").classes("text-xl font-bold")
        
        ui.space()
        
        with ui.row().classes("gap-2"):
            ui.button(
                icon="refresh",
                on_click=lambda: ui.notify("Данные обновлены"),
            ).props("flat color=white")
            
            ui.button(
                icon="settings",
                on_click=lambda: ui.navigate.to("/settings"),
            ).props("flat color=white")
            
            ui.button(
                icon="logout",
                on_click=lambda: ui.notify("Выход"),
            ).props("flat color=white")
