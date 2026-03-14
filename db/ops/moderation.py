import logging
from datetime import datetime

from db.client import db

log = logging.getLogger("[MOD_DB]")


# ── Bans ──────────────────────────────────────────────────────────────────────

async def ban_user(
    chat_id: int, user_id: int, banned_by: int, reason: str, unban_at: datetime = None
):
    """Insert or update a ban record."""
    query = """
    INSERT INTO bans (chat_id, user_id, banned_by, reason, unban_at, is_active)
    VALUES ($1, $2, $3, $4, $5, TRUE)
    ON CONFLICT (chat_id, user_id) DO UPDATE
    SET banned_by = EXCLUDED.banned_by, reason = EXCLUDED.reason,
        unban_at = EXCLUDED.unban_at, is_active = TRUE, banned_at = NOW()
    """
    await db.execute(query, chat_id, user_id, banned_by, reason, unban_at)


async def unban_user(chat_id: int, user_id: int):
    """Mark a ban as inactive."""
    await db.execute(
        "UPDATE bans SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
        chat_id,
        user_id,
    )


async def get_active_ban(chat_id: int, user_id: int):
    """Return the active ban record or None."""
    return await db.fetchrow(
        "SELECT * FROM bans WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE",
        chat_id,
        user_id,
    )


async def get_all_bans(chat_id: int, page: int = 1, limit: int = 20):
    """Paginated list of active bans."""
    offset = (page - 1) * limit
    return await db.fetch(
        "SELECT * FROM bans WHERE chat_id = $1 AND is_active = TRUE "
        "ORDER BY banned_at DESC LIMIT $2 OFFSET $3",
        chat_id,
        limit,
        offset,
    )


async def get_expiring_bans(cutoff_time: datetime):
    """Return bans whose unban_at has passed."""
    return await db.fetch(
        "SELECT chat_id, user_id FROM bans WHERE is_active = TRUE AND unban_at IS NOT NULL AND unban_at < $1",
        cutoff_time,
    )


# ── Mutes ─────────────────────────────────────────────────────────────────────

async def mute_user(
    chat_id: int, user_id: int, muted_by: int, reason: str, unmute_at: datetime = None
):
    """Insert or update a mute record."""
    query = """
    INSERT INTO mutes (chat_id, user_id, muted_by, reason, unmute_at, is_active)
    VALUES ($1, $2, $3, $4, $5, TRUE)
    ON CONFLICT (chat_id, user_id) DO UPDATE
    SET muted_by = EXCLUDED.muted_by, reason = EXCLUDED.reason,
        unmute_at = EXCLUDED.unmute_at, is_active = TRUE, muted_at = NOW()
    """
    await db.execute(query, chat_id, user_id, muted_by, reason, unmute_at)


async def unmute_user(chat_id: int, user_id: int):
    """Mark a mute as inactive."""
    await db.execute(
        "UPDATE mutes SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
        chat_id,
        user_id,
    )


async def get_active_mute(chat_id: int, user_id: int):
    """Return the active mute record or None."""
    return await db.fetchrow(
        "SELECT * FROM mutes WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE",
        chat_id,
        user_id,
    )


async def get_all_mutes(chat_id: int, page: int = 1, limit: int = 20):
    """Paginated list of active mutes."""
    offset = (page - 1) * limit
    return await db.fetch(
        "SELECT * FROM mutes WHERE chat_id = $1 AND is_active = TRUE "
        "ORDER BY muted_at DESC LIMIT $2 OFFSET $3",
        chat_id,
        limit,
        offset,
    )


async def get_expiring_mutes(cutoff_time: datetime):
    """Return mutes whose unmute_at has passed."""
    return await db.fetch(
        "SELECT chat_id, user_id FROM mutes WHERE is_active = TRUE AND unmute_at IS NOT NULL AND unmute_at < $1",
        cutoff_time,
    )


# ── Warnings ──────────────────────────────────────────────────────────────────

async def add_warning(
    chat_id: int, user_id: int, issued_by: int, reason: str, expires_at: datetime = None
):
    """Insert a new warning."""
    await db.execute(
        "INSERT INTO warnings (chat_id, user_id, reason, issued_by, expires_at) "
        "VALUES ($1, $2, $3, $4, $5)",
        chat_id,
        user_id,
        reason,
        issued_by,
        expires_at,
    )


async def remove_warning(warning_id: int):
    """Deactivate a specific warning by ID."""
    await db.execute(
        "UPDATE warnings SET is_active = FALSE WHERE id = $1", warning_id
    )


async def reset_warnings(chat_id: int, user_id: int):
    """Deactivate all warnings for a user in a chat."""
    await db.execute(
        "UPDATE warnings SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
        chat_id,
        user_id,
    )


async def get_user_warnings(chat_id: int, user_id: int):
    """Return all active warnings for a user."""
    return await db.fetch(
        "SELECT * FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE "
        "ORDER BY issued_at DESC",
        chat_id,
        user_id,
    )


