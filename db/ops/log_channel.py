"""
db/ops/log_channel.py

Database operations for log channel and activity log.
"""

import json


async def get_log_channel(pool, chat_id: int):
    """Get the log channel ID for a group, or None."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT log_channel_id FROM groups WHERE chat_id=$1",
            chat_id
        )
    return row["log_channel_id"] if row else None


async def get_log_categories(pool, chat_id: int) -> dict:
    """Get log category toggles. Returns dict with defaults if not set."""
    defaults = {
        "ban": True, "mute": True, "warn": True, "kick": True,
        "delete": True, "join": False, "leave": False, "raid": True,
        "captcha": True, "filter": True, "blocklist": True,
        "settings": True, "pin": True, "report": True, "note": False,
        "schedule": False, "password": True, "import_export": True,
    }
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT log_categories FROM groups WHERE chat_id=$1",
            chat_id
        )
    if not row or not row["log_categories"]:
        return defaults
    cats = row["log_categories"]
    if isinstance(cats, str):
        try:
            cats = json.loads(cats)
        except Exception:
            cats = {}
    result = dict(defaults)
    result.update(dict(cats))
    return result


async def log_activity(
    pool,
    chat_id: int,
    bot_id: int,
    event_type: str,
    actor_id=None,
    target_id=None,
    actor_name: str = "",
    target_name: str = "",
    details: dict = None,
):
    """Insert a row into the activity_log table."""
    details = details or {}
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO activity_log
               (chat_id, bot_id, event_type, actor_id, target_id,
                actor_name, target_name, details)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)""",
            chat_id, bot_id, event_type,
            actor_id, target_id,
            actor_name or "", target_name or "",
            json.dumps(details),
        )
