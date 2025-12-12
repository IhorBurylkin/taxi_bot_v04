from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from src.infra.database import DatabaseManager
from src.shared.models.trip_dto import TripDTO
from src.shared.models.enums import OrderStatus

class TripRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    async def create_trip(self, trip_data: dict) -> UUID:
        """Creates a new trip and returns its ID."""
        async with self.db.pool.acquire() as connection:
            # Map legacy/DTO keys to schema columns
            # Schema: pickup_lat, pickup_lon, pickup_address, destination_lat, destination_lon, destination_address
            # DTO/Legacy might use: from_lat, from_lon, address_from, to_lat, to_lon, address_to
            
            # Prepare data for insertion
            insert_data = {}
            
            # Mapping
            if "passenger_id" in trip_data: insert_data["passenger_id"] = trip_data["passenger_id"]
            if "driver_id" in trip_data: insert_data["driver_id"] = trip_data["driver_id"]
            
            if "pickup_lat" in trip_data: insert_data["pickup_lat"] = trip_data["pickup_lat"]
            elif "from_lat" in trip_data: insert_data["pickup_lat"] = trip_data["from_lat"]
            
            if "pickup_lon" in trip_data: insert_data["pickup_lon"] = trip_data["pickup_lon"]
            elif "from_lon" in trip_data: insert_data["pickup_lon"] = trip_data["from_lon"]
            
            if "pickup_address" in trip_data: insert_data["pickup_address"] = trip_data["pickup_address"]
            elif "address_from" in trip_data: insert_data["pickup_address"] = trip_data["address_from"]
            
            if "destination_lat" in trip_data: insert_data["destination_lat"] = trip_data["destination_lat"]
            elif "to_lat" in trip_data: insert_data["destination_lat"] = trip_data["to_lat"]
            
            if "destination_lon" in trip_data: insert_data["destination_lon"] = trip_data["destination_lon"]
            elif "to_lon" in trip_data: insert_data["destination_lon"] = trip_data["to_lon"]
            
            if "destination_address" in trip_data: insert_data["destination_address"] = trip_data["destination_address"]
            elif "address_to" in trip_data: insert_data["destination_address"] = trip_data["address_to"]

            if "distance_km" in trip_data: insert_data["distance_km"] = trip_data["distance_km"]
            if "fare" in trip_data: insert_data["fare"] = trip_data["fare"]
            elif "cost" in trip_data: insert_data["fare"] = trip_data["cost"]
            elif "total_cost" in trip_data: insert_data["fare"] = trip_data["total_cost"]
            
            if "status" in trip_data: insert_data["status"] = trip_data["status"]
            else: insert_data["status"] = OrderStatus.NEW.value
            
            if "created_at" in trip_data: insert_data["created_at"] = trip_data["created_at"]
            else: insert_data["created_at"] = datetime.utcnow()

            cols = ", ".join(insert_data.keys())
            placeholders = ", ".join([f"${i+1}" for i in range(len(insert_data))])
            vals = list(insert_data.values())

            query = f'''
                INSERT INTO trips_schema.orders ({cols})
                VALUES ({placeholders})
                RETURNING id;
            '''
            
            trip_id = await connection.fetchval(query, *vals)
            return trip_id

    async def get_trip_by_id(self, trip_id: UUID) -> Optional[dict]:
        """Retrieves a trip by ID."""
        async with self.db.pool.acquire() as connection:
            query = "SELECT * FROM trips_schema.orders WHERE id = $1"
            row = await connection.fetchrow(query, trip_id)
            return dict(row) if row else None

    async def update_trip_status(self, trip_id: UUID, status: str) -> None:
        """Updates the status of a trip."""
        async with self.db.pool.acquire() as connection:
            # Determine which timestamp to update based on status
            ts_column = None
            if status == OrderStatus.DRIVER_ON_WAY.value: # heading
                ts_column = 'accepted_at' # or maybe we need heading_at? Schema has accepted_at
            elif status == OrderStatus.WAITING.value: # arrived
                ts_column = 'arrived_at'
            elif status == OrderStatus.IN_PROGRESS.value: # started
                ts_column = 'started_at'
            elif status == OrderStatus.COMPLETED.value:
                ts_column = 'completed_at'
            elif status == OrderStatus.CANCELLED.value:
                ts_column = 'cancelled_at'
            
            if ts_column:
                query = f"UPDATE trips_schema.orders SET status = $1, {ts_column} = NOW() WHERE id = $2"
            else:
                query = "UPDATE trips_schema.orders SET status = $1 WHERE id = $2"
                
            await connection.execute(query, status, trip_id)

    async def update_trip_driver(self, trip_id: UUID, driver_id: int) -> None:
        """Assigns a driver to a trip."""
        async with self.db.pool.acquire() as connection:
            query = """
                UPDATE trips_schema.orders 
                SET driver_id = $1, accepted_at = NOW() 
                WHERE id = $2
            """
            await connection.execute(query, driver_id, trip_id)

    async def get_active_trips_by_passenger(self, passenger_id: int) -> List[dict]:
        """Returns active trips for a passenger."""
        async with self.db.pool.acquire() as connection:
            query = """
                SELECT * FROM trips_schema.orders 
                WHERE passenger_id = $1 
                AND status NOT IN ('completed', 'cancelled', 'expired')
                ORDER BY created_at DESC
            """
            rows = await connection.fetch(query, passenger_id)
            return [dict(row) for row in rows]

    async def get_active_trips_by_driver(self, driver_id: int) -> List[dict]:
        """Returns active trips for a driver."""
        async with self.db.pool.acquire() as connection:
            query = """
                SELECT * FROM trips_schema.orders 
                WHERE driver_id = $1 
                AND status NOT IN ('completed', 'cancelled', 'expired')
                ORDER BY created_at DESC
            """
            rows = await connection.fetch(query, driver_id)
            return [dict(row) for row in rows]

    async def get_all_trips(self, limit: int, offset: int) -> List[dict]:
        """Retrieves all trips with pagination."""
        async with self.db.pool.acquire() as connection:
            query = """
                SELECT * FROM trips_schema.orders
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """
            rows = await connection.fetch(query, limit, offset)
            return [dict(row) for row in rows]

    async def count_trips(self) -> int:
        """Returns total number of trips."""
        async with self.db.pool.acquire() as connection:
            query = "SELECT COUNT(*) FROM trips_schema.orders"
            return await connection.fetchval(query)
