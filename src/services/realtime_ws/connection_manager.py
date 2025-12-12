# src/services/realtime_ws/connection_manager.py
"""
Менеджер WebSocket соединений.
Управляет подписками и рассылкой сообщений.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from weakref import WeakSet

from fastapi import WebSocket


@dataclass
class ConnectionInfo:
    """Информация о соединении."""
    websocket: WebSocket
    user_id: int
    user_type: str  # rider, driver
    connected_at: datetime = field(default_factory=datetime.utcnow)
    subscriptions: set[str] = field(default_factory=set)  # trip_id, driver_id и т.д.


class ConnectionManager:
    """
    Менеджер WebSocket соединений.
    
    Поддерживает:
    - Подключение/отключение клиентов
    - Подписка на топики (trip:{id}, driver:{id})
    - Broadcast сообщений по топикам
    - Персональные сообщения
    """
    
    def __init__(self) -> None:
        # user_id -> ConnectionInfo
        self._connections: dict[int, ConnectionInfo] = {}
        
        # topic -> set of user_ids
        self._subscriptions: dict[str, set[int]] = {}
        
        # Для статистики
        self._total_connections: int = 0
        self._total_messages_sent: int = 0
    
    @property
    def active_connections(self) -> int:
        """Количество активных соединений."""
        return len(self._connections)
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        user_type: str = "rider",
    ) -> None:
        """
        Подключить клиента.
        
        Если у пользователя уже есть соединение — закрываем старое.
        """
        # Закрываем предыдущее соединение если есть
        if user_id in self._connections:
            old_conn = self._connections[user_id]
            await self._close_connection(old_conn)
        
        await websocket.accept()
        
        self._connections[user_id] = ConnectionInfo(
            websocket=websocket,
            user_id=user_id,
            user_type=user_type,
        )
        self._total_connections += 1
    
    async def disconnect(self, user_id: int) -> None:
        """Отключить клиента."""
        if user_id in self._connections:
            conn = self._connections[user_id]
            
            # Отписываемся от всех топиков
            for topic in list(conn.subscriptions):
                self._unsubscribe_from_topic(user_id, topic)
            
            del self._connections[user_id]
    
    async def subscribe(self, user_id: int, topic: str) -> None:
        """
        Подписать пользователя на топик.
        
        Примеры топиков:
        - trip:{trip_id} — обновления поездки
        - driver:{driver_id} — локация водителя
        - order:{order_id} — статус заказа
        """
        if user_id not in self._connections:
            return
        
        self._connections[user_id].subscriptions.add(topic)
        
        if topic not in self._subscriptions:
            self._subscriptions[topic] = set()
        self._subscriptions[topic].add(user_id)
    
    async def unsubscribe(self, user_id: int, topic: str) -> None:
        """Отписать пользователя от топика."""
        self._unsubscribe_from_topic(user_id, topic)
    
    def _unsubscribe_from_topic(self, user_id: int, topic: str) -> None:
        """Внутренний метод отписки."""
        if user_id in self._connections:
            self._connections[user_id].subscriptions.discard(topic)
        
        if topic in self._subscriptions:
            self._subscriptions[topic].discard(user_id)
            if not self._subscriptions[topic]:
                del self._subscriptions[topic]
    
    async def send_personal(self, user_id: int, message: dict[str, Any]) -> bool:
        """
        Отправить сообщение конкретному пользователю.
        
        Returns:
            True если сообщение отправлено, False если пользователь не подключен
        """
        if user_id not in self._connections:
            return False
        
        try:
            await self._connections[user_id].websocket.send_json(message)
            self._total_messages_sent += 1
            return True
        except Exception:
            # Соединение разорвано
            await self.disconnect(user_id)
            return False
    
    async def broadcast_to_topic(self, topic: str, message: dict[str, Any]) -> int:
        """
        Отправить сообщение всем подписчикам топика.
        
        Returns:
            Количество успешно отправленных сообщений
        """
        if topic not in self._subscriptions:
            return 0
        
        sent_count = 0
        failed_users: list[int] = []
        
        for user_id in self._subscriptions[topic]:
            if user_id in self._connections:
                try:
                    await self._connections[user_id].websocket.send_json(message)
                    sent_count += 1
                    self._total_messages_sent += 1
                except Exception:
                    failed_users.append(user_id)
        
        # Отключаем failed соединения
        for user_id in failed_users:
            await self.disconnect(user_id)
        
        return sent_count
    
    async def broadcast_all(self, message: dict[str, Any]) -> int:
        """Отправить сообщение всем подключенным клиентам."""
        sent_count = 0
        failed_users: list[int] = []
        
        for user_id, conn in self._connections.items():
            try:
                await conn.websocket.send_json(message)
                sent_count += 1
                self._total_messages_sent += 1
            except Exception:
                failed_users.append(user_id)
        
        for user_id in failed_users:
            await self.disconnect(user_id)
        
        return sent_count
    
    def get_user_subscriptions(self, user_id: int) -> set[str]:
        """Получить все подписки пользователя."""
        if user_id in self._connections:
            return self._connections[user_id].subscriptions.copy()
        return set()
    
    def get_topic_subscribers(self, topic: str) -> set[int]:
        """Получить всех подписчиков топика."""
        return self._subscriptions.get(topic, set()).copy()
    
    def get_stats(self) -> dict[str, Any]:
        """Получить статистику."""
        return {
            "active_connections": len(self._connections),
            "total_topics": len(self._subscriptions),
            "total_connections_ever": self._total_connections,
            "total_messages_sent": self._total_messages_sent,
            "connections_by_type": self._count_by_type(),
        }
    
    def _count_by_type(self) -> dict[str, int]:
        """Подсчёт соединений по типу."""
        counts: dict[str, int] = {}
        for conn in self._connections.values():
            counts[conn.user_type] = counts.get(conn.user_type, 0) + 1
        return counts
    
    async def _close_connection(self, conn: ConnectionInfo) -> None:
        """Закрыть соединение."""
        try:
            await conn.websocket.close()
        except Exception:
            pass


# Глобальный экземпляр
manager = ConnectionManager()
