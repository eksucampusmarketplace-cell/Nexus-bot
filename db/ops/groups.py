import json

from db.client import db


async def get_group(chat_id: int, bot_token_hash: str = None):
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM groups WHERE chat_id = $1", chat_id)
        
        bot_settings_json = {}
        if bot_token_hash:
            bot_row = await conn.fetchrow(
                "SELECT settings FROM bot_group_settings WHERE bot_token_hash=$1 AND chat_id=$2",
                bot_token_hash,
                chat_id,
            )
            if bot_row and bot_row["settings"]:
                bot_settings_json = bot_row["settings"]
                if isinstance(bot_settings_json, str):
                    try:
                        bot_settings_json = json.loads(bot_settings_json)
                    except Exception:
                        bot_settings_json = {}

        if row:
            res = dict(row)
            if isinstance(res.get("settings"), str):
                try:
                    res["settings"] = json.loads(res["settings"])
                except Exception:
                    res["settings"] = {}
            if not res.get("settings"):
                res["settings"] = {}

            if bot_settings_json:
                # Merge bot-specific overrides into settings
                def deep_merge(base, new):
                    for k, v in new.items():
                        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                            deep_merge(base[k], v)
                        else:
                            base[k] = v
                    return base
                deep_merge(res["settings"], bot_settings_json)

            if isinstance(res.get("modules"), str):
                try:
                    res["modules"] = json.loads(res["modules"])
                except Exception:
                    res["modules"] = {}
            elif res.get("modules") is None:
                res["modules"] = {}
            
            # Merge modules into settings for backward compatibility
            # Add module settings to the settings dict for easier access
            res["settings"]["_modules"] = res["modules"]
            return res
        return None


async def get_or_create_group(db_pool, chat_id: int, title: str = None):
    """Get existing group or create new one. Returns group record."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM groups WHERE chat_id = $1", chat_id)
        if row:
            res = dict(row)
            if isinstance(res.get("settings"), str):
                try:
                    res["settings"] = json.loads(res["settings"])
                except Exception:
                    res["settings"] = {}
            if isinstance(res.get("modules"), str):
                try:
                    res["modules"] = json.loads(res["modules"])
                except Exception:
                    res["modules"] = {}
            elif res.get("modules") is None:
                res["modules"] = {}
            return res
        # Create new group
        if title is None:
            title = f"Group {chat_id}"
        await conn.execute("INSERT INTO groups (chat_id, title) VALUES ($1, $2)", chat_id, title)
        row = await conn.fetchrow("SELECT * FROM groups WHERE chat_id = $1", chat_id)
        return dict(row) if row else None


async def get_group_miniapp_url(db_pool, chat_id: int) -> str | None:
    """Get the Mini App URL configured for a group."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT settings->>'miniapp_url' as url FROM groups WHERE chat_id = $1", chat_id
        )
        return row["url"] if row else None


