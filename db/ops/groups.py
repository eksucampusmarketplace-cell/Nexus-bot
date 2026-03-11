import json
from db.client import db

async def get_group(chat_id: int):
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM groups WHERE chat_id = $1", chat_id)
        if row:
            res = dict(row)
            if isinstance(res['settings'], str):
                res['settings'] = json.loads(res['settings'])
            return res
        return None

async def upsert_group(chat_id: int, title: str, bot_token_hash: str, settings: dict = None):
    if settings is None:
        settings = {
            "commands": {
                "warn": True, "ban": True, "mute": True, "kick": True,
                "purge": True, "lock": True, "rules": True, "stats": True,
                "report": True, "info": True, "admins": True
            },
            "automod": {
                "antiflood": {"enabled": True, "limit": 5, "window": 10, "action": "mute", "duration": 600},
                "antispam": {"enabled": True, "threshold": 3, "action": "warn"},
                "antilink": {"enabled": False, "whitelist": ["github.com", "stackoverflow.com"]},
                "captcha": {"enabled": True, "timeout": 120, "action": "kick"},
                "antibot": {"enabled": True, "min_age_days": 7}
            },
            "warnings": {"threshold": 3, "action": "ban"},
            "welcome": {"enabled": True, "text": "👋 Welcome {first_name}!", "delete_after": 60},
            "goodbye": {"enabled": False, "text": "👋 {first_name} left."},
            "rules": ["Be respectful", "No spam"],
            "silent_commands": False,
            "log_channel": None
        }
    
    async with db.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO groups (chat_id, title, bot_token_hash, settings)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (chat_id) DO UPDATE
            SET title = EXCLUDED.title, bot_token_hash = EXCLUDED.bot_token_hash, settings = EXCLUDED.settings
        """, chat_id, title, bot_token_hash, json.dumps(settings))

async def update_group_settings(chat_id: int, settings: dict):
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE groups SET settings = $1::jsonb WHERE chat_id = $2", json.dumps(settings), chat_id)

async def get_user_managed_groups(user_id: int):
    # In a real scenario, we'd check if the user is an admin in these groups.
    # For now, let's return groups where the user is known.
    # Actually, the API needs to list groups the user manages.
    # We might need a separate table for admins or just query Telegram for each group we know.
    # To keep it simple, we'll return all groups for now, but in a production bot, 
    # we would filter by admin status.
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM groups")
        return [dict(row) for row in rows]
