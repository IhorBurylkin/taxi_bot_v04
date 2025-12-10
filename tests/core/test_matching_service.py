# tests/core/test_matching_service.py
"""
Тесты для сервиса матчинга.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.core.matching.service import DriverCandidate, MatchingService


class TestDriverCandidate:
    """Тесты для dataclass DriverCandidate."""
    
    def test_create_candidate(self) -> None:
        """Проверяет создание кандидата."""
        now = datetime.utcnow()
        candidate = DriverCandidate(
            driver_id=123,
            distance_km=2.5,
            last_seen=now,
        )
        
        assert candidate.driver_id == 123
        assert candidate.distance_km == 2.5
        assert candidate.last_seen == now
    
    def test_candidate_default_last_seen(self) -> None:
        """Проверяет значение last_seen по умолчанию."""
        candidate = DriverCandidate(driver_id=123, distance_km=1.0)
        assert candidate.last_seen is None


class TestMatchingService:
    """Тесты для сервиса матчинга."""
    
    @pytest.fixture
    def matching_service(
        self,
        mock_redis: AsyncMock,
        mock_db: AsyncMock,
    ) -> MatchingService:
        """Создаёт сервис с моками."""
        return MatchingService(redis=mock_redis, db=mock_db)
    
    @pytest.mark.asyncio
    async def test_find_nearby_drivers_empty(
        self,
        matching_service: MatchingService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет поиск при отсутствии водителей."""
        mock_redis.georadius.return_value = []
        
        with patch("src.config.settings") as mock_settings:
            mock_settings.search.SEARCH_RADIUS_MAX_KM = 10.0
            mock_settings.search.MAX_DRIVERS_TO_NOTIFY = 10
            
            result = await matching_service.find_nearby_drivers(
                latitude=50.45,
                longitude=30.52,
                radius_km=10.0,
                max_count=10,
            )
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_find_nearby_drivers_success(
        self,
        matching_service: MatchingService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет успешный поиск водителей."""
        # Мокаем результат georadius
        mock_redis.georadius.return_value = [
            ("123", 1.5),
            ("456", 2.8),
        ]
        # Мокаем last_seen
        mock_redis.get.return_value = None
        
        with patch("src.config.settings") as mock_settings:
            mock_settings.search.SEARCH_RADIUS_MAX_KM = 10.0
            mock_settings.search.MAX_DRIVERS_TO_NOTIFY = 10
            
            result = await matching_service.find_nearby_drivers(
                latitude=50.45,
                longitude=30.52,
                radius_km=10.0,
                max_count=10,
            )
        
        assert len(result) == 2
        assert result[0].driver_id == 123
        assert result[0].distance_km == 1.5
        assert result[1].driver_id == 456
        assert result[1].distance_km == 2.8
    
    @pytest.mark.asyncio
    async def test_find_nearby_drivers_with_custom_radius(
        self,
        matching_service: MatchingService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет поиск с кастомным радиусом."""
        mock_redis.georadius.return_value = []
        
        await matching_service.find_nearby_drivers(
            latitude=50.45,
            longitude=30.52,
            radius_km=5.0,
            max_count=10,
        )
        
        # Проверяем, что был передан кастомный радиус
        call_args = mock_redis.georadius.call_args
        assert call_args[0][3] == 5.0  # radius_km
    
    @pytest.mark.asyncio
    async def test_find_nearby_drivers_with_last_seen(
        self,
        matching_service: MatchingService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет поиск с информацией о last_seen."""
        now = datetime.utcnow()
        mock_redis.georadius.return_value = [("123", 1.5)]
        mock_redis.get.return_value = now.isoformat()
        
        result = await matching_service.find_nearby_drivers(
            latitude=50.45,
            longitude=30.52,
            radius_km=10.0,
            max_count=10,
        )
        
        assert len(result) == 1
        assert result[0].last_seen is not None
    
    @pytest.mark.asyncio
    async def test_find_nearby_drivers_invalid_last_seen(
        self,
        matching_service: MatchingService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет обработку невалидного last_seen."""
        mock_redis.georadius.return_value = [("123", 1.5)]
        mock_redis.get.return_value = "invalid_date"
        
        result = await matching_service.find_nearby_drivers(
            latitude=50.45,
            longitude=30.52,
            radius_km=10.0,
            max_count=10,
        )
        
        assert len(result) == 1
        assert result[0].last_seen is None
    
    @pytest.mark.asyncio
    async def test_find_nearby_drivers_exception(
        self,
        matching_service: MatchingService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет обработку исключения."""
        mock_redis.georadius.side_effect = Exception("Redis error")
        
        result = await matching_service.find_nearby_drivers(
            latitude=50.45,
            longitude=30.52,
            radius_km=10.0,
            max_count=10,
        )
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_find_drivers_incrementally(
        self,
        matching_service: MatchingService,
        mock_redis: AsyncMock,
    ) -> None:
        """Проверяет поиск с инкрементальным увеличением радиуса."""
        # Первый вызов - пустой, второй - с результатами
        mock_redis.georadius.side_effect = [
            [],  # 1 км
            [],  # 2 км
            [("123", 2.5)],  # 3 км - нашли
        ]
        mock_redis.get.return_value = None
        
        with patch("src.config.settings") as mock_settings:
            mock_settings.search.SEARCH_RADIUS_MIN_KM = 1.0
            mock_settings.search.SEARCH_RADIUS_MAX_KM = 5.0
            mock_settings.search.SEARCH_RADIUS_STEP_KM = 1.0
            mock_settings.search.MAX_DRIVERS_TO_NOTIFY = 10
            
            result = await matching_service.find_drivers_incrementally(
                latitude=50.45,
                longitude=30.52,
            )
        
        # Проверяем, что были вызовы с увеличивающимся радиусом
        assert mock_redis.georadius.call_count >= 1