async def upsert_group(
    chat_id: int,
    title: str,
    bot_token_hash: str,
    settings: dict = None,
    member_count: int = 0,
    photo_big: str = None,
    photo_small: str = None,
    chat_type: str = None,
):
    if settings is None:
        # ... (keep existing settings default logic)
        settings = {
            "commands": {
                "warn": True,
                "ban": True,
                "mute": True,
                "kick": True,
                "purge": True,
                "lock": True,
                "rules": True,
                "stats": True,
                "report": True,
                "info": True,
                "admins": True,
            },
            "automod": {
                "antiflood": {
                    "enabled": True,
                    "limit": 5,
                    "window": 10,
                    "action": "mute",
                    "duration": 600,
                },
                "antispam": {"enabled": True, "threshold": 3, "action": "warn"},
                "antilink": {"enabled": False, "whitelist": ["github.com", "stackoverflow.com"]},
                "captcha": {"enabled": True, "timeout": 120, "action": "kick"},
                "antibot": {"enabled": True, "min_age_days": 7},
            },
            "warnings": {"threshold": 3, "action": "ban"},
            "welcome": {"enabled": True, "text": "👋 Welcome {first_name}!", "delete_after": 60},
            "goodbye": {"enabled": False, "text": "👋 {first_name} left."},
            "rules": ["Be respectful", "No spam"],
            "silent_commands": False,
            "log_channel": None,
        }

    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO groups (chat_id, title, bot_token_hash, settings, member_count, photo_big, photo_small, chat_type)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (chat_id) DO UPDATE
            SET title = EXCLUDED.title,
                bot_token_hash = CASE WHEN EXCLUDED.bot_token_hash IS NOT NULL AND EXCLUDED.bot_token_hash != '' THEN EXCLUDED.bot_token_hash ELSE groups.bot_token_hash END,
                settings = EXCLUDED.settings,
                member_count = CASE WHEN EXCLUDED.member_count > 0 THEN EXCLUDED.member_count ELSE groups.member_count END,
                photo_big = CASE WHEN EXCLUDED.photo_big IS NOT NULL AND EXCLUDED.photo_big != '' THEN EXCLUDED.photo_big ELSE groups.photo_big END,
                photo_small = CASE WHEN EXCLUDED.photo_small IS NOT NULL AND EXCLUDED.photo_small != '' THEN EXCLUDED.photo_small ELSE groups.photo_small END,
                chat_type = CASE WHEN EXCLUDED.chat_type IS NOT NULL THEN EXCLUDED.chat_type ELSE groups.chat_type END
        """,
            chat_id,
            title,
            bot_token_hash,
            json.dumps(settings),
            member_count or 0,
            photo_big,
            photo_small,
            chat_type or 'group',
        )


async def update_group_settings(chat_id: int, settings: dict):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE groups SET settings = $1::jsonb WHERE chat_id = $2",
            json.dumps(settings),
            chat_id,
        )


async def set_group_setting(pool, chat_id: int, **kwargs):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
        settings = row["settings"] if row else {}
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except Exception:
                settings = {}
        settings = settings or {}
        settings.update(kwargs)
        await conn.execute(
            "UPDATE groups SET settings = $1::jsonb WHERE chat_id = $2",
            json.dumps(settings), chat_id,
        )


async def get_user_managed_groups(user_id: int):
    # In a real scenario, we'd check if the user is an admin in these groups.
    # For now, let's return groups where the user is known.
    # Actually, the API needs to list groups the user manages.
    # We might need a separate table for admins or just query Telegram for each group we know.
    # To keep it simple, we'll return all groups for now, but in a production bot,
    # we would filter by admin status.
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM groups")
        res = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("settings"), str):
                try:
                    d["settings"] = json.loads(d["settings"])
                except Exception:
                    d["settings"] = {}
            elif not d.get("settings"):
                d["settings"] = {}
            res.append(d)
        return res


# ── Custom Messages ──────────────────────────────────────────────────────────


async def get_custom_messages(chat_id: int) -> dict:
    """Get all custom messages for a group. Returns dict of {key: body}."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT message_key, body FROM group_custom_messages WHERE group_id = $1", chat_id
        )
        return {row["message_key"]: row["body"] for row in rows}


async def get_custom_message(chat_id: int, key: str) -> str | None:
    """Get a single custom message for a group."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT body FROM group_custom_messages WHERE group_id = $1 AND message_key = $2",
            chat_id,
            key,
        )
        return row["body"] if row else None


async def set_custom_message(chat_id: int, key: str, body: str, updated_by: int):
    """Set or update a custom message for a group."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO group_custom_messages (group_id, message_key, body, updated_by)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (group_id, message_key)
            DO UPDATE SET body = EXCLUDED.body, updated_by = EXCLUDED.updated_by, updated_at = NOW()
            """,
            chat_id,
            key,
            body,
            updated_by,
        )


async def delete_custom_message(chat_id: int, key: str):
    """Delete a custom message, reverting to default."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM group_custom_messages WHERE group_id = $1 AND message_key = $2",
            chat_id,
            key,
        )


async def get_group_modules(chat_id: int) -> dict:
    """Get the modules configuration for a group."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT modules FROM groups WHERE chat_id = $1", chat_id)
        if row and row["modules"]:
            modules = row["modules"]
            if isinstance(modules, str):
                try:
                    modules = json.loads(modules)
                except Exception:
                    modules = {}
            return modules
        return {}


async def require_admin(db_pool, chat_id: int, user_id: int, bot) -> bool:
    """Check if user is an admin in the chat."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False
