# src/core/orders/service.py
"""
Сервис для работы с заказами.
Координирует бизнес-логику заказов.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.common.constants import OrderStatus, DriverStatus, TypeMsg
from src.common.logger import log_info, log_error
from src.core.orders.models import Order, OrderCreateDTO, FareCalculationDTO
from src.core.orders.repository import OrderRepository
from src.infra.database import DatabaseManager
from src.infra.redis_client import RedisClient
from src.infra.event_bus import EventBus, DomainEvent, EventTypes


class FareCalculator:
    """Калькулятор стоимости поездки."""
    
    def __init__(self) -> None:
        """Инициализация с загрузкой тарифов из конфига."""
        from src.config import settings
        
        self.base_fare = settings.fares.BASE_FARE
        self.fare_per_km = settings.fares.FARE_PER_KM
        self.fare_per_minute = settings.fares.FARE_PER_MINUTE
        self.pickup_fare = settings.fares.PICKUP_FARE
        self.min_fare = settings.fares.MIN_FARE
        self.surge_max = settings.fares.SURGE_MULTIPLIER_MAX
        self.currency = settings.fares.CURRENCY
    
    def calculate(
        self,
        distance_km: float,
        duration_minutes: int,
        surge_multiplier: float = 1.0,
    ) -> FareCalculationDTO:
        """
        Рассчитывает стоимость поездки.
        
        Args:
            distance_km: Расстояние в километрах
            duration_minutes: Время поездки в минутах
            surge_multiplier: Коэффициент спроса
            
        Returns:
            Результат расчёта
        """
        # Ограничиваем surge multiplier
        surge = min(surge_multiplier, self.surge_max)
        
        # Рассчитываем компоненты
        distance_fare = distance_km * self.fare_per_km
        time_fare = duration_minutes * self.fare_per_minute
        
        # Итоговая стоимость
        total = (self.base_fare + distance_fare + time_fare + self.pickup_fare) * surge
        
        # Минимальная стоимость
        total = max(total, self.min_fare * surge)
        
        # Округляем до целых
        total = round(total)
        
        return FareCalculationDTO(
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            base_fare=self.base_fare,
            distance_fare=distance_fare,
            time_fare=time_fare,
            pickup_fare=self.pickup_fare,
            surge_multiplier=surge,
            total_fare=total,
            currency=self.currency,
        )


class OrderService:
    """
    Сервис заказов.
    Управляет жизненным циклом заказов.
    """
    
    def __init__(
        self,
        db: DatabaseManager,
        redis: RedisClient,
        event_bus: EventBus,
    ) -> None:
        """
        Инициализация сервиса.
        
        Args:
            db: Менеджер базы данных
            redis: Клиент Redis
            event_bus: Шина событий
        """
        self._repo = OrderRepository(db)
        self._redis = redis
        self._event_bus = event_bus
        self._fare_calculator = FareCalculator()
    
    def _order_cache_key(self, order_id: str) -> str:
        """Генерирует ключ кэша для заказа."""
        return f"order:{order_id}"
    
    # =========================================================================
    # РАСЧЁТ СТОИМОСТИ
    # =========================================================================
    
    def calculate_fare(
        self,
        distance_km: float,
        duration_minutes: int,
        surge_multiplier: float = 1.0,
    ) -> FareCalculationDTO:
        """
        Рассчитывает стоимость поездки.
        
        Args:
            distance_km: Расстояние
            duration_minutes: Время
            surge_multiplier: Коэффициент спроса
            
        Returns:
            Результат расчёта
        """
        return self._fare_calculator.calculate(distance_km, duration_minutes, surge_multiplier)
    
    # =========================================================================
    # CRUD ОПЕРАЦИИ
    # =========================================================================
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """
        Получает заказ по ID.
        
        Args:
            order_id: UUID заказа
            
        Returns:
            Заказ или None
        """
        cache_key = self._order_cache_key(order_id)
        
        # Проверяем кэш
        cached = await self._redis.get_model(cache_key, Order)
        if cached is not None:
            return cached
        
        # Читаем из БД
        order = await self._repo.get_by_id(order_id)
        
        if order is not None:
            from src.config import settings
            await self._redis.set_model(
                cache_key,
                order,
                ttl=settings.redis_ttl.ORDER_TTL,
            )
        
        return order
    
    async def get_active_order_for_passenger(self, passenger_id: int) -> Optional[Order]:
        """
        Получает активный заказ пассажира.
        
        Args:
            passenger_id: ID пассажира
            
        Returns:
            Активный заказ или None
        """
        return await self._repo.get_active_by_passenger(passenger_id)
    
    async def get_active_order_for_driver(self, driver_id: int) -> Optional[Order]:
        """
        Получает активный заказ водителя.
        
        Args:
            driver_id: ID водителя
            
        Returns:
            Активный заказ или None
        """
        return await self._repo.get_active_by_driver(driver_id)
    
    # =========================================================================
    # ЖИЗНЕННЫЙ ЦИКЛ ЗАКАЗА
    # =========================================================================
    
    async def create_order(
        self,
        dto: OrderCreateDTO,
        distance_km: float,
        duration_minutes: int,
    ) -> Optional[Order]:
        """
        Создаёт новый заказ.
        
        Args:
            dto: Данные заказа
            distance_km: Расстояние маршрута
            duration_minutes: Время маршрута
            
        Returns:
            Созданный заказ или None
        """
        try:
            # Проверяем, нет ли активного заказа
            existing = await self.get_active_order_for_passenger(dto.passenger_id)
            if existing is not None:
                await log_info(
                    f"У пассажира {dto.passenger_id} уже есть активный заказ {existing.id}",
                    type_msg=TypeMsg.WARNING,
                )
                return None
            
            # Рассчитываем стоимость
            fare = self.calculate_fare(distance_km, duration_minutes)
            
            # Создаём заказ
            order = Order(
                passenger_id=dto.passenger_id,
                pickup_address=dto.pickup_address,
                pickup_latitude=dto.pickup_latitude,
                pickup_longitude=dto.pickup_longitude,
                destination_address=dto.destination_address,
                destination_latitude=dto.destination_latitude,
                destination_longitude=dto.destination_longitude,
                distance_km=distance_km,
                duration_minutes=duration_minutes,
                estimated_fare=fare.total_fare,
                surge_multiplier=fare.surge_multiplier,
                status=OrderStatus.CREATED,
                payment_method=dto.payment_method,
                passenger_comment=dto.passenger_comment,
            )
            
            # Сохраняем в БД
            created = await self._repo.create(order)
            
            if created is not None:
                # Кэшируем
                from src.config import settings
                await self._redis.set_model(
                    self._order_cache_key(created.id),
                    created,
                    ttl=settings.redis_ttl.ORDER_TTL,
                )
                
                # Публикуем событие
                try:
                    await self._event_bus.publish(DomainEvent(
                        event_type=EventTypes.ORDER_CREATED,
                        payload={
                            "order_id": created.id,
                            "passenger_id": created.passenger_id,
                            "pickup_latitude": created.pickup_latitude,
                            "pickup_longitude": created.pickup_longitude,
                            "estimated_fare": created.estimated_fare,
                        },
                    ))
                except Exception as pub_error:
                    await log_error(f"Не удалось опубликовать ORDER_CREATED: {pub_error}")
                
                await log_info(
                    f"Заказ {created.id} создан пассажиром {created.passenger_id}",
                    type_msg=TypeMsg.INFO,
                )
            
            return created
        except Exception as e:
            await log_error(f"Ошибка создания заказа: {e}", exc_info=True)
            return None
    
    async def start_search(self, order_id: str) -> bool:
        """
        Переводит заказ в статус поиска водителя.
        
        Args:
            order_id: ID заказа
            
        Returns:
            True если успешно
        """
        success = await self._repo.update_status(order_id, OrderStatus.SEARCHING)
        
        if success:
            await self._invalidate_cache(order_id)
            await log_info(f"Заказ {order_id}: начат поиск водителя", type_msg=TypeMsg.DEBUG)
        
        return success
    
    async def accept_order(self, order_id: str, driver_id: int) -> bool:
        """
        Водитель принимает заказ.
        
        Args:
            order_id: ID заказа
            driver_id: ID водителя
            
        Returns:
            True если успешно
        """
        try:
            # Проверяем, что заказ в правильном статусе
            order = await self.get_order(order_id)
            if order is None:
                return False
            
            if order.status not in (OrderStatus.CREATED, OrderStatus.SEARCHING):
                await log_info(
                    f"Заказ {order_id} нельзя принять (статус: {order.status.value})",
                    type_msg=TypeMsg.WARNING,
                )
                return False
            
            # Назначаем водителя
            success = await self._repo.assign_driver(order_id, driver_id)
            
            if success:
                await self._invalidate_cache(order_id)
                
                # Публикуем событие
                try:
                    await self._event_bus.publish(DomainEvent(
                        event_type=EventTypes.ORDER_ACCEPTED,
                        payload={
                            "order_id": order_id,
                            "driver_id": driver_id,
                            "passenger_id": order.passenger_id,
                        },
                    ))
                except Exception as pub_error:
                    await log_error(f"Не удалось опубликовать ORDER_ACCEPTED: {pub_error}")
                
                await log_info(
                    f"Заказ {order_id} принят водителем {driver_id}",
                    type_msg=TypeMsg.INFO,
                )
            
            return success
        except Exception as e:
            await log_error(f"Ошибка принятия заказа {order_id}: {e}")
            return False
    
    async def driver_arrived(self, order_id: str) -> bool:
        """
        Водитель прибыл на место подачи.
        
        Args:
            order_id: ID заказа
            
        Returns:
            True если успешно
        """
        success = await self._repo.update_status(
            order_id,
            OrderStatus.DRIVER_ARRIVED,
            arrived_at=datetime.now(timezone.utc),
        )
        
        if success:
            await self._invalidate_cache(order_id)
            await log_info(f"Заказ {order_id}: водитель прибыл", type_msg=TypeMsg.INFO)
        
        return success
    
    async def start_ride(self, order_id: str) -> bool:
        """
        Начинает поездку.
        
        Args:
            order_id: ID заказа
            
        Returns:
            True если успешно
        """
        success = await self._repo.update_status(
            order_id,
            OrderStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
        )
        
        if success:
            await self._invalidate_cache(order_id)
            await log_info(f"Заказ {order_id}: поездка началась", type_msg=TypeMsg.INFO)
        
        return success
    
    async def complete_order(self, order_id: str, final_fare: Optional[float] = None) -> bool:
        """
        Завершает заказ.
        
        Args:
            order_id: ID заказа
            final_fare: Итоговая стоимость (если отличается от расчётной)
            
        Returns:
            True если успешно
        """
        try:
            order = await self.get_order(order_id)
            if order is None:
                return False
            
            kwargs = {
                "completed_at": datetime.now(timezone.utc),
            }
            if final_fare is not None:
                kwargs["final_fare"] = final_fare
            
            success = await self._repo.update_status(
                order_id,
                OrderStatus.COMPLETED,
                **kwargs,
            )
            
            if success:
                await self._invalidate_cache(order_id)
                
                # Публикуем событие
                try:
                    await self._event_bus.publish(DomainEvent(
                        event_type=EventTypes.ORDER_COMPLETED,
                        payload={
                            "order_id": order_id,
                            "driver_id": order.driver_id,
                            "passenger_id": order.passenger_id,
                            "fare": final_fare or order.estimated_fare,
                        },
                    ))
                except Exception as pub_error:
                    await log_error(f"Не удалось опубликовать ORDER_COMPLETED: {pub_error}")
                
                await log_info(
                    f"Заказ {order_id} завершён",
                    type_msg=TypeMsg.INFO,
                )
            
            return success
        except Exception as e:
            await log_error(f"Ошибка завершения заказа {order_id}: {e}")
            return False
    
    async def cancel_order(self, order_id: str, cancelled_by: str = "passenger") -> bool:
        """
        Отменяет заказ.
        
        Args:
            order_id: ID заказа
            cancelled_by: Кто отменил (passenger/driver/system)
            
        Returns:
            True если успешно
        """
        try:
            order = await self.get_order(order_id)
            if order is None:
                return False
            
            if not order.is_active:
                return False
            
            success = await self._repo.update_status(
                order_id,
                OrderStatus.CANCELLED,
                cancelled_at=datetime.now(timezone.utc),
            )
            
            if success:
                await self._invalidate_cache(order_id)
                
                # Публикуем событие
                try:
                    await self._event_bus.publish(DomainEvent(
                        event_type=EventTypes.ORDER_CANCELLED,
                        payload={
                            "order_id": order_id,
                            "driver_id": order.driver_id,
                            "passenger_id": order.passenger_id,
                            "cancelled_by": cancelled_by,
                        },
                    ))
                except Exception as pub_error:
                    await log_error(f"Не удалось опубликовать ORDER_CANCELLED: {pub_error}")
                
                await log_info(
                    f"Заказ {order_id} отменён ({cancelled_by})",
                    type_msg=TypeMsg.INFO,
                )
            
            return success
        except Exception as e:
            await log_error(f"Ошибка отмены заказа {order_id}: {e}")
            return False
    
    async def _invalidate_cache(self, order_id: str) -> None:
        """Инвалидирует кэш заказа."""
        await self._redis.delete(self._order_cache_key(order_id))
