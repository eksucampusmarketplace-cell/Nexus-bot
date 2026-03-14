import logging
from datetime import datetime

from db.client import db

log = logging.getLogger("[MOD_DB]")


# Bans
async def ban_user(
    chat_id: int, user_id: int, banned_by: int, reason: str, unban_at: datetime = None
):
    query = """
    INSERT INTO bans (chat_id, user_id, banned_by, reason, unban_at, is_active)
    VALUES ($1, $2, $3, $4, $5, TRUE)
    ON CONFLICT (chat_id, user_id) DO UPDATE 
    SET banned_by = EXCLUDED.banned_by, reason = EXCLUDED.reason, unban_at = EXCLUDED.unban_at, is_active = TRUE, banned_at = NOW()
    """
    await db.execute(query, chat_id, user_id, banned_by, reason, unban_at)


async def unban_user(chat_id: int, user_id: int):
    await db.execute(
        "UPDATE bans SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2", chat_id, user_id
    )


async def get_all_bans(chat_id: int, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    return await db.fetch(
        "SELECT * FROM bans WHERE chat_id = $1 AND is_active = TRUE ORDER BY banned_at DESC LIMIT $2 OFFSET $3",
        chat_id,
        limit,
        offset,
    )


# Mutes
async def mute_user(
    chat_id: int, user_id: int, muted_by: int, reason: str, unmute_at: datetime = None
):
    query = """
    INSERT INTO mutes (chat_id, user_id, muted_by, reason, unmute_at, is_active)
    VALUES ($1, $2, $3, $4, $5, TRUE)
    ON CONFLICT (chat_id, user_id) DO UPDATE 
    SET muted_by = EXCLUDED.muted_by, reason = EXCLUDED.reason, unmute_at = EXCLUDED.unmute_at, is_active = TRUE, muted_at = NOW()
    """
    await db.execute(query, chat_id, user_id, muted_by, reason, unmute_at)


async def unmute_user(chat_id: int, user_id: int):
    await db.execute(
        "UPDATE mutes SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2", chat_id, user_id
    )


async def get_all_mutes(chat_id: int, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    return await db.fetch(
        "SELECT * FROM mutes WHERE chat_id = $1 AND is_active = TRUE ORDER BY muted_at DESC LIMIT $2 OFFSET $3",
        chat_id,
        limit,
        offset,
    )


# Warnings
async def add_warning(chat_id: int, user_id: int, issued_by: int, reason: str):
    await db.execute(
        "INSERT INTO warnings (chat_id, user_id, reason, issued_by) VALUES ($1, $2, $3, $4)",
        chat_id,
        user_id,
        reason,
        issued_by,
    )


async def get_user_warnings(chat_id: int, user_id: int):
    return await db.fetch(
        "SELECT * FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE ORDER BY issued_at DESC",
        chat_id,
        user_id,
    )


# Warn Settings
async def get_warn_settings(chat_id: int):
    row = await db.fetchrow("SELECT * FROM warn_settings WHERE chat_id = $1", chat_id)
    if not row:
        return {"max_warns": 3, "warn_action": "mute", "warn_duration": "1h", "reset_on_kick": True}
    return dict(row)


# Locks
async def get_locks(chat_id: int):
    row = await db.fetchrow("SELECT * FROM locks WHERE chat_id = $1", chat_id)
    if not row:
        return {}
    return dict(row)


# Mod log
async def add_mod_log(
    chat_id: int,
    action: str,
    target_id: int,
    target_name: str,
    admin_id: int,
    admin_name: str,
    reason: str,
    duration: str = None,
):
    query = """
    INSERT INTO mod_logs (chat_id, action, target_id, target_name, admin_id, admin_name, reason, duration)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    """
    await db.execute(
        query, chat_id, action, target_id, target_name, admin_id, admin_name, reason, duration
    )
