# tests/common/test_constants.py
"""
Тесты для модуля констант.
"""

import pytest

from src.common.constants import (
    TypeMsg,
    UserRole,
    OrderStatus,
    DriverStatus,
    PaymentStatus,
    PaymentMethod,
)


class TestTypeMsg:
    """Тесты для enum TypeMsg."""
    
    def test_type_msg_values(self) -> None:
        """Проверяет значения типов сообщений."""
        assert TypeMsg.DEBUG.value == "debug"
        assert TypeMsg.INFO.value == "info"
        assert TypeMsg.WARNING.value == "warning"
        assert TypeMsg.ERROR.value == "error"
        assert TypeMsg.CRITICAL.value == "critical"
    
    def test_type_msg_is_str_enum(self) -> None:
        """Проверяет, что TypeMsg является строковым enum."""
        assert isinstance(TypeMsg.DEBUG, str)
        assert TypeMsg.INFO == "info"
    
    def test_type_msg_membership(self) -> None:
        """Проверяет членство в enum."""
        assert TypeMsg.DEBUG in TypeMsg
        assert TypeMsg.INFO in TypeMsg


class TestUserRole:
    """Тесты для enum UserRole."""
    
    def test_user_role_values(self) -> None:
        """Проверяет значения ролей пользователей."""
        assert UserRole.PASSENGER.value == "passenger"
        assert UserRole.DRIVER.value == "driver"
        assert UserRole.ADMIN.value == "admin"
    
    def test_user_role_is_str_enum(self) -> None:
        """Проверяет, что UserRole является строковым enum."""
        assert isinstance(UserRole.PASSENGER, str)
        assert UserRole.DRIVER == "driver"
    
    def test_all_roles_exist(self) -> None:
        """Проверяет наличие всех основных ролей."""
        roles = list(UserRole)
        assert len(roles) == 3
        assert UserRole.PASSENGER in roles
        assert UserRole.DRIVER in roles
        assert UserRole.ADMIN in roles


class TestOrderStatus:
    """Тесты для enum OrderStatus."""
    
    def test_order_status_values(self) -> None:
        """Проверяет значения статусов заказа."""
        assert OrderStatus.CREATED.value == "created"
        assert OrderStatus.SEARCHING.value == "searching"
        assert OrderStatus.ACCEPTED.value == "accepted"
        assert OrderStatus.DRIVER_ARRIVED.value == "driver_arrived"
        assert OrderStatus.IN_PROGRESS.value == "in_progress"
        assert OrderStatus.COMPLETED.value == "completed"
        assert OrderStatus.CANCELLED.value == "cancelled"
        assert OrderStatus.EXPIRED.value == "expired"
    
    def test_order_status_is_str_enum(self) -> None:
        """Проверяет, что OrderStatus является строковым enum."""
        assert isinstance(OrderStatus.CREATED, str)
        assert OrderStatus.COMPLETED == "completed"
    
    def test_active_statuses(self) -> None:
        """Проверяет активные статусы заказа."""
        active_statuses = [
            OrderStatus.CREATED,
            OrderStatus.SEARCHING,
            OrderStatus.ACCEPTED,
            OrderStatus.DRIVER_ARRIVED,
            OrderStatus.IN_PROGRESS,
        ]
        
        for status in active_statuses:
            assert status in OrderStatus
    
    def test_terminal_statuses(self) -> None:
        """Проверяет терминальные статусы заказа."""
        terminal_statuses = [
            OrderStatus.COMPLETED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
        ]
        
        for status in terminal_statuses:
            assert status in OrderStatus


class TestDriverStatus:
    """Тесты для enum DriverStatus."""
    
    def test_driver_status_values(self) -> None:
        """Проверяет значения статусов водителя."""
        assert DriverStatus.OFFLINE.value == "offline"
        assert DriverStatus.ONLINE.value == "online"
        assert DriverStatus.BUSY.value == "busy"
    
    def test_driver_status_is_str_enum(self) -> None:
        """Проверяет, что DriverStatus является строковым enum."""
        assert isinstance(DriverStatus.ONLINE, str)
        assert DriverStatus.BUSY == "busy"
    
    def test_all_driver_statuses_exist(self) -> None:
        """Проверяет наличие всех статусов водителя."""
        statuses = list(DriverStatus)
        assert len(statuses) == 3


class TestPaymentStatus:
    """Тесты для enum PaymentStatus."""
    
    def test_payment_status_values(self) -> None:
        """Проверяет значения статусов оплаты."""
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.COMPLETED.value == "completed"
        assert PaymentStatus.FAILED.value == "failed"
        assert PaymentStatus.REFUNDED.value == "refunded"
    
    def test_payment_status_is_str_enum(self) -> None:
        """Проверяет, что PaymentStatus является строковым enum."""
        assert isinstance(PaymentStatus.PENDING, str)


class TestPaymentMethod:
    """Тесты для enum PaymentMethod."""
    
    def test_payment_method_values(self) -> None:
        """Проверяет значения способов оплаты."""
        assert PaymentMethod.CASH.value == "cash"
        assert PaymentMethod.CARD.value == "card"
        assert PaymentMethod.STARS.value == "stars"
    
    def test_payment_method_is_str_enum(self) -> None:
        """Проверяет, что PaymentMethod является строковым enum."""
        assert isinstance(PaymentMethod.CASH, str)
        assert PaymentMethod.CARD == "card"
    
    def test_all_payment_methods_exist(self) -> None:
        """Проверяет наличие всех способов оплаты."""
        methods = list(PaymentMethod)
        assert len(methods) == 3
