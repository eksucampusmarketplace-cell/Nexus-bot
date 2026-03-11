from db.client import db
from datetime import datetime

async def add_captcha_pending(user_id: int, chat_id: int, message_id: int, expires_at: datetime):
    async with db.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO captcha_pending (user_id, chat_id, message_id, expires_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, chat_id) DO UPDATE
            SET message_id = EXCLUDED.message_id, expires_at = EXCLUDED.expires_at
        """, user_id, chat_id, message_id, expires_at)

async def get_captcha_pending(user_id: int, chat_id: int):
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM captcha_pending WHERE user_id = $1 AND chat_id = $2", user_id, chat_id)
        return dict(row) if row else None

async def remove_captcha_pending(user_id: int, chat_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM captcha_pending WHERE user_id = $1 AND chat_id = $2", user_id, chat_id)
