# src/bot/handlers/passenger.py
"""
Хендлеры пассажира.
Создание заказа, отслеживание поездки.
"""

from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Location
from aiogram.fsm.context import FSMContext

from src.common.localization import get_text
from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg, PaymentMethod
from src.bot.keyboards import (
    get_confirm_order_keyboard,
    get_cancel_keyboard,
    get_location_keyboard,
)
from src.bot.states import OrderStates
from src.bot.dependencies import get_user_service, get_order_service, get_geo_service

router = Router(name="passenger")


@router.callback_query(F.data == "new_order")
async def start_new_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало создания нового заказа."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(user_id)
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Проверяем, нет ли активного заказа
        active_order = await order_service.get_active_order_for_passenger(user_id)
        if active_order is not None:
            await callback.answer("У вас уже есть активный заказ")
            return
        
        # Запрашиваем точку подачи
        await state.set_state(OrderStates.pickup_location)
        
        await callback.message.edit_text(
            get_text("ENTER_PICKUP_LOCATION", user.language),
            reply_markup=get_location_keyboard(user.language),
        )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в start_new_order: {e}", exc_info=True)
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.message(OrderStates.pickup_location, F.location)
async def receive_pickup_location(message: Message, state: FSMContext) -> None:
    """Получение геолокации точки подачи."""
    try:
        user_id = message.from_user.id
        location = message.location
        
        user_service = get_user_service()
        geo_service = get_geo_service()
        
        user = await user_service.get_user(user_id)
        if user is None:
            await message.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Получаем адрес по координатам
        address = await geo_service.reverse_geocode(
            location.latitude,
            location.longitude,
        )
        
        if address is None:
            address = f"{location.latitude:.6f}, {location.longitude:.6f}"
        
        # Сохраняем в состояние
        await state.update_data(
            pickup_lat=location.latitude,
            pickup_lng=location.longitude,
            pickup_address=address,
        )
        
        # Переходим к пункту назначения
        await state.set_state(OrderStates.destination_location)
        
        await message.answer(
            f"📍 Точка подачи: {address}\n\n{get_text('ENTER_DESTINATION', user.language)}",
            reply_markup=get_location_keyboard(user.language),
        )
    except Exception as e:
        await log_error(f"Ошибка в receive_pickup_location: {e}", exc_info=True)
        await message.answer(get_text("ERROR_GENERIC", "ru"))


@router.message(OrderStates.pickup_location, F.text)
async def receive_pickup_address(message: Message, state: FSMContext) -> None:
    """Получение текстового адреса точки подачи."""
    try:
        user_id = message.from_user.id
        address = message.text.strip()
        
        user_service = get_user_service()
        geo_service = get_geo_service()
        
        user = await user_service.get_user(user_id)
        if user is None:
            await message.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Геокодируем адрес
        location = await geo_service.geocode(address)
        
        if location is None:
            await message.answer(get_text("ERROR_INVALID_LOCATION", user.language))
            return
        
        # Сохраняем в состояние
        await state.update_data(
            pickup_lat=location.latitude,
            pickup_lng=location.longitude,
            pickup_address=location.address,
        )
        
        # Переходим к пункту назначения
        await state.set_state(OrderStates.destination_location)
        
        await message.answer(
            f"📍 Точка подачи: {location.address}\n\n{get_text('ENTER_DESTINATION', user.language)}",
            reply_markup=get_location_keyboard(user.language),
        )
    except Exception as e:
        await log_error(f"Ошибка в receive_pickup_address: {e}", exc_info=True)
        await message.answer(get_text("ERROR_GENERIC", "ru"))


@router.message(OrderStates.destination_location, F.location)
async def receive_destination_location(message: Message, state: FSMContext) -> None:
    """Получение геолокации пункта назначения."""
    try:
        user_id = message.from_user.id
        location = message.location
        
        user_service = get_user_service()
        geo_service = get_geo_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(user_id)
        if user is None:
            await message.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Получаем адрес по координатам
        address = await geo_service.reverse_geocode(
            location.latitude,
            location.longitude,
        )
        
        if address is None:
            address = f"{location.latitude:.6f}, {location.longitude:.6f}"
        
        # Сохраняем в состояние
        data = await state.get_data()
        await state.update_data(
            dest_lat=location.latitude,
            dest_lng=location.longitude,
            dest_address=address,
        )
        
        # Рассчитываем маршрут
        route = await geo_service.calculate_route(
            data["pickup_lat"],
            data["pickup_lng"],
            location.latitude,
            location.longitude,
        )
        
        if route is None:
            await message.answer(get_text("ERROR_GENERIC", user.language))
            return
        
        # Рассчитываем стоимость
        fare = order_service.calculate_fare(route.distance_km, route.duration_minutes)
        
        await state.update_data(
            distance_km=route.distance_km,
            duration_min=route.duration_minutes,
            fare=fare.total_fare,
            currency=fare.currency,
        )
        
        # Показываем подтверждение
        await state.set_state(OrderStates.confirm)
        
        fare_text = get_text(
            "FARE_DETAILS",
            user.language,
            distance=route.distance_km,
            duration=route.duration_minutes,
            fare=fare.total_fare,
            currency=fare.currency,
        )
        
        await message.answer(
            f"🎯 Пункт назначения: {address}\n\n{fare_text}",
            reply_markup=get_confirm_order_keyboard(user.language),
        )
    except Exception as e:
        await log_error(f"Ошибка в receive_destination_location: {e}", exc_info=True)
        await message.answer(get_text("ERROR_GENERIC", "ru"))


