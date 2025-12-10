# src/bot/dependencies.py
"""
Dependency Injection для Telegram бота.
Фабрики сервисов и инфраструктуры.
"""

from __future__ import annotations

from typing import Optional

from src.core.users.service import UserService
from src.core.orders.service import OrderService
from src.core.matching.service import MatchingService
from src.core.geo.service import GeoService
from src.core.billing.service import BillingService
from src.core.notifications.service import NotificationService
from src.infra.database import get_db
from src.infra.redis_client import get_redis
from src.infra.event_bus import get_event_bus


# Кэшированные экземпляры сервисов
_user_service: Optional[UserService] = None
_order_service: Optional[OrderService] = None
_matching_service: Optional[MatchingService] = None
_geo_service: Optional[GeoService] = None
_billing_service: Optional[BillingService] = None
_notification_service: Optional[NotificationService] = None


def get_user_service() -> UserService:
    """
    Возвращает сервис пользователей.
    
    Returns:
        UserService
    """
    global _user_service
    if _user_service is None:
        _user_service = UserService(
            db=get_db(),
            redis=get_redis(),
            event_bus=get_event_bus(),
        )
    return _user_service


def get_order_service() -> OrderService:
    """
    Возвращает сервис заказов.
    
    Returns:
        OrderService
    """
    global _order_service
    if _order_service is None:
        _order_service = OrderService(
            db=get_db(),
            redis=get_redis(),
            event_bus=get_event_bus(),
        )
    return _order_service


def get_matching_service() -> MatchingService:
    """
    Возвращает сервис матчинга.
    
    Returns:
        MatchingService
    """
    global _matching_service
    if _matching_service is None:
        _matching_service = MatchingService(
            redis=get_redis(),
            db=get_db(),
        )
    return _matching_service


def get_geo_service() -> GeoService:
    """
    Возвращает geo-сервис.
    
    Returns:
        GeoService
    """
    global _geo_service
    if _geo_service is None:
        _geo_service = GeoService()
    return _geo_service


def get_billing_service() -> BillingService:
    """
    Возвращает сервис биллинга.
    
    Returns:
        BillingService
    """
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService(
            db=get_db(),
            redis=get_redis(),
            event_bus=get_event_bus(),
        )
    return _billing_service


def get_notification_service() -> NotificationService:
    """
    Возвращает сервис уведомлений.
    
    Returns:
        NotificationService
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService(
            event_bus=get_event_bus(),
        )
    return _notification_service


def reset_services() -> None:
    """Сбрасывает кэшированные сервисы (для тестов)."""
    global _user_service, _order_service, _matching_service
    global _geo_service, _billing_service, _notification_service
    
    _user_service = None
    _order_service = None
    _matching_service = None
    _geo_service = None
    _billing_service = None
    _notification_service = None
