import logging
from db.client import db

logger = logging.getLogger(__name__)


async def get_bot_custom_messages(bot_id: int) -> dict:
    """Get all custom messages for a bot. Returns dict of {key: body}."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT message_key, body FROM bot_custom_messages WHERE bot_id = $1", bot_id
        )
        return {row["message_key"]: row["body"] for row in rows}


async def get_bot_custom_message(bot_id: int, key: str) -> str | None:
    """Get a single custom message for a bot."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT body FROM bot_custom_messages WHERE bot_id = $1 AND message_key = $2",
            bot_id,
            key,
        )
        return row["body"] if row else None


async def set_bot_custom_message(bot_id: int, key: str, body: str, updated_by: int):
    """Set or update a custom message for a bot."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bot_custom_messages (bot_id, message_key, body, updated_by)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (bot_id, message_key)
            DO UPDATE SET body = EXCLUDED.body, updated_by = EXCLUDED.updated_by, updated_at = NOW()
            """,
            bot_id,
            key,
            body,
            updated_by,
        )


async def delete_bot_custom_message(bot_id: int, key: str):
    """Delete a custom message, reverting to default."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM bot_custom_messages WHERE bot_id = $1 AND message_key = $2", bot_id, key
        )
