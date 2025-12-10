# src/bot/keyboards.py
"""
Клавиатуры для Telegram бота.
Inline и Reply клавиатуры.
"""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from src.common.localization import get_text
from src.common.constants import UserRole


def get_start_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Стартовая клавиатура с выбором роли."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🚕 Я пассажир",
            callback_data="role_passenger",
        ),
        InlineKeyboardButton(
            text="🚗 Я водитель",
            callback_data="role_driver",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="settings",
        ),
    )
    
    return builder.as_markup()


def get_main_menu_keyboard(
    lang: str = "ru",
    role: UserRole = UserRole.PASSENGER,
    is_online: bool = False,
) -> InlineKeyboardMarkup:
    """Главное меню в зависимости от роли."""
    builder = InlineKeyboardBuilder()
    
    if role == UserRole.PASSENGER:
        builder.row(
            InlineKeyboardButton(
                text="🚕 Новый заказ",
                callback_data="new_order",
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text="📋 Мои поездки",
                callback_data="my_trips",
            ),
        )
    elif role == UserRole.DRIVER:
        if is_online:
            builder.row(
                InlineKeyboardButton(
                    text="🔴 Уйти с линии",
                    callback_data="go_offline",
                ),
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="🟢 Выйти на линию",
                    callback_data="go_online",
                ),
            )
        builder.row(
            InlineKeyboardButton(
                text="💰 Мой баланс",
                callback_data="my_balance",
            ),
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data="my_stats",
            ),
        )
    
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="settings",
        ),
    )
    
    return builder.as_markup()


def get_language_keyboard(current_lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура выбора языка."""
    builder = InlineKeyboardBuilder()
    
    languages = [
        ("🇷🇺 Русский", "ru"),
        ("🇺🇦 Українська", "uk"),
        ("🇬🇧 English", "en"),
        ("🇩🇪 Deutsch", "de"),
    ]
    
    for name, code in languages:
        # Добавляем галочку к текущему языку
        text = f"✅ {name}" if code == current_lang else name
        builder.button(
            text=text,
            callback_data=f"lang_{code}",
        )
    
    builder.adjust(2)  # По 2 кнопки в ряду
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back",
        ),
    )
    
    return builder.as_markup()


def get_location_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отправки геолокации."""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(
            text="📍 Отправить геолокацию",
            request_location=True,
        ),
    )
    
    builder.row(
        KeyboardButton(text="❌ Отмена"),
    )
    
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_confirm_order_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения заказа."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить заказ",
            callback_data="confirm_order",
        ),
    )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_order",
        ),
    )
    
    return builder.as_markup()


def get_cancel_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить заказ",
            callback_data="cancel_order",
        ),
    )
    
    return builder.as_markup()


def get_new_order_keyboard(
    lang: str = "ru",
    order_id: str = "",
) -> InlineKeyboardMarkup:
    """Клавиатура нового заказа для водителя."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Принять",
            callback_data=f"accept_order_{order_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"decline_order_{order_id}",
        ),
    )
    
    return builder.as_markup()


def get_driver_order_keyboard(
    lang: str = "ru",
    status: str = "accepted",
) -> InlineKeyboardMarkup:
    """Клавиатура управления заказом для водителя."""
    builder = InlineKeyboardBuilder()
    
    if status == "accepted":
        builder.row(
            InlineKeyboardButton(
                text="📍 Я на месте",
                callback_data="driver_arrived",
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="cancel_order",
            ),
        )
    elif status == "arrived":
        builder.row(
            InlineKeyboardButton(
                text="🚀 Начать поездку",
                callback_data="start_ride",
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="cancel_order",
            ),
        )
    elif status == "in_progress":
        builder.row(
            InlineKeyboardButton(
                text="✅ Завершить поездку",
                callback_data="complete_ride",
            ),
        )
    
    return builder.as_markup()


def get_remove_keyboard() -> ReplyKeyboardRemove:
    """Удаление Reply клавиатуры."""
    return ReplyKeyboardRemove()
