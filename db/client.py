import logging

import asyncpg

from config import settings

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.pool = None
        self.redis = None

    async def connect(self):
        """Connect to the database with retry logic and better error messages."""
        import asyncio

        conn_str = settings.SUPABASE_CONNECTION_STRING

        # Note: statement_cache_size=0 is required for Supabase/pgbouncer compatibility
        # Supabase uses pgbouncer with transaction pooling, which doesn't support
        # prepared statements properly. Setting statement_cache_size to 0 disables
        # the prepared statement cache and allows the application to work correctly.

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
                    statement_cache_size=0,
                    server_settings={"application_name": "nexus-bot"},
                )
                logger.info("Successfully connected to Supabase PostgreSQL")
                # Initialize schema
                await self.init_db()
                return
            except Exception as e:
                last_error = e
                logger.warning(f"Database connection attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)  # Exponential backoff

        logger.error(f"Failed to connect to database after {max_retries} attempts")
        raise last_error

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetchval(self, query: str, *args, column: int = 0):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args, column=column)

    async def executemany(self, query: str, args):
        async with self.pool.acquire() as conn:
            return await conn.executemany(query, args)

    async def init_db(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id BIGINT PRIMARY KEY,
                    title TEXT,
                    bot_token_hash TEXT,
                    settings JSONB DEFAULT '{}'::jsonb,
                    modules JSONB DEFAULT '{}'::jsonb,
                    text_config JSONB DEFAULT '{}'::jsonb,
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
                    trust_score INTEGER DEFAULT 50,
                    join_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id)
                );

                -- Linked channels per group
                CREATE TABLE IF NOT EXISTS linked_channels (
                    id BIGSERIAL PRIMARY KEY,
                    group_chat_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL UNIQUE,
                    channel_username TEXT,
                    channel_title TEXT,
                    bot_id BIGINT NOT NULL,
                    linked_at TIMESTAMPTZ DEFAULT NOW()
                );

                -- Scheduled and sent posts
                CREATE TABLE IF NOT EXISTS channel_posts (
                    id BIGSERIAL PRIMARY KEY,
                    bot_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    group_chat_id BIGINT NOT NULL,
                    text TEXT,
                    media_file_id TEXT,
                    media_type TEXT,       -- photo | video | animation | document
                    parse_mode TEXT DEFAULT 'HTML',
                    status TEXT DEFAULT 'scheduled',  -- scheduled | sent | failed | cancelled
                    scheduled_at TIMESTAMPTZ,
                    sent_at TIMESTAMPTZ,
                    sent_message_id BIGINT,    -- Telegram message_id of the sent post (for edit/delete)
                    fail_reason TEXT,
                    created_by BIGINT,     -- user_id of admin who created the post
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_posts_scheduled ON channel_posts(status, scheduled_at)
                  WHERE status = 'scheduled';

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
                    owner_user_id BIGINT,
                    status TEXT NOT NULL DEFAULT 'active',
                    webhook_url TEXT,
                    webhook_active BOOLEAN DEFAULT FALSE,
                    groups_count INT DEFAULT 0,
                    is_primary BOOLEAN DEFAULT FALSE,
                    added_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    last_seen TIMESTAMPTZ DEFAULT NOW(),
                    death_reason TEXT,
                    group_limit INT DEFAULT 1 CHECK (group_limit BETWEEN 1 AND 20),
                    group_access_policy TEXT DEFAULT 'blocked' CHECK (group_access_policy IN ('open','approval','blocked')),
                    bot_add_notifications BOOLEAN DEFAULT FALSE
                );

                -- Tracks every group a clone bot has been added to
                CREATE TABLE IF NOT EXISTS clone_bot_groups (
                    id              BIGSERIAL PRIMARY KEY,
                    bot_id          BIGINT NOT NULL,             -- bots.bot_id
                    chat_id         BIGINT NOT NULL,             -- Telegram group chat_id
                    chat_title      TEXT,
                    added_by        BIGINT NOT NULL,             -- user_id of who added the bot
                    added_by_name   TEXT,
                    is_owner_group  BOOLEAN DEFAULT FALSE,       -- true if added_by = clone owner
                    is_active       BOOLEAN DEFAULT TRUE,        -- false when bot is removed from group
                    access_status   TEXT DEFAULT 'pending'
                                    CHECK (access_status IN ('active','pending','denied','left')),
                    added_at        TIMESTAMPTZ DEFAULT NOW(),
                    left_at         TIMESTAMPTZ,
                    UNIQUE (bot_id, chat_id)
                );

                CREATE INDEX IF NOT EXISTS idx_clone_bot_groups_bot    ON clone_bot_groups(bot_id);
                CREATE INDEX IF NOT EXISTS idx_clone_bot_groups_chat   ON clone_bot_groups(chat_id);
                CREATE INDEX IF NOT EXISTS idx_clone_bot_groups_active ON clone_bot_groups(bot_id, is_active);

                -- Ensure columns exist in groups table
                ALTER TABLE groups ADD COLUMN IF NOT EXISTS member_count INTEGER DEFAULT 0;
                ALTER TABLE groups ADD COLUMN IF NOT EXISTS last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
                ALTER TABLE groups ADD COLUMN IF NOT EXISTS bot_token_hash TEXT;
                ALTER TABLE groups ADD COLUMN IF NOT EXISTS modules JSONB DEFAULT '{}'::jsonb;
                ALTER TABLE groups ADD COLUMN IF NOT EXISTS text_config JSONB DEFAULT '{}'::jsonb;
                ALTER TABLE groups ADD COLUMN IF NOT EXISTS photo_big TEXT;
                ALTER TABLE groups ADD COLUMN IF NOT EXISTS photo_small TEXT;

                -- Ensure columns exist in users table
                ALTER TABLE users ADD COLUMN IF NOT EXISTS trust_score INTEGER DEFAULT 50;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS message_count INTEGER DEFAULT 0;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS warns JSONB DEFAULT '[]'::jsonb;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS is_muted BOOLEAN DEFAULT FALSE;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE;

                -- Ensure columns exist in member_boost_records table
                ALTER TABLE member_boost_records ADD COLUMN IF NOT EXISTS invited_count INTEGER DEFAULT 0;
                ALTER TABLE member_boost_records ADD COLUMN IF NOT EXISTS manual_credits INTEGER DEFAULT 0;
                ALTER TABLE member_boost_records ADD COLUMN IF NOT EXISTS is_unlocked BOOLEAN DEFAULT FALSE;
                ALTER TABLE member_boost_records ADD COLUMN IF NOT EXISTS is_restricted BOOLEAN DEFAULT FALSE;
                ALTER TABLE member_boost_records ADD COLUMN IF NOT EXISTS is_exempted BOOLEAN DEFAULT FALSE;

                -- Ensure columns exist in force_channel_records table
                ALTER TABLE force_channel_records ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
                ALTER TABLE force_channel_records ADD COLUMN IF NOT EXISTS is_restricted BOOLEAN DEFAULT FALSE;

                -- Ensure columns exist in actions_log table
                ALTER TABLE actions_log ADD COLUMN IF NOT EXISTS bot_token_hash TEXT;

                -- Ensure columns exist in bots table for existing installations
                ALTER TABLE bots ADD COLUMN IF NOT EXISTS group_limit INT DEFAULT 1 CHECK (group_limit BETWEEN 1 AND 20);
                ALTER TABLE bots ADD COLUMN IF NOT EXISTS group_access_policy TEXT DEFAULT 'blocked' CHECK (group_access_policy IN ('open','approval','blocked'));
                ALTER TABLE bots ADD COLUMN IF NOT EXISTS bot_add_notifications BOOLEAN DEFAULT FALSE;
                ALTER TABLE bots ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT FALSE;
                ALTER TABLE bots ADD COLUMN IF NOT EXISTS token_hash TEXT;
                ALTER TABLE bots ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
                ALTER TABLE bots ALTER COLUMN owner_user_id DROP NOT NULL;
                
                -- Rate limiting table
                CREATE TABLE IF NOT EXISTS clone_attempts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    attempted_at TIMESTAMPTZ DEFAULT NOW(),
                    success BOOLEAN DEFAULT FALSE,
                    fail_reason TEXT,
                    token_hash TEXT
                );

                -- Member Booster tables
                CREATE TABLE IF NOT EXISTS member_boost_records (
                    id BIGSERIAL PRIMARY KEY,
                    group_id BIGINT NOT NULL REFERENCES groups(chat_id),
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    invite_link TEXT UNIQUE,
                    invite_link_name TEXT,
                    invited_count INTEGER DEFAULT 0,
                    required_count INTEGER DEFAULT 0,
                    manual_credits INTEGER DEFAULT 0,
                    is_unlocked BOOLEAN DEFAULT FALSE,
                    is_restricted BOOLEAN DEFAULT FALSE,
                    is_exempted BOOLEAN DEFAULT FALSE,
                    exempted_by BIGINT,
                    exemption_reason TEXT,
                    boost_message_id INTEGER,
                    join_source TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    unlocked_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(group_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS member_invite_events (
                    id BIGSERIAL PRIMARY KEY,
                    group_id BIGINT NOT NULL REFERENCES groups(chat_id),
                    inviter_user_id BIGINT NOT NULL,
                    invited_user_id BIGINT NOT NULL,
                    invited_username TEXT,
                    invited_first_name TEXT,
                    invite_link TEXT,
                    source TEXT DEFAULT 'link',
                    joined_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(group_id, invited_user_id)
                );

                CREATE TABLE IF NOT EXISTS manual_add_credits (
                    id BIGSERIAL PRIMARY KEY,
                    group_id BIGINT NOT NULL REFERENCES groups(chat_id),
                    claimant_user_id BIGINT NOT NULL,
                    claimant_username TEXT,
                    claimed_count INTEGER DEFAULT 1,
                    claimed_user_ids JSONB DEFAULT '[]',
                    status TEXT DEFAULT 'pending',
                    approved_count INTEGER DEFAULT 0,
                    reviewed_by BIGINT,
                    review_note TEXT,
                    admin_message_id INTEGER,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    reviewed_at TIMESTAMPTZ
                );

                CREATE TABLE IF NOT EXISTS manual_adds_detected (
                    id BIGSERIAL PRIMARY KEY,
                    group_id BIGINT NOT NULL REFERENCES groups(chat_id),
                    added_user_id BIGINT NOT NULL,
                    added_username TEXT,
                    added_first_name TEXT,
                    added_by_user_id BIGINT,
                    detected_at TIMESTAMPTZ DEFAULT NOW(),
                    credited_to BIGINT,
                    credit_id INTEGER REFERENCES manual_add_credits(id)
                );

                CREATE TABLE IF NOT EXISTS force_channel_records (
                    id BIGSERIAL PRIMARY KEY,
                    group_id BIGINT NOT NULL REFERENCES groups(chat_id),
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    channel_id BIGINT NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    is_restricted BOOLEAN DEFAULT FALSE,
                    verified_at TIMESTAMPTZ,
                    last_checked TIMESTAMPTZ,
                    notified_at TIMESTAMPTZ,
                    check_count INTEGER DEFAULT 0,
                    notify_message_id INTEGER,
                    UNIQUE(group_id, user_id)
                );
            """)

            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bots_owner ON bots(owner_user_id);
                CREATE INDEX IF NOT EXISTS idx_bots_status ON bots(status);
                CREATE INDEX IF NOT EXISTS idx_bots_token_hash ON bots(token_hash);
                CREATE INDEX IF NOT EXISTS idx_clone_attempts_user ON clone_attempts(user_id, attempted_at);
                CREATE INDEX IF NOT EXISTS idx_boost_records_group ON member_boost_records(group_id);
                CREATE INDEX IF NOT EXISTS idx_boost_records_user ON member_boost_records(user_id);
                CREATE INDEX IF NOT EXISTS idx_invite_events_group ON member_invite_events(group_id);
                CREATE INDEX IF NOT EXISTS idx_invite_events_inviter ON member_invite_events(inviter_user_id);
                CREATE INDEX IF NOT EXISTS idx_manual_adds_group ON manual_adds_detected(group_id);
                CREATE INDEX IF NOT EXISTS idx_manual_adds_detected_at ON manual_adds_detected(detected_at);
                CREATE INDEX IF NOT EXISTS idx_manual_credits_group ON manual_add_credits(group_id);
                CREATE INDEX IF NOT EXISTS idx_manual_credits_status ON manual_add_credits(status);
                CREATE INDEX IF NOT EXISTS idx_force_channel_group ON force_channel_records(group_id);
                CREATE INDEX IF NOT EXISTS idx_force_channel_user ON force_channel_records(user_id);
            """)
            logger.info("Database schema initialized")


db = Database()
