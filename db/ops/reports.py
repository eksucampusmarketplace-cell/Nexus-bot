"""
db/ops/reports.py

Database operations for the report system.
"""

import json
from datetime import datetime, timezone


async def save_report(
    pool,
    chat_id: int,
    reporter_id: int,
    reported_id: int | None,
    message_id: int | None,
    reason: str = ""
) -> int:
    """Insert a new report and return its ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO reports
               (chat_id, reporter_id, reported_id, message_id, reason)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING id""",
            chat_id, reporter_id, reported_id, message_id, reason
        )
    return row["id"] if row else 0


async def get_open_reports(pool, chat_id: int) -> list[dict]:
    """Return all open (unresolved) reports for a group, newest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM reports
               WHERE chat_id = $1 AND status = 'open'
               ORDER BY created_at DESC""",
            chat_id
        )
    return [dict(r) for r in rows]


async def get_all_reports(pool, chat_id: int, limit: int = 50) -> list[dict]:
    """Return all reports for a group (all statuses), newest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM reports
               WHERE chat_id = $1
               ORDER BY created_at DESC
               LIMIT $2""",
            chat_id, limit
        )
    return [dict(r) for r in rows]


async def get_report(pool, report_id: int) -> dict | None:
    """Return a single report by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM reports WHERE id = $1",
            report_id
        )
    return dict(row) if row else None


async def resolve_report(
    pool,
    report_id: int,
    resolved_by: int,
    status: str = "resolved",
    note: str = ""
) -> bool:
    """Mark a report as resolved or dismissed. Returns True on success."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE reports
               SET status = $1,
                   resolved_by = $2,
                   resolved_at = $3,
                   resolution_note = $4
               WHERE id = $5 AND status = 'open'""",
            status, resolved_by,
            datetime.now(timezone.utc),
            note,
            report_id
        )
    return result == "UPDATE 1"


async def count_open_reports(pool, chat_id: int) -> int:
    """Fast count of open reports for a group."""
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT COUNT(*) FROM reports WHERE chat_id = $1 AND status = 'open'",
            chat_id
        )
    return int(val or 0)


async def increment_user_report_count(pool, chat_id: int, user_id: int) -> None:
    """Increment the report_count on the users row (best-effort)."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE users
                   SET report_count = report_count + 1
                   WHERE chat_id = $1 AND user_id = $2""",
                chat_id, user_id
            )
    except Exception:
        pass
