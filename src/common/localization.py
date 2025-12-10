# src/common/localization.py
"""
Модуль локализации.
Загружает и предоставляет доступ к переводам из lang_dict.json.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def get_lang_dict_path() -> Path:
    """Возвращает путь к файлу локализации."""
    return Path(__file__).parent.parent.parent / "config" / "lang_dict.json"


@lru_cache()
def load_lang_dict() -> dict[str, dict[str, str]]:
    """
    Загружает словарь локализации из JSON файла.
    Кэширует результат для производительности.
    
    Returns:
        Словарь с переводами
    """
    lang_path = get_lang_dict_path()
    if not lang_path.exists():
        raise FileNotFoundError(f"Файл локализации не найден: {lang_path}")
    
    with open(lang_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_text(
    key: str,
    lang: str = "ru",
    default: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Получает локализованный текст по ключу.
    
    Args:
        key: Ключ перевода
        lang: Код языка (ru, uk, en, de)
        default: Значение по умолчанию, если ключ не найден
        **kwargs: Параметры для форматирования строки
        
    Returns:
        Локализованный текст
        
    Example:
        >>> get_text("WELCOME", "ru")
        "Добро пожаловать в Taxi Bot!"
        
        >>> get_text("NEW_ORDER_NOTIFICATION", "ru", pickup="ул. Крещатик", destination="Аэропорт", fare=150, currency="UAH")
        "🆕 Новый заказ!\n📍 Откуда: ул. Крещатик\n🎯 Куда: Аэропорт\n💰 Стоимость: 150 UAH"
    """
    try:
        lang_dict = load_lang_dict()
    except FileNotFoundError:
        if default:
            return default
        return f"[{key}]"
    
    # Получаем перевод по ключу
    translations = lang_dict.get(key)
    
    if not translations:
        if default:
            return default
        return f"[{key}]"
    
    # Получаем текст на нужном языке
    text = translations.get(lang)
    
    if not text:
        # Пробуем русский как fallback
        text = translations.get("ru")
        
    if not text:
        # Берём первый доступный перевод
        text = next(iter(translations.values()), f"[{key}]")
    
    # Форматируем строку, если переданы параметры
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass  # Игнорируем отсутствующие ключи форматирования
    
    return text


def get_available_languages() -> list[str]:
    """
    Возвращает список доступных языков.
    
    Returns:
        Список кодов языков
    """
    try:
        lang_dict = load_lang_dict()
        # Берём языки из первого ключа
        first_key = next(iter(lang_dict.values()), {})
        return list(first_key.keys())
    except Exception:
        return ["ru", "uk", "en", "de"]


def validate_lang_dict() -> list[str]:
    """
    Проверяет целостность словаря локализации.
    
    Returns:
        Список ошибок (пустой, если всё в порядке)
    """
    errors = []
    
    try:
        lang_dict = load_lang_dict()
    except FileNotFoundError as e:
        return [str(e)]
    
    available_langs = get_available_languages()
    
    for key, translations in lang_dict.items():
        if not isinstance(translations, dict):
            errors.append(f"Ключ '{key}' имеет неверный формат")
            continue
        
        missing_langs = set(available_langs) - set(translations.keys())
        if missing_langs:
            errors.append(f"Ключ '{key}' не имеет перевода для языков: {missing_langs}")
    
    return errors
