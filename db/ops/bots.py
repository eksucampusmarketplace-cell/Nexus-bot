"""
db/ops/bots.py

All database operations for the bots/cloning system.
Uses asyncpg directly for reliable async PostgreSQL access.

Every function receives an asyncpg.Pool as first argument.
The pool is created once at startup in main.py and injected everywhere.

Logging:
  - Log every query with table name, operation type, and key param
  - Log query duration for anything over 200ms
  - Never log token values — log token_hash instead
"""

import asyncpg
import logging
import time
from typing import Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


# ── Bot CRUD ──────────────────────────────────────────────────────────────────

async def get_bot_by_id(pool: asyncpg.Pool, bot_id: int) -> Optional[dict]:
    """
    Fetch single bot record by Telegram numeric bot ID.
    Returns None if not found.
    Logs: [DB][bots][SELECT] bot_id={bot_id}
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM bots WHERE bot_id = $1",
            bot_id
        )
    duration = (time.monotonic() - start) * 1000
    logger.debug(f"[DB][bots][SELECT] bot_id={bot_id} | duration={duration:.1f}ms")
    return dict(row) if row else None


async def get_bot_by_token_hash(pool: asyncpg.Pool, token_hash: str) -> Optional[dict]:
    """
    Check if a token is already registered using its hash.
    Used for deduplication — never needs the raw token.
    Logs: [DB][bots][SELECT] token_hash={token_hash[:8]}...
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM bots WHERE token_hash = $1",
            token_hash
        )
    duration = (time.monotonic() - start) * 1000
    logger.debug(f"[DB][bots][SELECT] token_hash={token_hash[:12]}... | duration={duration:.1f}ms")
    return dict(row) if row else None


async def get_bots_by_owner(pool: asyncpg.Pool, owner_user_id: int) -> list[dict]:
    """
    Return all bots owned by a user, ordered by is_primary DESC, added_at DESC.
    Primary bot always appears first in the list.
    Logs: [DB][bots][SELECT] owner={owner_user_id} → {count} rows
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bots WHERE owner_user_id = $1 ORDER BY is_primary DESC, added_at DESC",
            owner_user_id
        )
    duration = (time.monotonic() - start) * 1000
    count = len(rows)
    logger.debug(f"[DB][bots][SELECT] owner={owner_user_id} → {count} rows | duration={duration:.1f}ms")
    return [dict(r) for r in rows]


async def get_all_active_bots(pool: asyncpg.Pool) -> list[dict]:
    """
    Return all bots with status='active'.
    Called at startup to recover all clones.
    Logs: [DB][bots][SELECT] status=active → {count} rows
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bots WHERE status = 'active'"
        )
    duration = (time.monotonic() - start) * 1000
    count = len(rows)
    logger.debug(f"[DB][bots][SELECT] status=active → {count} rows | duration={duration:.1f}ms")
    return [dict(r) for r in rows]


