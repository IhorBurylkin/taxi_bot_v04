# tests/bot/test_dependencies.py
"""
Тесты для Dependency Injection Telegram бота.
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from src.bot.dependencies import (
    get_user_service,
    get_order_service,
    get_matching_service,
    get_geo_service,
    get_billing_service,
    get_notification_service,
    reset_services,
)
from src.core.users.service import UserService
from src.core.orders.service import OrderService
from src.core.matching.service import MatchingService
from src.core.geo.service import GeoService
from src.core.billing.service import BillingService
from src.core.notifications.service import NotificationService


class TestDependencies:
    """Тесты для фабрик сервисов."""
    
    @pytest.fixture(autouse=True)
    def reset(self) -> Generator[None, None, None]:
        """Сбрасывает кэшированные сервисы перед каждым тестом."""
        reset_services()
        yield
        reset_services()
    
    @patch("src.bot.dependencies.get_db")
    @patch("src.bot.dependencies.get_redis")
    @patch("src.bot.dependencies.get_event_bus")
    def test_get_user_service(
        self,
        mock_event_bus: MagicMock,
        mock_redis: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет получение сервиса пользователей."""
        # Arrange
        mock_db.return_value = MagicMock()
        mock_redis.return_value = MagicMock()
        mock_event_bus.return_value = MagicMock()
        
        # Act
        service = get_user_service()
        
        # Assert
        assert isinstance(service, UserService)
        mock_db.assert_called_once()
        mock_redis.assert_called_once()
        mock_event_bus.assert_called_once()
    
    @patch("src.bot.dependencies.get_db")
    @patch("src.bot.dependencies.get_redis")
    @patch("src.bot.dependencies.get_event_bus")
    def test_get_user_service_singleton(
        self,
        mock_event_bus: MagicMock,
        mock_redis: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет, что сервис пользователей - синглтон."""
        # Arrange
        mock_db.return_value = MagicMock()
        mock_redis.return_value = MagicMock()
        mock_event_bus.return_value = MagicMock()
        
        # Act
        service1 = get_user_service()
        service2 = get_user_service()
        
        # Assert
        assert service1 is service2
        assert mock_db.call_count == 1  # Должен быть вызван только один раз
    
    @patch("src.bot.dependencies.get_db")
    @patch("src.bot.dependencies.get_redis")
    @patch("src.bot.dependencies.get_event_bus")
    def test_get_order_service(
        self,
        mock_event_bus: MagicMock,
        mock_redis: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет получение сервиса заказов."""
        # Arrange
        mock_db.return_value = MagicMock()
        mock_redis.return_value = MagicMock()
        mock_event_bus.return_value = MagicMock()
        
        # Act
        service = get_order_service()
        
        # Assert
        assert isinstance(service, OrderService)
    
    @patch("src.bot.dependencies.get_db")
    @patch("src.bot.dependencies.get_redis")
    @patch("src.bot.dependencies.get_event_bus")
    def test_get_order_service_singleton(
        self,
        mock_event_bus: MagicMock,
        mock_redis: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет, что сервис заказов - синглтон."""
        # Arrange
        mock_db.return_value = MagicMock()
        mock_redis.return_value = MagicMock()
        mock_event_bus.return_value = MagicMock()
        
        # Act
        service1 = get_order_service()
        service2 = get_order_service()
        
        # Assert
        assert service1 is service2
    
    @patch("src.bot.dependencies.get_db")
    @patch("src.bot.dependencies.get_redis")
    def test_get_matching_service(
        self,
        mock_redis: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет получение сервиса матчинга."""
        # Arrange
        mock_redis.return_value = MagicMock()
        mock_db.return_value = MagicMock()
        
        # Act
        service = get_matching_service()
        
        # Assert
        assert isinstance(service, MatchingService)
    
    def test_get_geo_service(self) -> None:
        """Проверяет получение geo-сервиса."""
        # Act
        service = get_geo_service()
        
        # Assert
        assert isinstance(service, GeoService)
    
    def test_get_geo_service_singleton(self) -> None:
        """Проверяет, что geo-сервис - синглтон."""
        # Act
        service1 = get_geo_service()
        service2 = get_geo_service()
        
        # Assert
        assert service1 is service2
    
    @patch("src.bot.dependencies.get_db")
    @patch("src.bot.dependencies.get_redis")
    @patch("src.bot.dependencies.get_event_bus")
    def test_get_billing_service(
        self,
        mock_event_bus: MagicMock,
        mock_redis: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет получение сервиса биллинга."""
        # Arrange
        mock_db.return_value = MagicMock()
        mock_redis.return_value = MagicMock()
        mock_event_bus.return_value = MagicMock()
        
        # Act
        service = get_billing_service()
        
        # Assert
        assert isinstance(service, BillingService)
    
    @patch("src.bot.dependencies.get_event_bus")
    def test_get_notification_service(
        self,
        mock_event_bus: MagicMock,
    ) -> None:
        """Проверяет получение сервиса уведомлений."""
        # Arrange
        mock_event_bus.return_value = MagicMock()
        
        # Act
        service = get_notification_service()
        
        # Assert
        assert isinstance(service, NotificationService)
    
    @patch("src.bot.dependencies.get_db")
    @patch("src.bot.dependencies.get_redis")
    @patch("src.bot.dependencies.get_event_bus")
    def test_reset_services(
        self,
        mock_event_bus: MagicMock,
        mock_redis: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет сброс кэшированных сервисов."""
        # Arrange
        mock_db.return_value = MagicMock()
        mock_redis.return_value = MagicMock()
        mock_event_bus.return_value = MagicMock()
        
        # Создаём сервисы
        service1 = get_user_service()
        
        # Act
        reset_services()
        service2 = get_user_service()
        
        # Assert
        assert service1 is not service2
    
    @patch("src.bot.dependencies.get_db")
    @patch("src.bot.dependencies.get_redis")
    @patch("src.bot.dependencies.get_event_bus")
    def test_all_services_independent(
        self,
        mock_event_bus: MagicMock,
        mock_redis: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """Проверяет независимость всех сервисов."""
        # Arrange
        mock_db.return_value = MagicMock()
        mock_redis.return_value = MagicMock()
        mock_event_bus.return_value = MagicMock()
        
        # Act
        user_service = get_user_service()
        order_service = get_order_service()
        matching_service = get_matching_service()
        geo_service = get_geo_service()
        billing_service = get_billing_service()
        notification_service = get_notification_service()
        
        # Assert
        services = {
            user_service,
            order_service,
            matching_service,
            geo_service,
            billing_service,
            notification_service,
        }
        assert len(services) == 6  # Все сервисы разные
