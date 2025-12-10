# src/bot/states.py
"""
FSM состояния для Telegram бота.
"""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния регистрации водителя."""
    car_brand = State()
    car_model = State()
    car_color = State()
    car_plate = State()


class OrderStates(StatesGroup):
    """Состояния создания заказа."""
    pickup_location = State()
    destination_location = State()
    confirm = State()


class DriverStates(StatesGroup):
    """Состояния водителя."""
    online = State()
    on_order = State()
