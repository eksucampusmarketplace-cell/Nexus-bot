import json
from db.client import db
from datetime import datetime


async def get_user(user_id: int, chat_id: int):
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1 AND chat_id = $2", user_id, chat_id
        )
        if row:
            res = dict(row)
            if isinstance(res["warns"], str):
                res["warns"] = json.loads(res["warns"])
            return res
        return None


async def upsert_user(user_id: int, chat_id: int, username: str = None, first_name: str = None):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, chat_id, username, first_name, last_seen)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, chat_id) DO UPDATE
            SET username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_seen = CURRENT_TIMESTAMP
        """,
            user_id,
            chat_id,
            username,
            first_name,
        )


async def increment_message_count(user_id: int, chat_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users SET message_count = message_count + 1, last_seen = CURRENT_TIMESTAMP
            WHERE user_id = $1 AND chat_id = $2
        """,
            user_id,
            chat_id,
        )


async def add_warn(user_id: int, chat_id: int, reason: str, by_user_id: int):
    user = await get_user(user_id, chat_id)
    warns = user["warns"] if user else []
    warns.append({"reason": reason, "by": by_user_id, "timestamp": datetime.now().isoformat()})
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET warns = $1::jsonb WHERE user_id = $2 AND chat_id = $3",
            json.dumps(warns),
            user_id,
            chat_id,
        )
    return len(warns)


async def remove_warn(user_id: int, chat_id: int):
    user = await get_user(user_id, chat_id)
    if not user or not user["warns"]:
        return 0
    warns = user["warns"]
    warns.pop()
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET warns = $1::jsonb WHERE user_id = $2 AND chat_id = $3",
            json.dumps(warns),
            user_id,
            chat_id,
        )
    return len(warns)


async def update_user_status(
    user_id: int,
    chat_id: int,
    is_muted: bool = None,
    mute_until: datetime = None,
    is_banned: bool = None,
):
    updates = []
    params = []
    if is_muted is not None:
        params.append(is_muted)
        updates.append(f"is_muted = ${len(params)}")
    if mute_until is not None:
        params.append(mute_until)
        updates.append(f"mute_until = ${len(params)}")
    if is_banned is not None:
        params.append(is_banned)
        updates.append(f"is_banned = ${len(params)}")

    if not updates:
        return

    params.extend([user_id, chat_id])
    query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ${len(params)-1} AND chat_id = ${len(params)}"
    async with db.pool.acquire() as conn:
        await conn.execute(query, *params)
