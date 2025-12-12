# src/web/components/sidebar.py
"""
Компонент бокового меню.
"""

from __future__ import annotations

from nicegui import ui


def create_sidebar() -> None:
    """Создаёт боковое меню."""
    with ui.column().classes("bg-gray-100 w-48 min-h-screen p-4"):
        _menu_item("📊 Дашборд", "/")
        _menu_item("📋 Заказы", "/orders")
        _menu_item("🚗 Водители", "/drivers")
        _menu_item("👤 Пассажиры", "/passengers")
        _menu_item("💰 Финансы", "/finance")
        _menu_item("📈 Аналитика", "/analytics")
        
        ui.space()
        
        _menu_item("🔧 Настройки", "/settings")
        _menu_item("❓ Помощь", "/help")


def _menu_item(label: str, path: str) -> None:
    """Создаёт пункт меню."""
    ui.button(
        label,
        on_click=lambda: ui.navigate.to(path),
    ).props("flat align=left").classes("w-full justify-start")
