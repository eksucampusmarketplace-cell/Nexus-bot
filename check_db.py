import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def check_schema():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set")
        return

    # Note: statement_cache_size=0 is required for Supabase/pgbouncer compatibility
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        print("Checking music_queues table...")
        columns = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'music_queues'
        """)
        for col in columns:
            print(f"Column: {col['column_name']}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_schema())
