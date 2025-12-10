# src/common/__init__.py
"""
Общие утилиты, константы и логгер.
"""

from src.common.logger import get_logger, log_info, log_error, log_warning, log_debug
from src.common.constants import TypeMsg
from src.common.localization import get_text, load_lang_dict

__all__ = [
    "get_logger",
    "log_info",
    "log_error",
    "log_warning",
    "log_debug",
    "TypeMsg",
    "get_text",
    "load_lang_dict",
]
