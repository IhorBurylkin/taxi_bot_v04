import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.config import settings
from src.infra.database import get_db

async def main():
    db = get_db()
    await db.connect(
        dsn=settings.database.dsn,
        min_size=1,
        max_size=1,
    )
    
    print("Connected to DB")
    
    # Insert user 12345
    query = """
        INSERT INTO users_schema.users (id, username, first_name, last_name, 
                          phone, language, role, is_active, is_blocked,
                          created_at, updated_at)
        VALUES (12345, 'DevUser', 'Dev', 'User', '1234567890', 'ru', 'passenger', true, false, NOW(), NOW())
        ON CONFLICT (id) DO NOTHING
    """
    
    await db.execute(query)
    print("User 12345 created")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())