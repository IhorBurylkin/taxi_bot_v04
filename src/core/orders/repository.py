# src/core/orders/repository.py
"""
Репозиторий для работы с заказами в БД.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.common.constants import OrderStatus, PaymentMethod, PaymentStatus
from src.common.logger import log_error, log_info
from src.common.constants import TypeMsg
from src.core.orders.models import Order, OrderCreateDTO
from src.infra.database import DatabaseManager


class OrderRepository:
    """Репозиторий заказов."""
    
    def __init__(self, db: DatabaseManager) -> None:
        """
        Инициализация репозитория.
        
        Args:
            db: Менеджер базы данных (Dependency Injection)
        """
        self._db = db
    
    async def get_by_id(self, order_id: str) -> Optional[Order]:
        """
        Получает заказ по ID.
        
        Args:
            order_id: UUID заказа
            
        Returns:
            Заказ или None
        """
        try:
            row = await self._db.fetchrow(
                """
                SELECT id, passenger_id, driver_id,
                       pickup_address, pickup_latitude, pickup_longitude,
                       destination_address, destination_latitude, destination_longitude,
                       distance_km, duration_minutes, estimated_fare, final_fare,
                       surge_multiplier, status, payment_method, payment_status,
                       created_at, accepted_at, arrived_at, started_at, completed_at, cancelled_at,
                       passenger_comment, driver_rating, passenger_rating
                FROM orders
                WHERE id = $1
                """,
                order_id,
            )
            
            if row is None:
                return None
            
            return self._row_to_order(row)
        except Exception as e:
            await log_error(f"Ошибка получения заказа {order_id}: {e}")
            return None
    
    async def get_active_by_passenger(self, passenger_id: int) -> Optional[Order]:
        """
        Получает активный заказ пассажира.
        
        Args:
            passenger_id: ID пассажира
            
        Returns:
            Активный заказ или None
        """
        try:
            row = await self._db.fetchrow(
                """
                SELECT id, passenger_id, driver_id,
                       pickup_address, pickup_latitude, pickup_longitude,
                       destination_address, destination_latitude, destination_longitude,
                       distance_km, duration_minutes, estimated_fare, final_fare,
                       surge_multiplier, status, payment_method, payment_status,
                       created_at, accepted_at, arrived_at, started_at, completed_at, cancelled_at,
                       passenger_comment, driver_rating, passenger_rating
                FROM orders
                WHERE passenger_id = $1
                  AND status IN ($2, $3, $4, $5, $6)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                passenger_id,
                OrderStatus.CREATED.value,
                OrderStatus.SEARCHING.value,
                OrderStatus.ACCEPTED.value,
                OrderStatus.DRIVER_ARRIVED.value,
                OrderStatus.IN_PROGRESS.value,
            )
            
            if row is None:
                return None
            
            return self._row_to_order(row)
        except Exception as e:
            await log_error(f"Ошибка получения активного заказа пассажира {passenger_id}: {e}")
            return None
    
    async def get_active_by_driver(self, driver_id: int) -> Optional[Order]:
        """
        Получает активный заказ водителя.
        
        Args:
            driver_id: ID водителя
            
        Returns:
            Активный заказ или None
        """
        try:
            row = await self._db.fetchrow(
                """
                SELECT id, passenger_id, driver_id,
                       pickup_address, pickup_latitude, pickup_longitude,
                       destination_address, destination_latitude, destination_longitude,
                       distance_km, duration_minutes, estimated_fare, final_fare,
                       surge_multiplier, status, payment_method, payment_status,
                       created_at, accepted_at, arrived_at, started_at, completed_at, cancelled_at,
                       passenger_comment, driver_rating, passenger_rating
                FROM orders
                WHERE driver_id = $1
                  AND status IN ($2, $3, $4)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                driver_id,
                OrderStatus.ACCEPTED.value,
                OrderStatus.DRIVER_ARRIVED.value,
                OrderStatus.IN_PROGRESS.value,
            )
            
            if row is None:
                return None
            
            return self._row_to_order(row)
        except Exception as e:
            await log_error(f"Ошибка получения активного заказа водителя {driver_id}: {e}")
            return None
    
    async def create(self, order: Order) -> Optional[Order]:
        """
        Создаёт новый заказ.
        
        Args:
            order: Данные заказа
            
        Returns:
            Созданный заказ или None
        """
        try:
            await self._db.execute(
                """
                INSERT INTO orders (
                    id, passenger_id, driver_id,
                    pickup_address, pickup_latitude, pickup_longitude,
                    destination_address, destination_latitude, destination_longitude,
                    distance_km, duration_minutes, estimated_fare, final_fare,
                    surge_multiplier, status, payment_method, payment_status,
                    created_at, accepted_at, arrived_at, started_at, completed_at, cancelled_at,
                    passenger_comment, driver_rating, passenger_rating
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26
                )
                """,
                order.id,
                order.passenger_id,
                order.driver_id,
                order.pickup_address,
                order.pickup_latitude,
                order.pickup_longitude,
                order.destination_address,
                order.destination_latitude,
                order.destination_longitude,
                order.distance_km,
                order.duration_minutes,
                order.estimated_fare,
                order.final_fare,
                order.surge_multiplier,
                order.status.value,
                order.payment_method.value,
                order.payment_status.value,
                order.created_at,
                order.accepted_at,
                order.arrived_at,
                order.started_at,
                order.completed_at,
                order.cancelled_at,
                order.passenger_comment,
                order.driver_rating,
                order.passenger_rating,
            )
            
            await log_info(f"Заказ {order.id} создан", type_msg=TypeMsg.DEBUG)
            
            return order
        except Exception as e:
            await log_error(f"Ошибка создания заказа: {e}")
            return None
    
    async def update_status(
        self,
        order_id: str,
        status: OrderStatus,
        **kwargs,
    ) -> bool:
        """
        Обновляет статус заказа.
        
        Args:
            order_id: ID заказа
            status: Новый статус
            **kwargs: Дополнительные поля для обновления
            
        Returns:
            True если успешно
        """
        try:
            # Формируем динамический SQL для дополнительных полей
            set_clauses = ["status = $2"]
            params = [order_id, status.value]
            param_idx = 3
            
            for key, value in kwargs.items():
                if value is not None:
                    set_clauses.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
            
            query = f"""
                UPDATE orders
                SET {", ".join(set_clauses)}
                WHERE id = $1
            """
            
            await self._db.execute(query, *params)
            
            await log_info(f"Статус заказа {order_id} обновлён на {status.value}", type_msg=TypeMsg.DEBUG)
            
            return True
        except Exception as e:
            await log_error(f"Ошибка обновления статуса заказа {order_id}: {e}")
            return False
    
    async def assign_driver(self, order_id: str, driver_id: int) -> bool:
        """
        Назначает водителя на заказ.
        
        Args:
            order_id: ID заказа
            driver_id: ID водителя
            
        Returns:
            True если успешно
        """
        try:
            await self._db.execute(
                """
                UPDATE orders
                SET driver_id = $2, status = $3, accepted_at = $4
                WHERE id = $1
                """,
                order_id,
                driver_id,
                OrderStatus.ACCEPTED.value,
                datetime.now(timezone.utc),
            )
            
            return True
        except Exception as e:
            await log_error(f"Ошибка назначения водителя на заказ {order_id}: {e}")
            return False
    
    async def get_orders_by_status(
        self,
        status: OrderStatus,
        limit: int = 100,
    ) -> list[Order]:
        """
        Получает заказы по статусу.
        
        Args:
            status: Статус заказа
            limit: Максимальное количество
            
        Returns:
            Список заказов
        """
        try:
            rows = await self._db.fetch(
                """
                SELECT id, passenger_id, driver_id,
                       pickup_address, pickup_latitude, pickup_longitude,
                       destination_address, destination_latitude, destination_longitude,
                       distance_km, duration_minutes, estimated_fare, final_fare,
                       surge_multiplier, status, payment_method, payment_status,
                       created_at, accepted_at, arrived_at, started_at, completed_at, cancelled_at,
                       passenger_comment, driver_rating, passenger_rating
                FROM orders
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                status.value,
                limit,
            )
            
            return [self._row_to_order(row) for row in rows]
        except Exception as e:
            await log_error(f"Ошибка получения заказов со статусом {status.value}: {e}")
            return []
    
    def _row_to_order(self, row) -> Order:
        """Конвертирует строку БД в модель Order."""
        return Order(
            id=row["id"],
            passenger_id=row["passenger_id"],
            driver_id=row["driver_id"],
            pickup_address=row["pickup_address"],
            pickup_latitude=row["pickup_latitude"],
            pickup_longitude=row["pickup_longitude"],
            destination_address=row["destination_address"],
            destination_latitude=row["destination_latitude"],
            destination_longitude=row["destination_longitude"],
            distance_km=row["distance_km"],
            duration_minutes=row["duration_minutes"],
            estimated_fare=row["estimated_fare"],
            final_fare=row["final_fare"],
            surge_multiplier=row["surge_multiplier"],
            status=OrderStatus(row["status"]),
            payment_method=PaymentMethod(row["payment_method"]),
            payment_status=PaymentStatus(row["payment_status"]),
            created_at=row["created_at"],
            accepted_at=row["accepted_at"],
            arrived_at=row["arrived_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            cancelled_at=row["cancelled_at"],
            passenger_comment=row["passenger_comment"],
            driver_rating=row["driver_rating"],
            passenger_rating=row["passenger_rating"],
        )