@router.message(OrderStates.destination_location, F.text)
async def receive_destination_address(message: Message, state: FSMContext) -> None:
    """Получение текстового адреса пункта назначения."""
    try:
        user_id = message.from_user.id
        address = message.text.strip()
        
        user_service = get_user_service()
        geo_service = get_geo_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(user_id)
        if user is None:
            await message.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Геокодируем адрес
        location = await geo_service.geocode(address)
        
        if location is None:
            await message.answer(get_text("ERROR_INVALID_LOCATION", user.language))
            return
        
        # Сохраняем в состояние
        data = await state.get_data()
        await state.update_data(
            dest_lat=location.latitude,
            dest_lng=location.longitude,
            dest_address=location.address,
        )
        
        # Рассчитываем маршрут
        route = await geo_service.calculate_route(
            data["pickup_lat"],
            data["pickup_lng"],
            location.latitude,
            location.longitude,
        )
        
        if route is None:
            await message.answer(get_text("ERROR_GENERIC", user.language))
            return
        
        # Рассчитываем стоимость
        fare = order_service.calculate_fare(route.distance_km, route.duration_minutes)
        
        await state.update_data(
            distance_km=route.distance_km,
            duration_min=route.duration_minutes,
            fare=fare.total_fare,
            currency=fare.currency,
        )
        
        # Показываем подтверждение
        await state.set_state(OrderStates.confirm)
        
        fare_text = get_text(
            "FARE_DETAILS",
            user.language,
            distance=route.distance_km,
            duration=route.duration_minutes,
            fare=fare.total_fare,
            currency=fare.currency,
        )
        
        await message.answer(
            f"🎯 Пункт назначения: {location.address}\n\n{fare_text}",
            reply_markup=get_confirm_order_keyboard(user.language),
        )
    except Exception as e:
        await log_error(f"Ошибка в receive_destination_address: {e}", exc_info=True)
        await message.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(OrderStates.confirm, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение заказа."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(user_id)
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        
        from src.core.orders.models import OrderCreateDTO
        
        dto = OrderCreateDTO(
            passenger_id=user_id,
            pickup_address=data["pickup_address"],
            pickup_latitude=data["pickup_lat"],
            pickup_longitude=data["pickup_lng"],
            destination_address=data["dest_address"],
            destination_latitude=data["dest_lat"],
            destination_longitude=data["dest_lng"],
            payment_method=PaymentMethod.CASH,
        )
        
        # Создаём заказ
        order = await order_service.create_order(
            dto,
            data["distance_km"],
            data["duration_min"],
        )
        
        if order is None:
            await callback.answer(get_text("ERROR_GENERIC", user.language))
            return
        
        # Сбрасываем состояние
        await state.clear()
        
        await callback.message.edit_text(
            f"{get_text('ORDER_CREATED', user.language)}\n\n{get_text('SEARCHING_DRIVER', user.language)}",
            reply_markup=get_cancel_keyboard(user.language),
        )
        
        # Запускаем поиск водителя
        await order_service.start_search(order.id)
        
        await callback.answer()
        
        await log_info(
            f"Заказ {order.id} создан пассажиром {user_id}",
            type_msg=TypeMsg.INFO,
        )
    except Exception as e:
        await log_error(f"Ошибка в confirm_order: {e}", exc_info=True)
        await callback.answer(get_text("ERROR_GENERIC", "ru"))


@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена заказа."""
    try:
        user_id = callback.from_user.id
        
        user_service = get_user_service()
        order_service = get_order_service()
        
        user = await user_service.get_user(user_id)
        if user is None:
            await callback.answer(get_text("ERROR_NOT_REGISTERED", "ru"))
            return
        
        # Получаем активный заказ
        order = await order_service.get_active_order_for_passenger(user_id)
        
        if order is not None:
            await order_service.cancel_order(order.id, "passenger")
        
        # Сбрасываем состояние
        await state.clear()
        
        await callback.message.edit_text(
            get_text("ORDER_CANCELLED", user.language),
        )
        
        await callback.answer()
    except Exception as e:
        await log_error(f"Ошибка в cancel_order: {e}", exc_info=True)
        await callback.answer(get_text("ERROR_GENERIC", "ru"))
