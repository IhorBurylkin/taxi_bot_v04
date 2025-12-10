# src/config/__init__.py
"""
Модуль конфигурации.
Экспортирует настройки приложения.
"""

from src.config.loader import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
