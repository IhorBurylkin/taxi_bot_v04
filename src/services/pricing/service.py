# src/services/pricing/service.py
"""
Бизнес-логика Pricing Service.
Расчёт стоимости поездок и управление тарифами.
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from src.common.constants import TypeMsg
from src.common.logger import log_info
from src.config import settings
from src.infra.database import DatabaseManager
from src.infra.redis_client import RedisClient
from src.shared.models.trip import FareDTO


class PricingService:
    """Сервис тарификации."""
    
    # Кэш тарифов по городам
    TARIFF_CACHE_TTL = 300  # 5 минут
    
    def __init__(
        self,
        db: DatabaseManager,
        redis: RedisClient,
    ) -> None:
        self._db = db
        self._redis = redis
        
        # Загружаем базовые тарифы из конфига
        self._default_tariff = {
            "base_fare": settings.fares.BASE_FARE,
            "fare_per_km": settings.fares.FARE_PER_KM,
            "fare_per_minute": settings.fares.FARE_PER_MINUTE,
            "pickup_fare": settings.fares.PICKUP_FARE,
            "waiting_fare_per_minute": settings.fares.WAITING_FARE_PER_MINUTE,
            "min_fare": settings.fares.MIN_FARE,
            "surge_max": settings.fares.SURGE_MULTIPLIER_MAX,
            "currency": settings.fares.CURRENCY,
        }
        
        # Курс Stars к USD
        self._stars_to_usd_rate = settings.stars.STARS_TO_USD_RATE
    
    async def calculate_fare(
        self,
        distance_km: float,
        duration_minutes: int,
        surge_multiplier: float = 1.0,
        city: str | None = None,
        waiting_minutes: int = 0,
    ) -> tuple[FareDTO, dict[str, float]]:
        """
        Расчёт стоимости поездки.
        
        Returns:
            Tuple[FareDTO, dict]: (DTO стоимости, детализация расчёта)
        """
        # Получаем тариф для города
        tariff = await self._get_tariff_for_city(city)
        
        # Ограничиваем surge multiplier
        surge = min(surge_multiplier, tariff.get("surge_max", 3.0))
        
        # Рассчитываем компоненты
        base_fare = tariff["base_fare"]
        distance_fare = distance_km * tariff["fare_per_km"]
        time_fare = duration_minutes * tariff["fare_per_minute"]
        pickup_fare = tariff["pickup_fare"]
        waiting_fare = waiting_minutes * tariff["waiting_fare_per_minute"]
        
        # Итоговая стоимость с surge
        subtotal = base_fare + distance_fare + time_fare + pickup_fare + waiting_fare
        total = subtotal * surge
        
        # Минимальная стоимость
        min_fare = tariff["min_fare"] * surge
        total = max(total, min_fare)
        
        # Округляем до целых
        total = round(total)
        
        # Конвертируем в Stars
        stars = await self._convert_eur_to_stars(total)
        
        fare = FareDTO(
            base_fare=base_fare,
            distance_fare=round(distance_fare, 2),
            time_fare=round(time_fare, 2),
            pickup_fare=pickup_fare,
            waiting_fare=round(waiting_fare, 2),
            surge_multiplier=surge,
            total_fare=total,
            currency=tariff["currency"],
            total_stars=stars,
        )
        
        breakdown = {
            "base_fare": base_fare,
            "distance_fare": round(distance_fare, 2),
            "time_fare": round(time_fare, 2),
            "pickup_fare": pickup_fare,
            "waiting_fare": round(waiting_fare, 2),
            "subtotal": round(subtotal, 2),
            "surge_multiplier": surge,
            "total_before_min": round(subtotal * surge, 2),
            "min_fare": min_fare,
            "total_fare": total,
            "total_stars": stars,
        }
        
        return fare, breakdown
    
    async def _get_tariff_for_city(self, city: str | None) -> dict:
        """Получение тарифа для города."""
        if not city:
            return self._default_tariff
        
        cache_key = f"tariff:{city.lower()}"
        
        # Проверяем кэш
        cached = await self._redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
        
        # Ищем в БД
        query = """
            SELECT base_fare, fare_per_km, fare_per_minute, pickup_fare,
                   waiting_fare_per_minute, min_fare, currency
            FROM tariffs
            WHERE LOWER(city) = LOWER($1) AND is_active = true
            LIMIT 1
        """
        
        row = await self._db.fetchrow(query, city)
        
        if row:
            tariff = {
                "base_fare": row["base_fare"],
                "fare_per_km": row["fare_per_km"],
                "fare_per_minute": row["fare_per_minute"],
                "pickup_fare": row["pickup_fare"],
                "waiting_fare_per_minute": row["waiting_fare_per_minute"],
                "min_fare": row["min_fare"],
                "surge_max": self._default_tariff["surge_max"],
                "currency": row["currency"],
            }
            
            # Кэшируем
            import json
            await self._redis.set(
                cache_key,
                json.dumps(tariff),
                ttl=self.TARIFF_CACHE_TTL,
            )
            
            return tariff
        
        return self._default_tariff
    
    async def get_surge_multiplier(
        self,
        lat: float,
        lon: float,
        city: str | None = None,
    ) -> tuple[float, str, str | None]:
        """
        Расчёт коэффициента спроса.
        
        Returns:
            Tuple[float, str, str | None]: (multiplier, level, reason)
        """
        # TODO: Реализовать реальный расчёт surge на основе:
        # - Количества активных заказов в радиусе
        # - Количества доступных водителей
        # - Времени суток
        # - Погоды
        # - Событий в городе
        
        # Пока возвращаем базовый множитель
        # В будущем здесь будет сложная логика
        
        # Проверяем кэш surge для региона
        geo_key = f"surge:{round(lat, 2)}:{round(lon, 2)}"
        cached = await self._redis.get(geo_key)
        
        if cached:
            import json
            data = json.loads(cached)
            return data["multiplier"], data["level"], data.get("reason")
        
        # Базовый расчёт (упрощённый)
        multiplier = 1.0
        level = "normal"
        reason = None
        
        # Проверяем количество заказов в радиусе
        # (в реальности это будет сложнее)
        
        return multiplier, level, reason
    
    async def _convert_eur_to_stars(self, amount_eur: float) -> int:
        """Конвертация EUR в Telegram Stars."""
        # 1 Star ≈ $0.013
        # Нужен курс EUR/USD
        eur_to_usd = 1.08  # Примерный курс
        
        amount_usd = amount_eur * eur_to_usd
        stars = int(amount_usd / self._stars_to_usd_rate)
        
        return max(stars, 1)  # Минимум 1 Star
    
    async def convert_to_stars(
        self,
        amount: float,
        currency: str = "EUR",
    ) -> tuple[int, float]:
        """
        Конвертация суммы в Stars.
        
        Returns:
            Tuple[int, float]: (количество Stars, курс)
        """
        # Курсы к USD
        currency_rates = {
            "USD": 1.0,
            "EUR": 1.08,
            "RUB": 0.011,
            "UAH": 0.027,
        }
        
        rate = currency_rates.get(currency.upper(), 1.0)
        amount_usd = amount * rate
        
        stars = int(amount_usd / self._stars_to_usd_rate)
        stars = max(stars, 1)
        
        return stars, self._stars_to_usd_rate
    
    async def list_tariffs(self, city: str | None = None) -> list[dict]:
        """Список тарифов."""
        conditions = ["is_active = true"]
        values = []
        
        if city:
            conditions.append("LOWER(city) = LOWER($1)")
            values.append(city)
        
        query = f"""
            SELECT id, city, name, base_fare, fare_per_km, fare_per_minute,
                   pickup_fare, waiting_fare_per_minute, min_fare, currency, is_active
            FROM tariffs
            WHERE {" AND ".join(conditions)}
            ORDER BY city, name
        """
        
        rows = await self._db.fetch(query, *values) if values else await self._db.fetch(query)
        
        return [
            {
                "id": str(row["id"]),
                "city": row["city"],
                "name": row["name"],
                "base_fare": row["base_fare"],
                "fare_per_km": row["fare_per_km"],
                "fare_per_minute": row["fare_per_minute"],
                "pickup_fare": row["pickup_fare"],
                "waiting_fare_per_minute": row["waiting_fare_per_minute"],
                "min_fare": row["min_fare"],
                "currency": row["currency"],
                "is_active": row["is_active"],
            }
            for row in rows
        ]
    
    async def get_tariff(self, tariff_id: str) -> Optional[dict]:
        """Получение тарифа по ID."""
        query = """
            SELECT id, city, name, base_fare, fare_per_km, fare_per_minute,
                   pickup_fare, waiting_fare_per_minute, min_fare, currency, is_active
            FROM tariffs
            WHERE id = $1
        """
        
        row = await self._db.fetchrow(query, tariff_id)
        
        if not row:
            return None
        
        return {
            "id": str(row["id"]),
            "city": row["city"],
            "name": row["name"],
            "base_fare": row["base_fare"],
            "fare_per_km": row["fare_per_km"],
            "fare_per_minute": row["fare_per_minute"],
            "pickup_fare": row["pickup_fare"],
            "waiting_fare_per_minute": row["waiting_fare_per_minute"],
            "min_fare": row["min_fare"],
            "currency": row["currency"],
            "is_active": row["is_active"],
        }
    
    async def create_tariff(self, tariff: dict) -> dict:
        """Создание нового тарифа."""
        tariff_id = str(uuid4())
        
        query = """
            INSERT INTO tariffs (id, city, name, base_fare, fare_per_km, fare_per_minute,
                                pickup_fare, waiting_fare_per_minute, min_fare, currency, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
        """
        
        await self._db.execute(
            query,
            tariff_id,
            tariff["city"],
            tariff["name"],
            tariff["base_fare"],
            tariff["fare_per_km"],
            tariff["fare_per_minute"],
            tariff["pickup_fare"],
            tariff["waiting_fare_per_minute"],
            tariff["min_fare"],
            tariff["currency"],
            tariff.get("is_active", True),
        )
        
        # Инвалидируем кэш
        await self._redis.delete(f"tariff:{tariff['city'].lower()}")
        
        await log_info(f"Тариф создан: {tariff_id}", type_msg=TypeMsg.INFO)
        
        tariff["id"] = tariff_id
        return tariff
    
    async def update_tariff(self, tariff_id: str, tariff: dict) -> Optional[dict]:
        """Обновление тарифа."""
        # Получаем текущий тариф для инвалидации кэша
        current = await self.get_tariff(tariff_id)
        if not current:
            return None
        
        query = """
            UPDATE tariffs
            SET city = $2, name = $3, base_fare = $4, fare_per_km = $5,
                fare_per_minute = $6, pickup_fare = $7, waiting_fare_per_minute = $8,
                min_fare = $9, currency = $10, is_active = $11
            WHERE id = $1
            RETURNING id
        """
        
        row = await self._db.fetchrow(
            query,
            tariff_id,
            tariff["city"],
            tariff["name"],
            tariff["base_fare"],
            tariff["fare_per_km"],
            tariff["fare_per_minute"],
            tariff["pickup_fare"],
            tariff["waiting_fare_per_minute"],
            tariff["min_fare"],
            tariff["currency"],
            tariff.get("is_active", True),
        )
        
        if not row:
            return None
        
        # Инвалидируем кэш для обоих городов (старого и нового)
        await self._redis.delete(f"tariff:{current['city'].lower()}")
        await self._redis.delete(f"tariff:{tariff['city'].lower()}")
        
        tariff["id"] = tariff_id
        return tariff
