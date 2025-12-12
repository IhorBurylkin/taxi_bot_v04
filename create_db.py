import asyncio
import asyncpg
from src.config import settings

async def create_db():
    try:
        # Connect to default postgres DB to create new DB
        sys_conn = await asyncpg.connect(
            user=settings.database.DB_USER,
            password=settings.database.DB_PASSWORD,
            host=settings.database.DB_HOST,
            port=settings.database.DB_PORT,
            database='postgres'
        )
        
        # Check if db exists
        exists = await sys_conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'taxi_bot_v04'")
        if not exists:
            print("Creating database taxi_bot_v04...")
            await sys_conn.execute('CREATE DATABASE taxi_bot_v04')
            print("Database created.")
        else:
            print("Database taxi_bot_v04 already exists.")
            
        await sys_conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(create_db())