async def get_active_warn_count(chat_id: int, user_id: int) -> int:
    """Count active warnings for a user."""
    val = await db.fetchval(
        "SELECT COUNT(*) FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE",
        chat_id,
        user_id,
    )
    return val or 0


async def get_all_warnings(chat_id: int, page: int = 1, limit: int = 20):
    """Paginated list of all active warnings in a chat."""
    offset = (page - 1) * limit
    return await db.fetch(
        "SELECT * FROM warnings WHERE chat_id = $1 AND is_active = TRUE "
        "ORDER BY issued_at DESC LIMIT $2 OFFSET $3",
        chat_id,
        limit,
        offset,
    )


# ── Warn Settings ─────────────────────────────────────────────────────────────

async def get_warn_settings(chat_id: int) -> dict:
    """Return warn settings for a chat, with defaults."""
    row = await db.fetchrow("SELECT * FROM warn_settings WHERE chat_id = $1", chat_id)
    if not row:
        return {
            "max_warns": 3,
            "warn_action": "mute",
            "warn_duration": "1h",
            "reset_on_kick": True,
        }
    return dict(row)


async def set_warn_settings(
    chat_id: int, max_warns: int, action: str, duration: str, reset_on_kick: bool
):
    """Upsert warn settings for a chat."""
    await db.execute(
        "INSERT INTO warn_settings (chat_id, max_warns, warn_action, warn_duration, reset_on_kick) "
        "VALUES ($1, $2, $3, $4, $5) "
        "ON CONFLICT (chat_id) DO UPDATE SET max_warns=EXCLUDED.max_warns, "
        "warn_action=EXCLUDED.warn_action, warn_duration=EXCLUDED.warn_duration, "
        "reset_on_kick=EXCLUDED.reset_on_kick",
        chat_id,
        max_warns,
        action,
        duration,
        reset_on_kick,
    )


# ── Locks ─────────────────────────────────────────────────────────────────────

async def get_locks(chat_id: int) -> dict:
    """Return lock state for a chat."""
    row = await db.fetchrow("SELECT * FROM locks WHERE chat_id = $1", chat_id)
    if not row:
        return {}
    return dict(row)


async def set_locks(chat_id: int, **lock_updates):
    """Update lock state for a chat."""
    if not lock_updates:
        return
    columns = ", ".join(lock_updates.keys())
    placeholders = ", ".join([f"${i+2}" for i in range(len(lock_updates))])
    values = list(lock_updates.values())
    update_clause = ", ".join([f"{k}=EXCLUDED.{k}" for k in lock_updates.keys()])
    query = (
        f"INSERT INTO locks (chat_id, {columns}) VALUES ($1, {placeholders}) "
        f"ON CONFLICT (chat_id) DO UPDATE SET {update_clause}"
    )
    await db.execute(query, chat_id, *values)

    if db.redis:
        await db.redis.delete(f"nexus:locks:{chat_id}")


# ── Filters ───────────────────────────────────────────────────────────────────

async def add_filter(chat_id: int, keyword: str, response: str, added_by: int):
    """Add or update a keyword filter."""
    await db.execute(
        "INSERT INTO filters (chat_id, keyword, response, added_by) VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (chat_id, keyword) DO UPDATE SET response=EXCLUDED.response",
        chat_id,
        keyword.lower(),
        response,
        added_by,
    )
    if db.redis:
        await db.redis.delete(f"nexus:filters:{chat_id}")


async def remove_filter(chat_id: int, keyword: str):
    """Remove a filter by keyword."""
    await db.execute(
        "DELETE FROM filters WHERE chat_id = $1 AND keyword = $2", chat_id, keyword.lower()
    )
    if db.redis:
        await db.redis.delete(f"nexus:filters:{chat_id}")


async def get_filters(chat_id: int):
    """Return all filters for a chat."""
    return await db.fetch(
        "SELECT * FROM filters WHERE chat_id = $1 ORDER BY keyword", chat_id
    )


async def get_all_filters_cached(chat_id: int):
    """Return filters from Redis cache or DB."""
    if db.redis:
        import json
        cached = await db.redis.get(f"nexus:filters:{chat_id}")
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

    rows = await db.fetch(
        "SELECT keyword, response FROM filters WHERE chat_id = $1", chat_id
    )
    result = [dict(r) for r in rows]
    if db.redis and result:
        import json
        await db.redis.setex(f"nexus:filters:{chat_id}", 600, json.dumps(result))
    return result


# ── Blacklist ─────────────────────────────────────────────────────────────────

async def add_blacklist(chat_id: int, word: str, action: str, added_by: int):
    """Add or update a blacklist entry."""
    await db.execute(
        "INSERT INTO blacklist (chat_id, word, action, added_by) VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (chat_id, word) DO UPDATE SET action=EXCLUDED.action",
        chat_id,
        word.lower(),
        action,
        added_by,
    )
    if db.redis:
        await db.redis.delete(f"nexus:blacklist:{chat_id}")


