# src/bot/handlers/common.py
"""
Общие хендлеры.
Команда /start, настройки, выбор языка.
"""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.common.localization import get_text
from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg, UserRole
from src.bot.keyboards import (
    get_start_keyboard,
    get_language_keyboard,
    get_main_menu_keyboard,
)
from src.bot.states import RegistrationStates
from src.bot.dependencies import get_user_service

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start."""
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        await log_info(
            f"Команда /start от пользователя {user_id} ({username})",
            type_msg=TypeMsg.DEBUG,
        )
        
        # Получаем или создаём пользователя
        user_service = get_user_service()
        
        from src.core.users.models import UserCreateDTO
        dto = UserCreateDTO(
            id=user_id,
            username=username,
            first_name=first_name or "User",
            last_name=last_name,
        )
        
        user = await user_service.register_user(dto)
        
        if user is None:
            await message.answer(get_text("ERROR_GENERIC", "ru"))
            return
        
        # Сбрасываем состояние
        await state.clear()
        
        # Приветствие
        await message.answer(
            get_text("WELCOME", user.language),
            reply_markup=get_start_keyboard(user.language),
        )
    except Exception as e:
        await log_error(f"Ошибка в cmd_start: {e}", exc_info=True)
        await message.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "role_passenger")
async def select_passenger_role(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор роли пассажира."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        user = await user_service.get_user(user_id)
        
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Устанавливаем роль
        await user_service.set_user_role(user_id, UserRole.PASSENGER)
        
        await callback.message.edit_text(
            get_text("ENTER_PICKUP_LOCATION", user.language),
            reply_markup=get_main_menu_keyboard(user.language, UserRole.PASSENGER),
        )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в select_passenger_role: {e}", exc_info=True)
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "role_driver")
async def select_driver_role(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор роли водителя."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        user = await user_service.get_user(user_id)
        
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Проверяем, есть ли профиль водителя
        driver_profile = await user_service.get_driver_profile(user_id)
        
        if driver_profile is None:
            # Начинаем регистрацию водителя
            await state.set_state(RegistrationStates.car_brand)
            await callback.message.edit_text(
                "🚗 Введите марку вашего автомобиля:",
            )
        else:
            # Профиль уже есть — показываем меню водителя
            await callback.message.edit_text(
                f"👋 Добро пожаловать, водитель!\n\n🚗 {driver_profile.car_info}",
                reply_markup=get_main_menu_keyboard(user.language, UserRole.DRIVER),
            )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в select_driver_role: {e}", exc_info=True)
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery) -> None:
    """Показывает настройки."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        user = await user_service.get_user(user_id)
        
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        await callback.message.edit_text(
            get_text("SETTINGS", user.language),
            reply_markup=get_language_keyboard(user.language),
        )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в show_settings: {e}")
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data.startswith("lang_"))
async def change_language(callback: CallbackQuery) -> None:
    """Смена языка."""
    try:
        user_id = callback.from_user.id
        new_lang = callback.data.split("_")[1]  # lang_ru -> ru
        
        user_service = get_user_service()
        user = await user_service.get_user(user_id)
        
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Обновляем язык
        user.language = new_lang
        await user_service.update_user(user)
        
        await callback.message.edit_text(
            get_text("PROFILE_UPDATED", new_lang),
            reply_markup=get_main_menu_keyboard(new_lang, user.role),
        )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в change_language: {e}")
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка Назад."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        user = await user_service.get_user(user_id)
        
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Сбрасываем состояние
        await state.clear()
        
        await callback.message.edit_text(
            get_text("WELCOME", user.language),
            reply_markup=get_main_menu_keyboard(user.language, user.role),
        )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в go_back: {e}")
        await callback.answer(get_text("ERROR_GENERIC", "ru"))