async def get_primary_bot(pool: asyncpg.Pool) -> Optional[dict]:
    """
    Return the bot record where is_primary=true.
    Used by auth middleware to get the primary token for initData validation.
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM bots WHERE is_primary = true LIMIT 1"
        )
    duration = (time.monotonic() - start) * 1000
    logger.debug(f"[DB][bots][SELECT] is_primary=true | duration={duration:.1f}ms")
    return dict(row) if row else None


async def insert_bot(pool: asyncpg.Pool, bot_data: dict) -> dict:
    """
    Insert new bot record. bot_data must contain:
      bot_id, username, display_name, token_encrypted, token_hash,
      owner_user_id, webhook_url, is_primary (bool)
    Returns inserted row as dict.
    Logs: [DB][bots][INSERT] bot_id={bot_id} username=@{username}
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO bots (
                bot_id, username, display_name, token_encrypted, token_hash,
                owner_user_id, webhook_url, is_primary, status, webhook_active,
                group_limit, group_access_policy, bot_add_notifications
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
            """,
            bot_data["bot_id"],
            bot_data["username"],
            bot_data["display_name"],
            bot_data["token_encrypted"],
            bot_data["token_hash"],
            bot_data["owner_user_id"],
            bot_data.get("webhook_url"),
            bot_data.get("is_primary", False),
            bot_data.get("status", "active"),
            bot_data.get("webhook_active", False),
            bot_data.get("group_limit", 1),
            bot_data.get("group_access_policy", "blocked"),
            bot_data.get("bot_add_notifications", False)
        )

    logger.info(f"[DB][bots][INSERT] bot_id={bot_data['bot_id']} username=@{bot_data['username']} | duration={duration:.1f}ms")
    return dict(row)


async def update_bot_status(
    pool: asyncpg.Pool,
    bot_id: int,
    status: str,
    death_reason: str = None,
    webhook_active: bool = None
) -> None:
    """
    Update bot status. Only updates fields that are not None.
    Also updates last_seen to now().
    Logs: [DB][bots][UPDATE] bot_id={bot_id} status={status}
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        # Build dynamic update query
        updates = ["status = $2", "last_seen = NOW()"]
        params = [bot_id, status]
        param_idx = 3
        
        if death_reason is not None:
            updates.append(f"death_reason = ${param_idx}")
            params.append(death_reason)
            param_idx += 1
        
        if webhook_active is not None:
            updates.append(f"webhook_active = ${param_idx}")
            params.append(webhook_active)
            param_idx += 1
        
        query = f"UPDATE bots SET {', '.join(updates)} WHERE bot_id = $1"
        
        await conn.execute(query, *params)
    
    duration = (time.monotonic() - start) * 1000
    logger.info(f"[DB][bots][UPDATE] bot_id={bot_id} status={status} | duration={duration:.1f}ms")


async def update_bot_access_settings(
    pool: asyncpg.Pool,
    bot_id: int,
    group_limit: int = None,
    group_access_policy: str = None,
    bot_add_notifications: bool = None
) -> None:
    """
    Update bot access settings. Only updates fields that are not None.
    Logs: [DB][bots][UPDATE] access settings | bot_id={bot_id}
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        updates = []
        params = [bot_id]
        param_idx = 2
        
        if group_limit is not None:
            updates.append(f"group_limit = ${param_idx}")
            params.append(group_limit)
            param_idx += 1
            
        if group_access_policy is not None:
            updates.append(f"group_access_policy = ${param_idx}")
            params.append(group_access_policy)
            param_idx += 1
            
        if bot_add_notifications is not None:
            updates.append(f"bot_add_notifications = ${param_idx}")
            params.append(bot_add_notifications)
            param_idx += 1
            
        if not updates:
            return
            
        query = f"UPDATE bots SET {', '.join(updates)} WHERE bot_id = $1"
        await conn.execute(query, *params)
        
    duration = (time.monotonic() - start) * 1000
    logger.info(f"[DB][bots][UPDATE] access settings | bot_id={bot_id} | duration={duration:.1f}ms")


async def update_bot_last_seen(pool: asyncpg.Pool, bot_id: int) -> None:
    """
    Touch last_seen. Called in background on every webhook update.
    Fire-and-forget — never raise, just log on error.
    """
    try:
        start = time.monotonic()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE bots SET last_seen = NOW() WHERE bot_id = $1",
                bot_id
            )
        duration = (time.monotonic() - start) * 1000
        logger.debug(f"[DB][bots][UPDATE] last_seen touched | bot_id={bot_id} | duration={duration:.1f}ms")
    except Exception as e:
        logger.warning(f"[DB][bots][UPDATE] failed to touch last_seen | bot_id={bot_id} | error={e}")


async def update_bot_token(
    pool: asyncpg.Pool,
    bot_id: int,
    token_encrypted: str,
    token_hash: str
) -> None:
    """
    Update bot token for reauthentication.
    Used when a dead bot gets a new token from @BotFather.
    Logs: [DB][bots][UPDATE] token | bot_id={bot_id}
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE bots 
            SET token_encrypted = $1, token_hash = $2, status = 'active', updated_at = NOW()
            WHERE bot_id = $3
            """,
            token_encrypted, token_hash, bot_id
        )
    duration = (time.monotonic() - start) * 1000
    logger.info(f"[DB][bots][UPDATE] token | bot_id={bot_id} | duration={duration:.1f}ms")


async def update_bot_groups_count(pool: asyncpg.Pool, bot_id: int) -> None:
    """
    Count groups managed by this bot from the groups table and update groups_count.
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        # First get the token_hash for this bot
        bot = await conn.fetchrow("SELECT token_hash FROM bots WHERE bot_id = $1", bot_id)
        if not bot:
            logger.warning(f"[DB][bots] Bot not found for groups_count update | bot_id={bot_id}")
            return
        
        # Count groups for this bot using token_hash
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM groups WHERE bot_token_hash = $1",
            bot["token_hash"]
        )
        
        await conn.execute(
            "UPDATE bots SET groups_count = $1 WHERE bot_id = $2",
            count, bot_id
        )
    duration = (time.monotonic() - start) * 1000
    logger.debug(f"[DB][bots][UPDATE] groups_count={count} | bot_id={bot_id} | duration={duration:.1f}ms")


async def delete_bot(pool: asyncpg.Pool, bot_id: int) -> None:
    """
    Hard delete bot record.
    Called only after webhook is deleted and PTB app is stopped.
    Logs: [DB][bots][DELETE] bot_id={bot_id}
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM bots WHERE bot_id = $1", bot_id)
    duration = (time.monotonic() - start) * 1000
    logger.info(f"[DB][bots][DELETE] bot_id={bot_id} | duration={duration:.1f}ms")


# ── Rate limiting ─────────────────────────────────────────────────────────────

async def count_recent_clone_attempts(
    pool: asyncpg.Pool,
    user_id: int,
    window_minutes: int = 60
) -> int:
    """
    Count clone attempts by user in the last N minutes.
    Used to enforce CLONE_RATE_LIMIT before processing any token.
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM clone_attempts
            WHERE user_id = $1
            AND attempted_at > NOW() - INTERVAL '1 minute' * $2
            """,
            user_id, window_minutes
        )
    duration = (time.monotonic() - start) * 1000
    logger.debug(f"[DB][clone_attempts][SELECT] user_id={user_id} count={count} | duration={duration:.1f}ms")
    return count or 0


async def log_clone_attempt(
    pool: asyncpg.Pool,
    user_id: int,
    success: bool,
    fail_reason: str = None,
    token_hash: str = None
) -> None:
    """
    Append to clone_attempts.
    Always call this regardless of success/failure for audit trail.
    token_hash is optional — include when available for dedup analysis.
    """
    start = time.monotonic()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO clone_attempts (user_id, success, fail_reason, token_hash)
            VALUES ($1, $2, $3, $4)
            """,
            user_id, success, fail_reason, token_hash
        )
    duration = (time.monotonic() - start) * 1000
    logger.debug(f"[DB][clone_attempts][INSERT] user_id={user_id} success={success} | duration={duration:.1f}ms")
