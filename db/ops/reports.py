"""
db/ops/reports.py

Database operations for the report system.
"""


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
