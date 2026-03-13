
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def run_migration():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set")
        return
    
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        with open('db/migrations/add_bot_custom_messages.sql', 'r') as f:
            sql = f.read()
            print("Running migration: add_bot_custom_messages.sql")
            await conn.execute(sql)
            print("Migration successful")
            
        # Also add booster_enabled to groups settings if not exist
        # We'll handle this in the code by using the settings JSONB
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())
