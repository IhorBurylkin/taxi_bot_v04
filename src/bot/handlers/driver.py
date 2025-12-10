# src/bot/handlers/driver.py
"""
Хендлеры водителя.
Регистрация, выход на линию, принятие заказов.
"""

from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Location
from aiogram.fsm.context import FSMContext

from src.common.localization import get_text
from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg, UserRole
from src.bot.keyboards import get_main_menu_keyboard, get_driver_order_keyboard
from src.bot.states import RegistrationStates, DriverStates
from src.bot.dependencies import get_user_service, get_order_service

router = Router(name="driver")


# =============================================================================
# РЕГИСТРАЦИЯ ВОДИТЕЛЯ
# =============================================================================

@router.message(RegistrationStates.car_brand, F.text)
async def receive_car_brand(message: Message, state: FSMContext) -> None:
    """Получение марки автомобиля."""
    try:
        await state.update_data(car_brand=message.text.strip())
        await state.set_state(RegistrationStates.car_model)
        
        await message.answer("📝 Введите модель автомобиля:")
    except Exception as e:
        await log_error(f"Ошибка в receive_car_brand: {e}")
        await message.answer(get_text("ERROR_GENERIC", "ru"))


@router.message(RegistrationStates.car_model, F.text)
async def receive_car_model(message: Message, state: FSMContext) -> None:
    """Получение модели автомобиля."""
    try:
        await state.update_data(car_model=message.text.strip())
        await state.set_state(RegistrationStates.car_color)
        
        await message.answer("🎨 Введите цвет автомобиля:")
    except Exception as e:
        await log_error(f"Ошибка в receive_car_model: {e}")
        await message.answer(get_text("ERROR_GENERIC", "ru"))


@router.message(RegistrationStates.car_color, F.text)
async def receive_car_color(message: Message, state: FSMContext) -> None:
    """Получение цвета автомобиля."""
    try:
        await state.update_data(car_color=message.text.strip())
        await state.set_state(RegistrationStates.car_plate)
        
        await message.answer("🔢 Введите номер автомобиля:")
    except Exception as e:
        await log_error(f"Ошибка в receive_car_color: {e}")
        await message.answer(get_text("ERROR_GENERIC", "ru"))


@router.message(RegistrationStates.car_plate, F.text)
async def receive_car_plate(message: Message, state: FSMContext) -> None:
    """Получение номера автомобиля и завершение регистрации."""
    try:
        user_id = message.from_user.id
        car_plate = message.text.strip().upper()
        
        data = await state.get_data()
        
        user_service = get_user_service()
        user = await user_service.get_user(user_id)
        
        if user is None:
            await message.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Регистрируем водителя
        from src.core.users.models import DriverProfileCreateDTO
        
        dto = DriverProfileCreateDTO(
            user_id=user_id,
            car_brand=data["car_brand"],
            car_model=data["car_model"],
            car_color=data["car_color"],
            car_plate=car_plate,
        )
        
        profile = await user_service.register_driver(dto)
        
        if profile is None:
            await message.answer(get_text("ERROR_GENERIC", user.language))
            return
        
        # Сбрасываем состояние
        await state.clear()
        
        await message.answer(
            f"✅ Регистрация завершена!\n\n🚗 {profile.car_info}\n\n"
            f"⚠️ Ваш профиль ожидает верификации администратором.",
            reply_markup=get_main_menu_keyboard(user.language, UserRole.DRIVER),
        )
        
        await log_info(
            f"Водитель {user_id} зарегистрирован: {profile.car_info}",
            type_msg=TypeMsg.INFO,
        )
    except Exception as e:
        await log_error(f"Ошибка в receive_car_plate: {e}", exc_info=True)
        await message.answer(get_text("ERROR_GENERIC", "ru"))


# =============================================================================
# УПРАВЛЕНИЕ СТАТУСОМ
# =============================================================================

@router.callback_query(F.data == "go_online")
async def go_online(callback: CallbackQuery, state: FSMContext) -> None:
    """Выход на линию."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        user = await user_service.get_user(user_id)
        
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        profile = await user_service.get_driver_profile(user_id)
        
        if profile is None:
            await callback.answer("Профиль водителя не найден")
            return
        
        if not profile.is_verified:
            await callback.answer("Ваш профиль ещё не верифицирован")
            return
        
        # Выходим на линию
        success = await user_service.set_driver_online(user_id)
        
        if success:
            await state.set_state(DriverStates.online)
            
            await callback.message.edit_text(
                f"🟢 Вы на линии!\n\n🚗 {profile.car_info}\n\n"
                f"📍 Отправьте геолокацию для обновления позиции",
                reply_markup=get_main_menu_keyboard(user.language, UserRole.DRIVER, is_online=True),
            )
            
            await log_info(f"Водитель {user_id} вышел на линию", type_msg=TypeMsg.INFO)
        else:
            await callback.answer("Не удалось выйти на линию")
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в go_online: {e}", exc_info=True)
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "go_offline")
async def go_offline(callback: CallbackQuery, state: FSMContext) -> None:
    """Уход с линии."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        user = await user_service.get_user(user_id)
        
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        profile = await user_service.get_driver_profile(user_id)
        
        if profile is None:
            await callback.answer("Профиль водителя не найден")
            return
        
        # Уходим с линии
        success = await user_service.set_driver_offline(user_id)
        
        if success:
            await state.clear()
            
            await callback.message.edit_text(
                f"🔴 Вы ушли с линии\n\n🚗 {profile.car_info}",
                reply_markup=get_main_menu_keyboard(user.language, UserRole.DRIVER, is_online=False),
            )
            
            await log_info(f"Водитель {user_id} ушёл с линии", type_msg=TypeMsg.INFO)
        else:
            await callback.answer("Не удалось уйти с линии")
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в go_offline: {e}", exc_info=True)
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


