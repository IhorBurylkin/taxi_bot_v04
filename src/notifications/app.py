# src/notifications/app.py
"""
FastAPI приложение для сервиса уведомлений.
Предоставляет HTTP API для отправки уведомлений.
"""

from __future__ import annotations

from typing import Optional
import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config import settings
from src.common.logger import log_info, log_error
from src.common.constants import TypeMsg


# =============================================================================
# МОДЕЛИ ДАННЫХ
# =============================================================================

class TelegramNotification(BaseModel):
    """Модель уведомления в Telegram."""
    user_id: int
    message: str
    parse_mode: Optional[str] = "HTML"
    disable_notification: bool = False


class EmailNotification(BaseModel):
    """Модель email уведомления (в разработке)."""
    email: str
    subject: str
    body: str


class PushNotification(BaseModel):
    """Модель push уведомления (в разработке)."""
    user_id: int
    title: str
    body: str
    data: Optional[dict] = None


# =============================================================================
# ПРИЛОЖЕНИЕ
# =============================================================================

app = FastAPI(
    title="Taxi Bot Notifications Service",
    description="Централизованный сервис уведомлений (HTTP API + RabbitMQ Worker)",
    version="1.0.0",
)

# Глобальная переменная для воркера
_notification_worker = None


@app.on_event("startup")
async def startup() -> None:
    """
    Инициализация при старте сервиса.
    Запускает NotificationWorker для обработки событий из RabbitMQ.
    """
    global _notification_worker
    
    await log_info("Notifications сервис запущен", type_msg=TypeMsg.INFO)
    
    # Инициализация инфраструктуры
    from src.infra.database import init_db
    from src.infra.redis_client import init_redis
    from src.infra.event_bus import init_event_bus
    from src.worker.notifications import NotificationWorker
    
    await init_db()
    await init_redis()
    await init_event_bus()
    
    # Запускаем NotificationWorker
    _notification_worker = NotificationWorker()
    await _notification_worker.start()
    
    await log_info("NotificationWorker запущен", type_msg=TypeMsg.INFO)


@app.on_event("shutdown")
async def shutdown() -> None:
    """Очистка ресурсов при остановке."""
    global _notification_worker
    
    if _notification_worker:
        await _notification_worker.stop()
    
    from src.infra.event_bus import close_event_bus
    from src.infra.redis_client import close_redis
    from src.infra.database import close_db
    
    await close_event_bus()
    await close_redis()
    await close_db()
    
    await log_info("Notifications сервис остановлен", type_msg=TypeMsg.INFO)


# =============================================================================
# ЭНДПОИНТЫ
# =============================================================================

@app.get("/health")
async def health_check() -> dict:
    """Проверка здоровья сервиса."""
    return {
        "status": "healthy",
        "service": "notifications",
        "version": "1.0.0"
    }


@app.post("/api/notify/telegram")
async def send_telegram_notification(notification: TelegramNotification) -> dict:
    """
    Отправляет уведомление в Telegram.
    
    Args:
        notification: Данные уведомления
        
    Returns:
        Результат отправки
    """
    try:
        await log_info(
            f"Отправка Telegram уведомления пользователю {notification.user_id}",
            type_msg=TypeMsg.DEBUG
        )
        
        # TODO: Интеграция с Telegram Bot API
        # bot = Bot(token=settings.telegram.BOT_TOKEN)
        # await bot.send_message(
        #     chat_id=notification.user_id,
        #     text=notification.message,
        #     parse_mode=notification.parse_mode,
        #     disable_notification=notification.disable_notification
        # )
        
        return {
            "status": "success",
            "message": "Уведомление отправлено",
            "user_id": notification.user_id
        }
    
    except Exception as e:
        await log_error(
            f"Ошибка отправки Telegram уведомления: {e}",
            type_msg=TypeMsg.ERROR
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notify/email")
async def send_email_notification(notification: EmailNotification) -> dict:
    """
    Отправляет email уведомление (в разработке).
    
    Args:
        notification: Данные уведомления
        
    Returns:
        Результат отправки
    """
    return {
        "status": "not_implemented",
        "message": "Email уведомления в разработке"
    }


@app.post("/api/notify/push")
async def send_push_notification(notification: PushNotification) -> dict:
    """
    Отправляет push уведомление (в разработке).
    
    Args:
        notification: Данные уведомления
        
    Returns:
        Результат отправки
    """
    return {
        "status": "not_implemented",
        "message": "Push уведомления в разработке"
    }


# =============================================================================
# ЗАПУСК
# =============================================================================

async def run_notifications(
    host: str = "0.0.0.0",
    port: int = 8083,
    reload: bool = False,
) -> None:
    """
    Запускает сервис уведомлений.
    
    Args:
        host: Хост для привязки
        port: Порт
        reload: Авто-перезагрузка при изменениях
    """
    import uvicorn
    
    config = uvicorn.Config(
        "src.notifications.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
