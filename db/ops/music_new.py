"""
Database operations for music streaming system
Handles userbot accounts, queues, sessions, and settings
"""

import logging
from typing import Optional, List, Dict
import asyncpg

logger = logging.getLogger(__name__)


async def create_music_tables(pool: asyncpg.Pool):
    """Create music streaming tables if they don't exist"""
    async with pool.acquire() as conn:
        # Schema migration check: 
        # The old music system used a different music_queues table without bot_id.
        # If we detect it, we drop it to let the new schema be created.
        try:
            # Check if music_queues exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'music_queues'
                )
            """)
            
            if table_exists:
                # Check for bot_id column
                has_bot_id = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'music_queues' AND column_name = 'bot_id'
                    )
                """)
                
                if not has_bot_id:
                    logger.info("[MUSIC_DB] Old music_queues schema detected. Dropping for migration.")
                    # Drop old tables that might conflict
                    await conn.execute("DROP TABLE IF EXISTS music_queues CASCADE")
                    await conn.execute("DROP TABLE IF EXISTS music_sessions CASCADE")
                    await conn.execute("DROP TABLE IF EXISTS music_settings CASCADE")
        except Exception as e:
            logger.warning(f"[MUSIC_DB] Migration check failed: {e}")

        # Read SQL from migrations file
        with open("db/migrations/add_music.sql", "r") as f:
            sql = f.read()

        # Execute all statements
        await conn.execute(sql)

        logger.info("[MUSIC_DB] Tables created successfully")


async def save_music_userbot(
    pool: asyncpg.Pool,
    owner_bot_id: int,
    tg_user_id: int,
    tg_name: str,
    tg_username: str,
    encrypted_session: str,
    phone: Optional[str] = None
) -> Dict:
    """Save or update a music userbot account"""
    async with pool.acquire() as conn:
        # Check if already exists
        existing = await conn.fetchrow(
            "SELECT id FROM music_userbots WHERE owner_bot_id=$1 AND tg_user_id=$2",
            owner_bot_id, tg_user_id
        )

        if existing:
            row = await conn.fetchrow(
                """
                UPDATE music_userbots
                SET session_string=$1, tg_name=$2, tg_username=$3, phone=$4,
                    is_active=TRUE, last_used_at=NOW()
                WHERE owner_bot_id=$5 AND tg_user_id=$6
                RETURNING *
                """,
                encrypted_session, tg_name, tg_username, phone,
                owner_bot_id, tg_user_id
            )
            logger.info(f"[MUSIC_DB] Updated userbot | owner={owner_bot_id} user={tg_user_id}")
        else:
            row = await conn.fetchrow(
                """
                INSERT INTO music_userbots
                (owner_bot_id, tg_user_id, tg_name, tg_username, session_string, phone)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                owner_bot_id, tg_user_id, tg_name, tg_username, encrypted_session, phone
            )
            logger.info(f"[MUSIC_DB] Saved userbot | owner={owner_bot_id} user={tg_user_id}")

        return dict(row)


async def get_music_userbots(
    pool: asyncpg.Pool,
    owner_bot_id: int,
    active_only: bool = True
) -> List[Dict]:
    """Get all userbot accounts for a bot owner"""
    async with pool.acquire() as conn:
        if active_only:
            rows = await conn.fetch(
                "SELECT * FROM music_userbots WHERE owner_bot_id=$1 AND is_active=TRUE ORDER BY added_at DESC",
                owner_bot_id
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM music_userbots WHERE owner_bot_id=$1 ORDER BY added_at DESC",
                owner_bot_id
            )
        return [dict(row) for row in rows]


async def get_music_userbot_by_id(
    pool: asyncpg.Pool,
    owner_bot_id: int,
    userbot_id: int
) -> Optional[Dict]:
    """Get a specific userbot by ID"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM music_userbots WHERE owner_bot_id=$1 AND id=$2",
            owner_bot_id, userbot_id
        )
        return dict(row) if row else None


async def update_userbot_risk_fee(
    pool: asyncpg.Pool,
    owner_bot_id: int,
    userbot_id: int,
    risk_fee: int
) -> Dict:
    """Update risk fee for a userbot"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE music_userbots
            SET risk_fee=$1
            WHERE owner_bot_id=$2 AND id=$3
            RETURNING *
            """,
            risk_fee, owner_bot_id, userbot_id
        )
        return dict(row) if row else None


async def ban_userbot(
    pool: asyncpg.Pool,
    owner_bot_id: int,
    userbot_id: int,
    ban_reason: str = None
) -> Dict:
    """Ban a userbot (for risk fee non-payment)"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE music_userbots
            SET is_banned=TRUE, ban_reason=$1, is_active=FALSE
            WHERE owner_bot_id=$2 AND id=$3
            RETURNING *
            """,
            ban_reason, owner_bot_id, userbot_id
        )
        return dict(row) if row else None


async def unban_userbot(
    pool: asyncpg.Pool,
    owner_bot_id: int,
    userbot_id: int
) -> Dict:
    """Unban a userbot"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE music_userbots
            SET is_banned=FALSE, ban_reason=NULL, is_active=TRUE
            WHERE owner_bot_id=$2 AND id=$3
            RETURNING *
            """,
            owner_bot_id, userbot_id
        )
        return dict(row) if row else None


