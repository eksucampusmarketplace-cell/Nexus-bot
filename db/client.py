import asyncpg
import logging
from config import settings

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Connect to the database with retry logic and better error messages."""
        import asyncio
        
        conn_str = settings.SUPABASE_CONNECTION_STRING
        
        # Validate connection string format
        if not conn_str or not conn_str.startswith("postgresql://"):
            raise ValueError(
                "Invalid SUPABASE_CONNECTION_STRING. "
                "It should start with 'postgresql://' and contain valid connection details. "
                "Example: postgresql://postgres:password@db.project.supabase.co:5432/postgres"
            )
        
        max_retries = 3
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                self.pool = await asyncpg.create_pool(
                    conn_str,
                    min_size=1,
                    max_size=10,
                    command_timeout=60,
                    server_settings={
                        'application_name': 'groupguard-bot'
                    }
                )
                logger.info("Successfully connected to Supabase PostgreSQL")
                # Initialize schema
                await self.init_db()
                return
            except Exception as e:
                last_error = e
                logger.warning(f"Database connection attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"Failed to connect to database after {max_retries} attempts")
        raise last_error

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

    async def init_db(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id BIGINT PRIMARY KEY,
                    title TEXT,
                    bot_token_hash TEXT,
                    settings JSONB DEFAULT '{}'::jsonb
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT,
                    chat_id BIGINT,
                    username TEXT,
                    first_name TEXT,
                    warns JSONB DEFAULT '[]'::jsonb,
                    is_muted BOOLEAN DEFAULT FALSE,
                    mute_until TIMESTAMP WITH TIME ZONE,
                    is_banned BOOLEAN DEFAULT FALSE,
                    message_count INTEGER DEFAULT 0,
                    join_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS actions_log (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT,
                    action TEXT,
                    target_user_id BIGINT,
                    target_username TEXT,
                    by_user_id BIGINT,
                    by_username TEXT,
                    reason TEXT,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    bot_token_hash TEXT
                );

                CREATE TABLE IF NOT EXISTS captcha_pending (
                    user_id BIGINT,
                    chat_id BIGINT,
                    message_id BIGINT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    PRIMARY KEY (user_id, chat_id)
                );
            """)
            logger.info("Database schema initialized")

db = Database()
