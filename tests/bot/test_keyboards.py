# tests/bot/test_keyboards.py
"""
Тесты для клавиатур Telegram бота.
"""

from __future__ import annotations

import pytest
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.bot.keyboards import (
    get_start_keyboard,
    get_main_menu_keyboard,
    get_language_keyboard,
    get_location_keyboard,
)
from src.common.constants import UserRole


class TestKeyboards:
    """Тесты для генерации клавиатур."""
    
    def test_get_start_keyboard(self) -> None:
        """Проверяет генерацию стартовой клавиатуры."""
        # Act
        keyboard = get_start_keyboard()
        
        # Assert
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert keyboard.inline_keyboard is not None
        assert len(keyboard.inline_keyboard) > 0
        
        # Проверяем первый ряд с кнопками ролей
        first_row = keyboard.inline_keyboard[0]
        assert len(first_row) == 2
        assert "пассажир" in first_row[0].text.lower()
        assert "role_passenger" == first_row[0].callback_data
        assert "водитель" in first_row[1].text.lower()
        assert "role_driver" == first_row[1].callback_data
    
    def test_get_start_keyboard_with_lang(self) -> None:
        """Проверяет стартовую клавиатуру с указанием языка."""
        # Act
        keyboard = get_start_keyboard(lang="en")
        
        # Assert
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) > 0
    
    def test_get_main_menu_keyboard_passenger(self) -> None:
        """Проверяет главное меню для пассажира."""
        # Act
        keyboard = get_main_menu_keyboard(role=UserRole.PASSENGER)
        
        # Assert
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert keyboard.inline_keyboard is not None
        
        # Проверяем наличие кнопки "Новый заказ"
        buttons_text = [
            btn.text
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert any("заказ" in text.lower() for text in buttons_text)
        assert any("поездки" in text.lower() for text in buttons_text)
    
    def test_get_main_menu_keyboard_driver_offline(self) -> None:
        """Проверяет главное меню для водителя в оффлайне."""
        # Act
        keyboard = get_main_menu_keyboard(
            role=UserRole.DRIVER,
            is_online=False,
        )
        
        # Assert
        assert isinstance(keyboard, InlineKeyboardMarkup)
        
        # Проверяем наличие кнопки "Выйти на линию"
        buttons_text = [
            btn.text
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert any("выйти на линию" in text.lower() for text in buttons_text)
        assert any("баланс" in text.lower() for text in buttons_text)
        assert any("статистика" in text.lower() for text in buttons_text)
    
    def test_get_main_menu_keyboard_driver_online(self) -> None:
        """Проверяет главное меню для водителя в онлайне."""
        # Act
        keyboard = get_main_menu_keyboard(
            role=UserRole.DRIVER,
            is_online=True,
        )
        
        # Assert
        assert isinstance(keyboard, InlineKeyboardMarkup)
        
        # Проверяем наличие кнопки "Уйти с линии"
        buttons_text = [
            btn.text
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert any("уйти с линии" in text.lower() for text in buttons_text)
    
    def test_get_language_keyboard_default(self) -> None:
        """Проверяет клавиатуру выбора языка по умолчанию."""
        # Act
        keyboard = get_language_keyboard()
        
        # Assert
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert keyboard.inline_keyboard is not None
        
        # Проверяем наличие языковых кнопок
        buttons = [
            btn
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        
        callback_data = [btn.callback_data for btn in buttons if btn.callback_data]
        assert "lang_ru" in callback_data
        assert "lang_uk" in callback_data
        assert "lang_en" in callback_data
        assert "lang_de" in callback_data
        
        # Проверяем отметку текущего языка (ru)
        ru_button = next(btn for btn in buttons if btn.callback_data == "lang_ru")
        assert "✅" in ru_button.text
    
    def test_get_language_keyboard_current_lang(self) -> None:
        """Проверяет отметку текущего языка."""
        # Act
        keyboard = get_language_keyboard(current_lang="en")
        
        # Assert
        buttons = [
            btn
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        
        # Проверяем отметку текущего языка (en)
        en_button = next(btn for btn in buttons if btn.callback_data == "lang_en")
        assert "✅" in en_button.text
        
        # Проверяем, что другие языки не отмечены
        ru_button = next(btn for btn in buttons if btn.callback_data == "lang_ru")
        assert "✅" not in ru_button.text
    
    def test_get_language_keyboard_has_back_button(self) -> None:
        """Проверяет наличие кнопки "Назад"."""
        # Act
        keyboard = get_language_keyboard()
        
        # Assert
        buttons = [
            btn
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        
        back_button = next(
            (btn for btn in buttons if btn.callback_data == "back"),
            None,
        )
        assert back_button is not None
        assert "назад" in back_button.text.lower()
    
    def test_get_location_keyboard(self) -> None:
        """Проверяет клавиатуру с геолокацией."""
        # Act
        keyboard = get_location_keyboard()
        
        # Assert
        assert isinstance(keyboard, ReplyKeyboardMarkup)
        assert keyboard.keyboard is not None
        assert len(keyboard.keyboard) > 0
        
        # Проверяем первую кнопку (геолокация)
        first_button = keyboard.keyboard[0][0]
        assert first_button.request_location is True
        assert "геолокац" in first_button.text.lower()
    
    def test_get_location_keyboard_has_cancel(self) -> None:
        """Проверяет наличие кнопки отмены."""
        # Act
        keyboard = get_location_keyboard()
        
        # Assert
        buttons_text = [
            btn.text
            for row in keyboard.keyboard
            for btn in row
        ]
        assert any("отмена" in text.lower() for text in buttons_text)
    
    def test_get_location_keyboard_with_lang(self) -> None:
        """Проверяет клавиатуру геолокации с указанием языка."""
        # Act
        keyboard = get_location_keyboard(lang="en")
        
        # Assert
        assert isinstance(keyboard, ReplyKeyboardMarkup)
        assert len(keyboard.keyboard) > 0
    
    def test_keyboard_types(self) -> None:
        """Проверяет правильные типы клавиатур."""
        # Act & Assert
        assert isinstance(get_start_keyboard(), InlineKeyboardMarkup)
        assert isinstance(get_main_menu_keyboard(), InlineKeyboardMarkup)
        assert isinstance(get_language_keyboard(), InlineKeyboardMarkup)
        assert isinstance(get_location_keyboard(), ReplyKeyboardMarkup)
    
    def test_main_menu_keyboard_has_settings(self) -> None:
        """Проверяет наличие кнопки настроек в главном меню."""
        # Act
        keyboard_passenger = get_main_menu_keyboard(role=UserRole.PASSENGER)
        keyboard_driver = get_main_menu_keyboard(role=UserRole.DRIVER)
        
        # Assert
        for keyboard in [keyboard_passenger, keyboard_driver]:
            buttons = [
                btn
                for row in keyboard.inline_keyboard
                for btn in row
            ]
            settings_button = next(
                (btn for btn in buttons if btn.callback_data == "settings"),
                None,
            )
            assert settings_button is not None
