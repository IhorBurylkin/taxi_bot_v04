# src/services/realtime_ws/redis_subscriber.py
"""
Подписчик на Redis Pub/Sub для получения обновлений.

Слушает каналы:
- location:driver:{driver_id} — обновления геолокации
- trip:{trip_id} — обновления статуса поездки
- broadcast — глобальные уведомления
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from redis.asyncio import Redis


class RedisSubscriber:
    """
    Подписчик на Redis Pub/Sub.
    
    Получает сообщения и пересылает их через WebSocket.
    """
    
    def __init__(
        self,
        redis: "Redis",
        message_handler: Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Args:
            redis: Клиент Redis
            message_handler: Callback для обработки сообщений (channel, data)
        """
        self._redis = redis
        self._handler = message_handler
        self._pubsub = None
        self._task: asyncio.Task | None = None
        self._running = False
        
        # Паттерны для подписки
        self._patterns: set[str] = set()
        self._channels: set[str] = set()
    
    async def start(self) -> None:
        """Запустить подписчика."""
        if self._running:
            return
        
        self._pubsub = self._redis.pubsub()
        self._running = True
        
        # Подписываемся на базовые паттерны
        await self.subscribe_pattern("location:driver:*")
        await self.subscribe_pattern("trip:*")
        await self.subscribe_channel("broadcast")
        
        # Запускаем обработку сообщений
        self._task = asyncio.create_task(self._listen())
    
    async def stop(self) -> None:
        """Остановить подписчика."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.punsubscribe()
            await self._pubsub.close()
    
    async def subscribe_channel(self, channel: str) -> None:
        """Подписаться на канал."""
        if self._pubsub and channel not in self._channels:
            await self._pubsub.subscribe(channel)
            self._channels.add(channel)
    
    async def subscribe_pattern(self, pattern: str) -> None:
        """Подписаться на паттерн каналов."""
        if self._pubsub and pattern not in self._patterns:
            await self._pubsub.psubscribe(pattern)
            self._patterns.add(pattern)
    
    async def _listen(self) -> None:
        """Слушать сообщения из Redis."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                
                if message is None:
                    continue
                
                # Обрабатываем сообщение
                await self._process_message(message)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Логируем ошибку, но продолжаем работу
                print(f"Redis subscriber error: {e}")
                await asyncio.sleep(1)
    
    async def _process_message(self, message: dict[str, Any]) -> None:
        """Обработать сообщение из Redis."""
        msg_type = message.get("type")
        
        if msg_type not in ("message", "pmessage"):
            return
        
        # Получаем канал
        if msg_type == "pmessage":
            channel = message.get("channel", b"").decode("utf-8")
        else:
            channel = message.get("channel", b"").decode("utf-8")
        
        # Получаем данные
        data = message.get("data", b"")
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            parsed_data = {"raw": data}
        
        # Вызываем handler
        await self._handler(channel, parsed_data)
