"""
db/ops/scheduler.py

Database operations for the scheduler engine.
"""

from datetime import datetime, timezone


async def get_due_messages(pool) -> list:
    """Fetch all scheduled messages that are due to be sent."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM scheduled_messages
               WHERE is_active = TRUE
               AND next_send_at <= $1
               ORDER BY next_send_at ASC""",
            datetime.now(timezone.utc),
        )
    return [dict(r) for r in rows]


async def mark_sent(pool, msg_id: int, new_count: int, next_send_at: datetime):
    """Update send count, last_sent_at, and next_send_at after a send."""
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE scheduled_messages
               SET send_count=$1, last_sent_at=$2, next_send_at=$3
               WHERE id=$4""",
            new_count,
            datetime.now(timezone.utc),
            next_send_at,
            msg_id,
        )


async def deactivate_message(pool, msg_id: int):
    """Deactivate a scheduled message (max sends reached or manual)."""
    async with pool.acquire() as conn:
        await conn.execute("UPDATE scheduled_messages SET is_active=FALSE WHERE id=$1", msg_id)


async def get_active_silent_times(pool) -> list:
    """Fetch all active silent time slots across all groups."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""SELECT chat_id, slot, start_time, end_time, start_text, end_text
               FROM silent_times
               WHERE is_active = TRUE""")
    return [dict(r) for r in rows]
