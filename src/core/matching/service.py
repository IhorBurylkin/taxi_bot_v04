# src/core/matching/service.py
"""
Сервис поиска водителей.
Использует Redis Geo для быстрого поиска ближайших водителей.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.common.constants import TypeMsg
from src.common.logger import log_info, log_error
from src.infra.redis_client import RedisClient
from src.infra.database import DatabaseManager


@dataclass
class DriverCandidate:
    """Кандидат водителя для заказа."""
    driver_id: int
    distance_km: float
    last_seen: Optional[datetime] = None


class MatchingService:
    """
    Сервис матчинга заказов с водителями.
    
    Использует Redis Geo-индекс для быстрого поиска ближайших водителей.
    """
    
    def __init__(
        self,
        redis: RedisClient,
        db: DatabaseManager,
    ) -> None:
        """
        Инициализация сервиса.
        
        Args:
            redis: Клиент Redis
            db: Менеджер базы данных
        """
        self._redis = redis
        self._db = db
    
    async def find_nearby_drivers(
        self,
        latitude: float,
        longitude: float,
        radius_km: float | None = None,
        max_count: int | None = None,
    ) -> list[DriverCandidate]:
        """
        Ищет водителей в радиусе от точки.
        
        Args:
            latitude: Широта точки подачи
            longitude: Долгота точки подачи
            radius_km: Радиус поиска в км (из конфига если None)
            max_count: Максимальное количество водителей
            
        Returns:
            Список кандидатов, отсортированных по расстоянию
        """
        try:
            from src.config import settings
            
            if radius_km is None:
                radius_km = settings.search.SEARCH_RADIUS_MAX_KM
            
            if max_count is None:
                max_count = settings.search.MAX_DRIVERS_TO_NOTIFY
            
            # Ищем в geo-индексе
            results = await self._redis.georadius(
                "drivers:locations",
                longitude,
                latitude,
                radius_km,
                unit="km",
                with_dist=True,
                count=max_count,
                sort="ASC",
            )
            
            candidates = []
            
            for driver_id_str, distance in results:
                driver_id = int(driver_id_str)
                
                # Проверяем last_seen
                last_seen_str = await self._redis.get(f"driver:last_seen:{driver_id}")
                last_seen = None
                if last_seen_str:
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str)
                    except ValueError:
                        pass
                
                candidates.append(DriverCandidate(
                    driver_id=driver_id,
                    distance_km=round(distance, 2),
                    last_seen=last_seen,
                ))
            
            await log_info(
                f"Найдено {len(candidates)} водителей в радиусе {radius_km} км",
                type_msg=TypeMsg.DEBUG,
            )
            
            return candidates
        except Exception as e:
            await log_error(f"Ошибка поиска водителей: {e}")
            return []
    
    async def find_drivers_incrementally(
        self,
        latitude: float,
        longitude: float,
    ) -> list[DriverCandidate]:
        """
        Ищет водителей с постепенным увеличением радиуса.
        
        Args:
            latitude: Широта точки подачи
            longitude: Долгота точки подачи
            
        Returns:
            Список найденных кандидатов
        """
        from src.config import settings
        
        radius = settings.search.SEARCH_RADIUS_MIN_KM
        max_radius = settings.search.SEARCH_RADIUS_MAX_KM
        step = settings.search.SEARCH_RADIUS_STEP_KM
        max_count = settings.search.MAX_DRIVERS_TO_NOTIFY
        
        all_candidates = []
        
        while radius <= max_radius:
            candidates = await self.find_nearby_drivers(
                latitude,
                longitude,
                radius_km=radius,
                max_count=max_count,
            )
            
            if candidates:
                all_candidates = candidates
                
                # Если нашли достаточно — прекращаем
                if len(candidates) >= max_count:
                    break
            
            radius += step
        
        return all_candidates
    
    async def filter_available_drivers(
        self,
        candidates: list[DriverCandidate],
        order_id: str,
    ) -> list[DriverCandidate]:
        """
        Фильтрует водителей, исключая тех, кто уже уведомлён или отказался.
        
        Args:
            candidates: Список кандидатов
            order_id: ID заказа
            
        Returns:
            Отфильтрованный список
        """
        if not candidates:
            return []
        
        filtered = []
        
        for candidate in candidates:
            # Проверяем, не уведомлён ли уже
            notified_key = f"order:{order_id}:notified:{candidate.driver_id}"
            if await self._redis.exists(notified_key):
                continue
            
            # Проверяем, не отказался ли
            rejected_key = f"order:{order_id}:rejected:{candidate.driver_id}"
            if await self._redis.exists(rejected_key):
                continue
            
            filtered.append(candidate)
        
        return filtered
    
    async def mark_driver_notified(
        self,
        order_id: str,
        driver_id: int,
    ) -> None:
        """
        Помечает водителя как уведомлённого о заказе.
        
        Args:
            order_id: ID заказа
            driver_id: ID водителя
        """
        from src.config import settings
        
        key = f"order:{order_id}:notified:{driver_id}"
        await self._redis.set(
            key,
            "1",
            ttl=settings.redis_ttl.NOTIFIED_DRIVERS_TTL,
        )
    
    async def mark_driver_rejected(
        self,
        order_id: str,
        driver_id: int,
    ) -> None:
        """
        Помечает, что водитель отказался от заказа.
        
        Args:
            order_id: ID заказа
            driver_id: ID водителя
        """
        from src.config import settings
        
        key = f"order:{order_id}:rejected:{driver_id}"
        await self._redis.set(
            key,
            "1",
            ttl=settings.redis_ttl.NOTIFIED_DRIVERS_TTL,
        )
    
    async def get_best_candidate(
        self,
        latitude: float,
        longitude: float,
        order_id: str,
    ) -> Optional[DriverCandidate]:
        """
        Возвращает лучшего доступного кандидата для заказа.
        
        Args:
            latitude: Широта точки подачи
            longitude: Долгота точки подачи
            order_id: ID заказа
            
        Returns:
            Лучший кандидат или None
        """
        candidates = await self.find_drivers_incrementally(latitude, longitude)
        filtered = await self.filter_available_drivers(candidates, order_id)
        
        if not filtered:
            return None
        
        # Возвращаем ближайшего
        return filtered[0]
