# tests/bot/test_states.py
"""
Тесты для FSM состояний Telegram бота.
"""

from __future__ import annotations

import pytest
from aiogram.fsm.state import State, StatesGroup

from src.bot.states import RegistrationStates, OrderStates, DriverStates


class TestRegistrationStates:
    """Тесты для состояний регистрации водителя."""
    
    def test_registration_states_is_states_group(self) -> None:
        """Проверяет, что RegistrationStates является StatesGroup."""
        assert issubclass(RegistrationStates, StatesGroup)
    
    def test_registration_states_has_car_brand(self) -> None:
        """Проверяет наличие состояния car_brand."""
        assert hasattr(RegistrationStates, "car_brand")
        assert isinstance(RegistrationStates.car_brand, State)
    
    def test_registration_states_has_car_model(self) -> None:
        """Проверяет наличие состояния car_model."""
        assert hasattr(RegistrationStates, "car_model")
        assert isinstance(RegistrationStates.car_model, State)
    
    def test_registration_states_has_car_color(self) -> None:
        """Проверяет наличие состояния car_color."""
        assert hasattr(RegistrationStates, "car_color")
        assert isinstance(RegistrationStates.car_color, State)
    
    def test_registration_states_has_car_plate(self) -> None:
        """Проверяет наличие состояния car_plate."""
        assert hasattr(RegistrationStates, "car_plate")
        assert isinstance(RegistrationStates.car_plate, State)
    
    def test_registration_states_count(self) -> None:
        """Проверяет количество состояний регистрации."""
        states = [
            attr for attr in dir(RegistrationStates)
            if isinstance(getattr(RegistrationStates, attr), State)
        ]
        assert len(states) == 4


class TestOrderStates:
    """Тесты для состояний создания заказа."""
    
    def test_order_states_is_states_group(self) -> None:
        """Проверяет, что OrderStates является StatesGroup."""
        assert issubclass(OrderStates, StatesGroup)
    
    def test_order_states_has_pickup_location(self) -> None:
        """Проверяет наличие состояния pickup_location."""
        assert hasattr(OrderStates, "pickup_location")
        assert isinstance(OrderStates.pickup_location, State)
    
    def test_order_states_has_destination_location(self) -> None:
        """Проверяет наличие состояния destination_location."""
        assert hasattr(OrderStates, "destination_location")
        assert isinstance(OrderStates.destination_location, State)
    
    def test_order_states_has_confirm(self) -> None:
        """Проверяет наличие состояния confirm."""
        assert hasattr(OrderStates, "confirm")
        assert isinstance(OrderStates.confirm, State)
    
    def test_order_states_count(self) -> None:
        """Проверяет количество состояний заказа."""
        states = [
            attr for attr in dir(OrderStates)
            if isinstance(getattr(OrderStates, attr), State)
        ]
        assert len(states) == 3


class TestDriverStates:
    """Тесты для состояний водителя."""
    
    def test_driver_states_is_states_group(self) -> None:
        """Проверяет, что DriverStates является StatesGroup."""
        assert issubclass(DriverStates, StatesGroup)
    
    def test_driver_states_has_online(self) -> None:
        """Проверяет наличие состояния online."""
        assert hasattr(DriverStates, "online")
        assert isinstance(DriverStates.online, State)
    
    def test_driver_states_has_on_order(self) -> None:
        """Проверяет наличие состояния on_order."""
        assert hasattr(DriverStates, "on_order")
        assert isinstance(DriverStates.on_order, State)
    
    def test_driver_states_count(self) -> None:
        """Проверяет количество состояний водителя."""
        states = [
            attr for attr in dir(DriverStates)
            if isinstance(getattr(DriverStates, attr), State)
        ]
        assert len(states) == 2


class TestAllStates:
    """Общие тесты для всех состояний."""
    
    def test_all_states_groups_exist(self) -> None:
        """Проверяет, что все группы состояний существуют."""
        assert RegistrationStates is not None
        assert OrderStates is not None
        assert DriverStates is not None
    
    def test_states_are_unique(self) -> None:
        """Проверяет, что состояния не пересекаются между группами."""
        reg_states = {
            name: getattr(RegistrationStates, name)
            for name in dir(RegistrationStates)
            if isinstance(getattr(RegistrationStates, name), State)
        }
        
        order_states = {
            name: getattr(OrderStates, name)
            for name in dir(OrderStates)
            if isinstance(getattr(OrderStates, name), State)
        }
        
        driver_states = {
            name: getattr(DriverStates, name)
            for name in dir(DriverStates)
            if isinstance(getattr(DriverStates, name), State)
        }
        
        # Проверяем, что нет пересечений имён
        all_names = (
            set(reg_states.keys()) |
            set(order_states.keys()) |
            set(driver_states.keys())
        )
        total_count = len(reg_states) + len(order_states) + len(driver_states)
        
        assert len(all_names) == total_count