# =============================================================================
# ОБНОВЛЕНИЕ ЛОКАЦИИ
# =============================================================================

@router.message(DriverStates.online, F.location)
async def update_driver_location(message: Message, state: FSMContext) -> None:
    """Обновление геолокации водителя."""
    try:
        user_id = message.from_user.id
        location = message.location
        
        user_service = get_user_service()
        
        from src.core.users.models import DriverLocationDTO
        
        dto = DriverLocationDTO(
            driver_id=user_id,
            latitude=location.latitude,
            longitude=location.longitude,
        )
        
        await user_service.update_driver_location(dto)
        
        await message.answer(
            f"📍 Локация обновлена\n"
            f"Широта: {location.latitude:.6f}\n"
            f"Долгота: {location.longitude:.6f}"
        )
    except Exception as e:
        await log_error(f"Ошибка в update_driver_location: {e}")


# =============================================================================
# ПРИНЯТИЕ/ОТКЛОНЕНИЕ ЗАКАЗОВ
# =============================================================================

@router.callback_query(F.data.startswith("accept_order_"))
async def accept_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Принятие заказа водителем."""
    try:
        user_id = callback.from_user.id
        order_id = callback.data.split("_")[-1]  # accept_order_{order_id}
        
        user_service = get_user_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(user_id)
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Пытаемся принять заказ
        success = await order_service.accept_order(order_id, user_id)
        
        if success:
            order = await order_service.get_order(order_id)
            
            await state.set_state(DriverStates.on_order)
            await state.update_data(order_id=order_id)
            
            await callback.message.edit_text(
                f"✅ Заказ принят!\n\n"
                f"📍 Адрес подачи: {order.pickup_address}\n"
                f"🎯 Адрес назначения: {order.destination_address}\n"
                f"💰 Стоимость: {order.estimated_fare}",
                reply_markup=get_driver_order_keyboard(user.language, "accepted"),
            )
            
            await log_info(f"Водитель {user_id} принял заказ {order_id}", type_msg=TypeMsg.INFO)
        else:
            await callback.answer("Заказ уже занят или недоступен")
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в accept_order: {e}", exc_info=True)
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data.startswith("decline_order_"))
async def decline_order(callback: CallbackQuery) -> None:
    """Отклонение заказа водителем."""
    try:
        user_id = callback.from_user.id
        order_id = callback.data.split("_")[-1]
        
        from src.bot.dependencies import get_matching_service
        matching_service = get_matching_service()
        
        # Помечаем, что водитель отказался
        await matching_service.mark_driver_rejected(order_id, user_id)
        
        await callback.message.delete()
        await callback.answer("Заказ отклонён")
        
        await log_info(f"Водитель {user_id} отклонил заказ {order_id}", type_msg=TypeMsg.DEBUG)
    except Exception as e:
        await log_error(f"Ошибка в decline_order: {e}")
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "driver_arrived")
async def driver_arrived(callback: CallbackQuery, state: FSMContext) -> None:
    """Водитель прибыл на место подачи."""
    try:
        data = await state.get_data()
        order_id = data.get("order_id")
        
        if not order_id:
            await callback.answer("Заказ не найден")
            return
        
        user_service = get_user_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(callback.from_user.id)
        
        success = await order_service.driver_arrived(order_id)
        
        if success:
            await callback.message.edit_text(
                "🚗 Вы прибыли на место\n\nОжидаем пассажира...",
                reply_markup=get_driver_order_keyboard(user.language, "arrived"),
            )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в driver_arrived: {e}")
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "start_ride")
async def start_ride(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало поездки."""
    try:
        data = await state.get_data()
        order_id = data.get("order_id")
        
        if not order_id:
            await callback.answer("Заказ не найден")
            return
        
        user_service = get_user_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(callback.from_user.id)
        
        success = await order_service.start_ride(order_id)
        
        if success:
            await callback.message.edit_text(
                "🚀 Поездка началась\n\nСчастливого пути!",
                reply_markup=get_driver_order_keyboard(user.language, "in_progress"),
            )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в start_ride: {e}")
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "complete_ride")
async def complete_ride(callback: CallbackQuery, state: FSMContext) -> None:
    """Завершение поездки."""
    try:
        data = await state.get_data()
        order_id = data.get("order_id")
        
        if not order_id:
            await callback.answer("Заказ не найден")
            return
        
        user_id = callback.from_user.id
        user_service = get_user_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(user_id)
        order = await order_service.get_order(order_id)
        
        success = await order_service.complete_order(order_id)
        
        if success:
            await state.set_state(DriverStates.online)
            await state.update_data(order_id=None)
            
            await callback.message.edit_text(
                f"✅ Поездка завершена!\n\n"
                f"💰 Стоимость: {order.fare}",
                reply_markup=get_main_menu_keyboard(user.language, UserRole.DRIVER, is_online=True),
            )
            
            await log_info(f"Водитель {user_id} завершил заказ {order_id}", type_msg=TypeMsg.INFO)
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в complete_ride: {e}")
        await callback.answer(get_text("ERROR_GENERIC", "ru"))