async def remove_blacklist(chat_id: int, word: str):
    """Remove a blacklist entry."""
    await db.execute(
        "DELETE FROM blacklist WHERE chat_id = $1 AND word = $2", chat_id, word.lower()
    )
    if db.redis:
        await db.redis.delete(f"nexus:blacklist:{chat_id}")


async def get_blacklist(chat_id: int):
    """Return all blacklisted words for a chat."""
    return await db.fetch(
        "SELECT word, action FROM blacklist WHERE chat_id = $1 ORDER BY word", chat_id
    )


async def set_blacklist_mode(chat_id: int, mode: str):
    """Update action for all blacklist entries in a chat."""
    await db.execute("UPDATE blacklist SET action = $1 WHERE chat_id = $2", mode, chat_id)
    if db.redis:
        await db.redis.delete(f"nexus:blacklist:{chat_id}")


# ── Rules ─────────────────────────────────────────────────────────────────────

async def get_rules(chat_id: int):
    """Return rules text or None."""
    row = await db.fetchrow("SELECT rules_text FROM group_rules WHERE chat_id = $1", chat_id)
    return row["rules_text"] if row else None


async def set_rules(chat_id: int, rules_text: str, updated_by: int):
    """Upsert group rules."""
    await db.execute(
        "INSERT INTO group_rules (chat_id, rules_text, updated_by) VALUES ($1, $2, $3) "
        "ON CONFLICT (chat_id) DO UPDATE SET rules_text=EXCLUDED.rules_text, "
        "updated_by=EXCLUDED.updated_by, updated_at=NOW()",
        chat_id,
        rules_text,
        updated_by,
    )


# ── Mod Log ───────────────────────────────────────────────────────────────────

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
    """Insert a mod log entry."""
    query = """
    INSERT INTO mod_logs (chat_id, action, target_id, target_name, admin_id, admin_name, reason, duration)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    """
    await db.execute(
        query, chat_id, action, target_id, target_name, admin_id, admin_name, reason, duration
    )


async def get_mod_log(
    chat_id: int,
    page: int = 1,
    limit: int = 20,
    action_type: str = None,
    admin_id: int = None,
    target_id: int = None,
):
    """Return paginated mod log entries with optional filters."""
    offset = (page - 1) * limit
    conditions = ["chat_id = $1"]
    params = [chat_id]
    idx = 2

    if action_type:
        conditions.append(f"action = ${idx}")
        params.append(action_type)
        idx += 1

    if admin_id:
        conditions.append(f"admin_id = ${idx}")
        params.append(admin_id)
        idx += 1

    if target_id:
        conditions.append(f"target_id = ${idx}")
        params.append(target_id)
        idx += 1

    where = " AND ".join(conditions)
    query = (
        f"SELECT * FROM mod_logs WHERE {where} ORDER BY done_at DESC "
        f"LIMIT ${idx} OFFSET ${idx+1}"
    )
    params.extend([limit, offset])
    return await db.fetch(query, *params)


# ── Admin Titles ──────────────────────────────────────────────────────────────

async def set_admin_title(chat_id: int, user_id: int, title: str, set_by: int):
    """Upsert an admin title."""
    await db.execute(
        "INSERT INTO admin_titles (chat_id, user_id, title, set_by) VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (chat_id, user_id) DO UPDATE SET title=EXCLUDED.title, set_by=EXCLUDED.set_by",
        chat_id,
        user_id,
        title,
        set_by,
    )


async def get_admin_title(chat_id: int, user_id: int):
    """Return custom title for an admin or None."""
    row = await db.fetchrow(
        "SELECT title FROM admin_titles WHERE chat_id = $1 AND user_id = $2", chat_id, user_id
    )
    return row["title"] if row else None


async def get_all_admin_titles(chat_id: int) -> dict:
    """Return dict of {user_id: title} for all admins in a chat."""
    rows = await db.fetch(
        "SELECT user_id, title FROM admin_titles WHERE chat_id = $1", chat_id
    )
    return {row["user_id"]: row["title"] for row in rows}


# ── Member Mod Summary ────────────────────────────────────────────────────────

async def get_member_mod_summary(chat_id: int, user_id: int) -> dict:
    """Return combined moderation summary for a member."""
    warn_settings = await get_warn_settings(chat_id)
    max_warns = warn_settings.get("max_warns", 3)

    warn_count = await get_active_warn_count(chat_id, user_id)
    active_mute = await get_active_mute(chat_id, user_id)
    active_ban = await get_active_ban(chat_id, user_id)

    recent = await db.fetch(
        "SELECT action, done_at, reason FROM mod_logs "
        "WHERE chat_id = $1 AND target_id = $2 ORDER BY done_at DESC LIMIT 5",
        chat_id,
        user_id,
    )

    return {
        "warn_count": warn_count,
        "max_warns": max_warns,
        "is_muted": active_mute is not None,
        "is_banned": active_ban is not None,
        "mute_data": dict(active_mute) if active_mute else None,
        "ban_data": dict(active_ban) if active_ban else None,
        "recent_actions": [dict(r) for r in recent],
    }