async def delete_music_userbot(pool: asyncpg.Pool, owner_bot_id: int, userbot_id: int = None):
    """Delete userbot account(s) for a bot owner. If userbot_id is provided, delete that specific one."""
    async with pool.acquire() as conn:
        if userbot_id:
            result = await conn.execute(
                "DELETE FROM music_userbots WHERE owner_bot_id=$1 AND id=$2",
                owner_bot_id, userbot_id
            )
            logger.info(f"[MUSIC_DB] Deleted userbot | owner={owner_bot_id} id={userbot_id}")
        else:
            result = await conn.execute(
                "DELETE FROM music_userbots WHERE owner_bot_id=$1",
                owner_bot_id
            )
            logger.info(f"[MUSIC_DB] Deleted all userbots | owner={owner_bot_id}")


async def get_owner_clones(pool: asyncpg.Pool, owner_user_id: int) -> List[Dict]:
    """Get all clone bots owned by a user"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT bot_id, username, display_name
            FROM bots
            WHERE owner_user_id=$1 AND is_primary=FALSE AND status='active'
            ORDER BY created_at DESC
            """,
            owner_user_id
        )
        return [dict(row) for row in rows]


async def get_music_settings(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int
) -> Optional[Dict]:
    """Get music settings for a chat"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM music_settings WHERE chat_id=$1 AND bot_id=$2",
            chat_id, bot_id
        )
        return dict(row) if row else None


async def upsert_music_settings(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int,
    play_mode: str = "all",
    announce_tracks: bool = True,
    dj_role_id: Optional[int] = None,
    userbot_id: Optional[int] = None
) -> Dict:
    """Create or update music settings for a chat"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO music_settings (chat_id, bot_id, play_mode, announce_tracks, dj_role_id, userbot_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (chat_id, bot_id) DO UPDATE
            SET play_mode=EXCLUDED.play_mode,
                announce_tracks=EXCLUDED.announce_tracks,
                dj_role_id=EXCLUDED.dj_role_id,
                userbot_id=EXCLUDED.userbot_id
            RETURNING *
            """,
            chat_id, bot_id, play_mode, announce_tracks, dj_role_id, userbot_id
        )
        return dict(row)


async def can_user_play(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int,
    user_id: int,
    bot
) -> bool:
    """Check if a user is allowed to use music commands in a chat"""
    # Get music settings
    settings = await get_music_settings(pool, chat_id, bot_id)
    if not settings:
        # Default: everyone can play
        return True

    play_mode = settings.get("play_mode", "all")
    if play_mode == "all":
        return True

    if play_mode == "admins":
        # Check if user is admin
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            return member.status in ("administrator", "creator")
        except Exception:
            return False

    return True


async def save_queue_entry(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int,
    position: int,
    url: str,
    title: str,
    duration: int,
    thumbnail: str,
    source: str,
    requested_by: int,
    requested_by_name: str
) -> Dict:
    """Save a queue entry to the database"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO music_queues
            (chat_id, bot_id, position, url, title, duration, thumbnail, source, requested_by, requested_by_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            chat_id, bot_id, position, url, title, duration, thumbnail, source,
            requested_by, requested_by_name
        )
        return dict(row)


async def get_queue_entries(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int,
    played: bool = False
) -> List[Dict]:
    """Get all queue entries for a chat"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM music_queues WHERE chat_id=$1 AND bot_id=$2 AND played=$3 ORDER BY position",
            chat_id, bot_id, played
        )
        return [dict(row) for row in rows]


async def clear_queue_entries(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int
):
    """Mark all queue entries as played"""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE music_queues SET played=TRUE WHERE chat_id=$1 AND bot_id=$2",
            chat_id, bot_id
        )


async def get_session_state(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int
) -> Optional[Dict]:
    """Get playback session state for a chat"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM music_sessions WHERE chat_id=$1 AND bot_id=$2",
            chat_id, bot_id
        )
        return dict(row) if row else None


async def update_session_state(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int,
    is_playing: bool = None,
    is_paused: bool = None,
    is_looping: bool = None,
    volume: int = None,
    current_track_id: int = None,
    np_message_id: int = None
) -> Dict:
    """Update playback session state"""
    async with pool.acquire() as conn:
        # Build update clause dynamically
        updates = []
        params = [chat_id, bot_id]
        param_idx = 3

        if is_playing is not None:
            updates.append(f"is_playing=${param_idx}")
            params.append(is_playing)
            param_idx += 1

        if is_paused is not None:
            updates.append(f"is_paused=${param_idx}")
            params.append(is_paused)
            param_idx += 1

        if is_looping is not None:
            updates.append(f"is_looping=${param_idx}")
            params.append(is_looping)
            param_idx += 1

        if volume is not None:
            updates.append(f"volume=${param_idx}")
            params.append(volume)
            param_idx += 1

        if current_track_id is not None:
            updates.append(f"current_track=${param_idx}")
            params.append(current_track_id)
            param_idx += 1

        if np_message_id is not None:
            updates.append(f"np_message_id=${param_idx}")
            params.append(np_message_id)
            param_idx += 1

        updates.append("updated_at=NOW()")

        row = await conn.fetchrow(
            f"""
            INSERT INTO music_sessions (chat_id, bot_id)
            VALUES ($1, $2)
            ON CONFLICT (chat_id, bot_id) DO UPDATE
            SET {', '.join(updates)}
            RETURNING *
            """,
            *params
        )
        return dict(row)


async def delete_session_state(
    pool: asyncpg.Pool,
    chat_id: int,
    bot_id: int
):
    """Delete playback session state"""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM music_sessions WHERE chat_id=$1 AND bot_id=$2",
            chat_id, bot_id
        )
