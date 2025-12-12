# src/services/__init__.py
"""
Микросервисы приложения.

Архитектура:
- Каждый сервис — независимый FastAPI-приложение
- Общая PostgreSQL с логическим разделением
- Коммуникация через RabbitMQ (события) и HTTP (синхронно)
- Redis для кэширования и Pub/Sub

Сервисы:
- users_service: профили, документы, статусы, роли (driver/rider)
- trip_service: state machine заказа/поездки + история событий
- pricing_service: тарифы + тарифные зоны
- payments_service: учёт платежей, Stars (XTR)
- order_matching_service: матчинг/диспетчеризация
- notifications_service: очередь уведомлений
- miniapp_bff: BFF для Telegram Mini App
- telegram_bot_gateway: webhooks/commands/callbacks
- realtime_location_ingest: приём координат водителей
- realtime_ws_gateway: WebSocket для live-tracking
"""

__all__: list[str] = []
