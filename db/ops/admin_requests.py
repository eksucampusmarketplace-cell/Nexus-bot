"""
db/ops/admin_requests.py

Database operations for the admin request system (@admins mentions).
"""

from datetime import datetime, timezone
from typing import Optional


async def create_admin_request(
    pool,
    chat_id: int,
    user_id: int,
    message_id: int,
    message_text: str,
    reply_to_msg_id: Optional[int] = None
) -> int:
    """Create a new admin request and return its ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO admin_requests
               (chat_id, user_id, message_id, message_text, reply_to_msg_id)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING id""",
            chat_id, user_id, message_id, message_text[:4000], reply_to_msg_id  # Truncate to 4000 chars
        )
    return row["id"] if row else 0


async def get_open_requests(pool, chat_id: int, limit: int = 50) -> list[dict]:
    """Get all open admin requests for a group, newest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM admin_requests
               WHERE chat_id = $1 AND status = 'open'
               ORDER BY created_at DESC
               LIMIT $2""",
            chat_id, limit
        )
    return [dict(r) for r in rows]


async def get_request(pool, request_id: int) -> Optional[dict]:
    """Get a single admin request by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM admin_requests WHERE id = $1",
            request_id
        )
    return dict(row) if row else None


async def update_request_status(
    pool,
    request_id: int,
    status: str,
    responded_by: Optional[int] = None,
    response_text: Optional[str] = None
) -> bool:
    """Update request status and optionally add response info."""
    async with pool.acquire() as conn:
        if status == "closed":
            result = await conn.execute(
                """UPDATE admin_requests
                   SET status = $1,
                       responded_by = $2,
                       response_text = $3,
                       responded_at = $4
                   WHERE id = $5""",
                status, responded_by, response_text[:2000] if response_text else None,
                datetime.now(timezone.utc), request_id
            )
        else:
            result = await conn.execute(
                """UPDATE admin_requests
                   SET status = $1
                   WHERE id = $2""",
                status, request_id
            )
    return result == "UPDATE 1"


async def get_user_recent_request_count(
    pool,
    chat_id: int,
    user_id: int,
    period_seconds: int = 3600
) -> int:
    """Count user's requests in the last period_seconds."""
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            """SELECT COUNT(*) FROM admin_requests
               WHERE chat_id = $1
               AND user_id = $2
               AND created_at > NOW() - INTERVAL '1 second' * $3""",
            chat_id, user_id, period_seconds
        )
    return int(count or 0)


async def increment_user_request_count(pool, chat_id: int, user_id: int) -> None:
    """Increment the user's admin_request_count."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE users
                   SET admin_request_count = admin_request_count + 1,
                       last_admin_request_at = NOW()
                   WHERE chat_id = $1 AND user_id = $2""",
                chat_id, user_id
            )
    except Exception:
        pass


async def get_group_request_stats(pool, chat_id: int) -> dict:
    """Get statistics about admin requests for a group."""
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM admin_requests WHERE chat_id = $1",
            chat_id
        )
        open_count = await conn.fetchval(
            "SELECT COUNT(*) FROM admin_requests WHERE chat_id = $1 AND status = 'open'",
            chat_id
        )
        closed_count = await conn.fetchval(
            "SELECT COUNT(*) FROM admin_requests WHERE chat_id = $1 AND status = 'closed'",
            chat_id
        )
        # Average response time (in minutes) for closed requests
        avg_response = await conn.fetchval(
            """SELECT AVG(EXTRACT(EPOCH FROM (responded_at - created_at)) / 60)
               FROM admin_requests
               WHERE chat_id = $1 AND status = 'closed' AND responded_at IS NOT NULL""",
            chat_id
        )
    return {
        "total": int(total or 0),
        "open": int(open_count or 0),
        "closed": int(closed_count or 0),
        "avg_response_minutes": round(float(avg_response or 0), 2)
    }


async def cleanup_old_requests(pool, days: int = 30) -> int:
    """Delete closed requests older than specified days. Returns count deleted."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            """DELETE FROM admin_requests
               WHERE status = 'closed'
               AND responded_at < NOW() - INTERVAL '1 day' * $1""",
            days
        )
    return int(result.split()[-1] or 0)


async def get_group_setting(pool, chat_id: int, setting: str) -> any:
    """Get a specific group setting for admin requests."""
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            f"SELECT {setting} FROM groups WHERE chat_id = $1",
            chat_id
        )
    return value


async def set_group_setting(pool, chat_id: int, setting: str, value: any) -> bool:
    """Set a specific group setting for admin requests."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE groups SET {setting} = $1 WHERE chat_id = $2",
                value, chat_id
            )
        return True
    except Exception:
        return False
