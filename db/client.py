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
                    settings JSONB DEFAULT '{}'::jsonb,
                    member_count INTEGER DEFAULT 0,
                    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
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

                -- Core bots table
                CREATE TABLE IF NOT EXISTS bots (
                    id BIGSERIAL PRIMARY KEY,
                    bot_id BIGINT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    token_encrypted TEXT NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    owner_user_id BIGINT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    webhook_url TEXT,
                    webhook_active BOOLEAN DEFAULT FALSE,
                    groups_count INT DEFAULT 0,
                    is_primary BOOLEAN DEFAULT FALSE,
                    added_at TIMESTAMPTZ DEFAULT NOW(),
                    last_seen TIMESTAMPTZ DEFAULT NOW(),
                    death_reason TEXT
                );

                -- Rate limiting table
                CREATE TABLE IF NOT EXISTS clone_attempts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    attempted_at TIMESTAMPTZ DEFAULT NOW(),
                    success BOOLEAN DEFAULT FALSE,
                    fail_reason TEXT,
                    token_hash TEXT
                );
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bots_owner ON bots(owner_user_id);
                CREATE INDEX IF NOT EXISTS idx_bots_status ON bots(status);
                CREATE INDEX IF NOT EXISTS idx_bots_token_hash ON bots(token_hash);
                CREATE INDEX IF NOT EXISTS idx_clone_attempts_user ON clone_attempts(user_id, attempted_at);
            """)
            logger.info("Database schema initialized")

db = Database()
