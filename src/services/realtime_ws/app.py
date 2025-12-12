# src/services/realtime_ws/app.py
"""
FastAPI приложение для Realtime WebSocket Gateway.

WebSocket endpoints:
- /ws/rider/{user_id} — для пассажиров
- /ws/driver/{user_id} — для водителей

REST endpoints:
- GET /health — проверка здоровья
- GET /stats — статистика соединений
- POST /broadcast — отправить сообщение всем
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from pydantic import BaseModel

from src.shared.models.common import HealthStatus
from src.services.realtime_ws.connection_manager import manager, ConnectionManager
from src.services.realtime_ws.redis_subscriber import RedisSubscriber


# === MODELS ===

class BroadcastRequest(BaseModel):
    """Запрос на broadcast."""
    topic: str | None = None  # Если None — всем
    message: dict[str, Any]


class StatsResponse(BaseModel):
    """Статистика соединений."""
    active_connections: int
    total_topics: int
    total_connections_ever: int
    total_messages_sent: int
    connections_by_type: dict[str, int]


# === REDIS HANDLER ===

async def handle_redis_message(channel: str, data: dict[str, Any]) -> None:
    """
    Обработать сообщение из Redis и переслать в WebSocket.
    
    Каналы:
    - location:driver:{driver_id} → topic driver:{driver_id}
    - trip:{trip_id} → topic trip:{trip_id}
    - broadcast → всем
    """
    if channel == "broadcast":
        await manager.broadcast_all(data)
        return
    
    # Преобразуем канал Redis в топик WebSocket
    if channel.startswith("location:driver:"):
        driver_id = channel.split(":")[-1]
        topic = f"driver:{driver_id}"
        message = {
            "type": "location_update",
            "driver_id": driver_id,
            "data": data,
        }
    elif channel.startswith("trip:"):
        trip_id = channel.split(":")[-1]
        topic = f"trip:{trip_id}"
        message = {
            "type": "trip_update",
            "trip_id": trip_id,
            "data": data,
        }
    else:
        # Неизвестный канал
        return
    
    await manager.broadcast_to_topic(topic, message)


# === LIFESPAN ===

_redis_subscriber: RedisSubscriber | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения."""
    global _redis_subscriber
    
    # Startup
    from redis.asyncio import Redis
    from src.config import settings
    
    redis = Redis(
        host=settings.redis.REDIS_HOST,
        port=settings.redis.REDIS_PORT,
        db=settings.redis.REDIS_DB,
        password=settings.redis.REDIS_PASSWORD,
    )
    
    _redis_subscriber = RedisSubscriber(redis, handle_redis_message)
    await _redis_subscriber.start()
    
    yield
    
    # Shutdown
    if _redis_subscriber:
        await _redis_subscriber.stop()
    await redis.close()


# === APP ===

app = FastAPI(
    title="Realtime WebSocket Gateway",
    description="WebSocket сервис для live-tracking поездок и локации водителей.",
    version="0.5.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# === HEALTH CHECK ===

@app.get("/health", response_model=HealthStatus, tags=["Health"])
async def health_check() -> HealthStatus:
    """Проверка здоровья сервиса."""
    return HealthStatus(
        status="healthy",
        service="realtime_ws_gateway",
        version="0.5.0",
    )


# === STATS ===

@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats() -> StatsResponse:
    """Получить статистику соединений."""
    stats = manager.get_stats()
    return StatsResponse(**stats)


# === BROADCAST ===

@app.post("/broadcast", tags=["Admin"])
async def broadcast_message(request: BroadcastRequest) -> dict[str, Any]:
    """
    Отправить сообщение клиентам.
    
    - Если указан `topic` — только подписчикам топика
    - Если `topic=null` — всем подключенным
    """
    if request.topic:
        sent = await manager.broadcast_to_topic(request.topic, request.message)
    else:
        sent = await manager.broadcast_all(request.message)
    
    return {"sent_count": sent}


# === WEBSOCKET ENDPOINTS ===

@app.websocket("/ws/rider/{user_id}")
async def websocket_rider(
    websocket: WebSocket,
    user_id: int,
    trip_id: str | None = Query(default=None),
) -> None:
    """
    WebSocket для пассажиров.
    
    Подписывается на обновления поездки и локацию водителя.
    
    Входящие сообщения:
    - {"action": "subscribe", "topic": "trip:xxx"}
    - {"action": "unsubscribe", "topic": "trip:xxx"}
    - {"action": "ping"}
    """
    await manager.connect(websocket, user_id, "rider")
    
    # Автоматическая подписка на поездку если передан trip_id
    if trip_id:
        await manager.subscribe(user_id, f"trip:{trip_id}")
    
    try:
        while True:
            data = await websocket.receive_json()
            await _handle_client_message(user_id, data)
    
    except WebSocketDisconnect:
        await manager.disconnect(user_id)
    except Exception:
        await manager.disconnect(user_id)


@app.websocket("/ws/driver/{user_id}")
async def websocket_driver(
    websocket: WebSocket,
    user_id: int,
    trip_id: str | None = Query(default=None),
) -> None:
    """
    WebSocket для водителей.
    
    Подписывается на обновления назначенных заказов.
    
    Входящие сообщения:
    - {"action": "subscribe", "topic": "trip:xxx"}
    - {"action": "unsubscribe", "topic": "trip:xxx"}
    - {"action": "location", "lat": 53.55, "lon": 10.0}
    - {"action": "ping"}
    """
    await manager.connect(websocket, user_id, "driver")
    
    # Автоматическая подписка на поездку если передан trip_id
    if trip_id:
        await manager.subscribe(user_id, f"trip:{trip_id}")
    
    try:
        while True:
            data = await websocket.receive_json()
            await _handle_client_message(user_id, data)
    
    except WebSocketDisconnect:
        await manager.disconnect(user_id)
    except Exception:
        await manager.disconnect(user_id)


async def _handle_client_message(user_id: int, data: dict[str, Any]) -> None:
    """Обработать сообщение от клиента."""
    action = data.get("action")
    
    if action == "subscribe":
        topic = data.get("topic")
        if topic:
            await manager.subscribe(user_id, topic)
            await manager.send_personal(user_id, {
                "type": "subscribed",
                "topic": topic,
            })
    
    elif action == "unsubscribe":
        topic = data.get("topic")
        if topic:
            await manager.unsubscribe(user_id, topic)
            await manager.send_personal(user_id, {
                "type": "unsubscribed",
                "topic": topic,
            })
    
    elif action == "ping":
        await manager.send_personal(user_id, {"type": "pong"})
    
    elif action == "location":
        # Водитель отправляет локацию через WS (альтернатива HTTP)
        lat = data.get("lat")
        lon = data.get("lon")
        if lat is not None and lon is not None:
            # Публикуем в Redis для других подписчиков
            # Это будет обрабатывать realtime_location_ingest
            pass


# === STARTUP ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8089)
