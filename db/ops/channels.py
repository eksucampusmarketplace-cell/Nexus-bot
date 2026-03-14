import logging
from db.client import db
import json

logger = logging.getLogger(__name__)


async def get_linked_channel(group_chat_id: int):
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM linked_channels WHERE group_chat_id = $1", group_chat_id
        )
        return dict(row) if row else None


async def link_channel(
    group_chat_id: int, channel_id: int, channel_username: str, channel_title: str, bot_id: int
):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO linked_channels (group_chat_id, channel_id, channel_username, channel_title, bot_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (channel_id) DO UPDATE
            SET group_chat_id = EXCLUDED.group_chat_id, channel_username = EXCLUDED.channel_username, channel_title = EXCLUDED.channel_title, bot_id = EXCLUDED.bot_id
        """,
            group_chat_id,
            channel_id,
            channel_username,
            channel_title,
            bot_id,
        )
        logger.info(
            f"[CHANNEL] Linked | group_chat_id={group_chat_id} | channel_id={channel_id} | @{channel_username}"
        )
        return True


async def unlink_channel(group_chat_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM linked_channels WHERE group_chat_id = $1", group_chat_id)
        return True


async def get_channel_posts(group_chat_id: int):
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM channel_posts WHERE group_chat_id = $1 ORDER BY created_at DESC",
            group_chat_id,
        )
        return [dict(row) for row in rows]
