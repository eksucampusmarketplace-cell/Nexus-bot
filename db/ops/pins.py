"""
db/ops/pins.py

Database operations for pinned message tracking.
"""


async def record_pin(pool, chat_id: int, message_id: int, pinned_by: int = None):
    """Record a newly pinned message and mark others as not current."""
    async with pool.acquire() as conn:
        await conn.execute("UPDATE pinned_messages SET is_current=FALSE WHERE chat_id=$1", chat_id)
        await conn.execute(
            """INSERT INTO pinned_messages (chat_id, message_id, pinned_by, is_current)
               VALUES ($1, $2, $3, TRUE)""",
            chat_id,
            message_id,
            pinned_by,
        )


async def get_current_pin(pool, chat_id: int) -> dict | None:
    """Get the currently pinned message record."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM pinned_messages
               WHERE chat_id=$1 AND is_current=TRUE
               ORDER BY pinned_at DESC LIMIT 1""",
            chat_id,
        )
    return dict(row) if row else None


async def get_last_pin(pool, chat_id: int) -> dict | None:
    """Get the most recently pinned message (including non-current)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM pinned_messages
               WHERE chat_id=$1
               ORDER BY pinned_at DESC LIMIT 1""",
            chat_id,
        )
    return dict(row) if row else None


async def mark_unpinned(pool, chat_id: int):
    """Mark the current pin as no longer current."""
    async with pool.acquire() as conn:
        await conn.execute("UPDATE pinned_messages SET is_current=FALSE WHERE chat_id=$1", chat_id)
