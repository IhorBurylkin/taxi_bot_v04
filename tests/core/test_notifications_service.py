# tests/core/test_notifications_service.py
"""
Тесты для сервиса уведомлений.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.notifications.service import NotificationData, NotificationService
from src.infra.event_bus import EventTypes


class TestNotificationData:
    """Тесты для dataclass NotificationData."""
    
    def test_create_notification_data(self) -> None:
        """Проверяет создание данных уведомления."""
        data = NotificationData(
            user_id=123,
            message_key="WELCOME",
            language="ru",
            kwargs={"name": "Иван"},
        )
        
        assert data.user_id == 123
        assert data.message_key == "WELCOME"
        assert data.language == "ru"
        assert data.kwargs == {"name": "Иван"}
        assert data.reply_markup is None
    
    def test_notification_data_defaults(self) -> None:
        """Проверяет значения по умолчанию."""
        data = NotificationData(
            user_id=123,
            message_key="TEST",
        )
        
        assert data.language == "ru"
        assert data.kwargs is None
        assert data.reply_markup is None


class TestNotificationService:
    """Тесты для сервиса уведомлений."""
    
    @pytest.fixture
    def notification_service(self, mock_event_bus: AsyncMock) -> NotificationService:
        """Создаёт сервис с моком."""
        return NotificationService(event_bus=mock_event_bus)
    
    @pytest.mark.asyncio
    async def test_send_notification_success(
        self,
        notification_service: NotificationService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет успешную отправку уведомления."""
        # Настраиваем мок event_bus.publish
        mock_event_bus.publish = AsyncMock()
        
        data = NotificationData(
            user_id=123,
            message_key="WELCOME",
            language="ru",
        )
        
        with patch("src.core.notifications.service.get_text") as mock_get_text:
            mock_get_text.return_value = "Добро пожаловать!"
            
            result = await notification_service.send_notification(data)
        
        assert result is True
        assert mock_event_bus.publish.called
        
        # Проверяем, что событие правильного типа
        call_args = mock_event_bus.publish.call_args[0][0]
        assert call_args.event_type == EventTypes.NOTIFICATION_SEND
        assert call_args.payload["user_id"] == 123
        assert call_args.payload["text"] == "Добро пожаловать!"
    
    @pytest.mark.asyncio
    async def test_send_notification_with_kwargs(
        self,
        notification_service: NotificationService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет отправку уведомления с параметрами."""
        # Настраиваем мок event_bus.publish
        mock_event_bus.publish = AsyncMock()
        
        data = NotificationData(
            user_id=123,
            message_key="GREETING",
            language="ru",
            kwargs={"name": "Иван"},
        )
        
        with patch("src.core.notifications.service.get_text") as mock_get_text:
            mock_get_text.return_value = "Привет, Иван!"
            
            result = await notification_service.send_notification(data)
        
        assert result is True
        mock_get_text.assert_called_once_with("GREETING", "ru", name="Иван")
    
    @pytest.mark.asyncio
    async def test_send_notification_exception(
        self,
        notification_service: NotificationService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет обработку исключения при отправке."""
        data = NotificationData(
            user_id=123,
            message_key="TEST",
        )
        
        mock_event_bus.publish.side_effect = Exception("Event bus error")
        
        with patch("src.core.notifications.service.get_text") as mock_get_text:
            mock_get_text.return_value = "Тест"
            
            result = await notification_service.send_notification(data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_notify_order_created(
        self,
        notification_service: NotificationService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет уведомление о создании заказа."""
        with patch("src.core.notifications.service.get_text") as mock_get_text:
            mock_get_text.return_value = "Ваш заказ создан!"
            
            result = await notification_service.notify_order_created(
                passenger_id=123,
                language="ru",
            )
        
        assert result is True
        mock_event_bus.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_notify_driver_found(
        self,
        notification_service: NotificationService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет уведомление о найденном водителе."""
        with patch("src.core.notifications.service.get_text") as mock_get_text:
            mock_get_text.return_value = "Водитель найден!"
            
            result = await notification_service.notify_driver_found(
                passenger_id=123,
                driver_name="Иван",
                car_info="Toyota Camry",
                language="ru",
            )
        
        assert result is True
        mock_event_bus.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_notify_new_order(
        self,
        notification_service: NotificationService,
        mock_event_bus: AsyncMock,
    ) -> None:
        """Проверяет уведомление о новом заказе для водителя."""
        with patch("src.core.notifications.service.get_text") as mock_get_text:
            mock_get_text.return_value = "Новый заказ!"
            
            result = await notification_service.notify_new_order(
                driver_id=456,
                pickup="ул. Крещатик, 1",
                destination="Аэропорт",
                fare=250.0,
                currency="UAH",
                language="ru",
            )
        
        assert result is True
        mock_event_bus.publish.assert_called_once()
