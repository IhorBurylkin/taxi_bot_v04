# src/services/realtime_location/__init__.py
"""
Realtime Location Ingest — сервис приёма геолокации водителей.

Обеспечивает:
- Высокопроизводительный приём координат (HTTP)
- Сохранение в Redis GEO
- Публикация в Redis Pub/Sub для WebSocket
- Обновление last_seen водителя
"""
