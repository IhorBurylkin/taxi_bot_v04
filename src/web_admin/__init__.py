# src/web/__init__.py
"""
Web интерфейс на NiceGUI (FastAPI).
"""

from src.web_admin.app import create_app

__all__ = ["create_app"]
