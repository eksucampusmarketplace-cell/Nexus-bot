"""
db/ops/antiraid.py
Database operations for anti-raid.
"""

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

async def record_join(db, chat_id: int, user_id: int):
    await db.execute(
        "INSERT INTO recent_joins (chat_id, user_id) VALUES ($1, $2)",
        chat_id, user_id
    )

async def count_recent_joins(db, chat_id: int, window_seconds: int = 60) -> int:
    row = await db.fetchrow(
        "SELECT COUNT(*) FROM recent_joins WHERE chat_id = $1 AND joined_at > NOW() - INTERVAL '1 second' * $2",
        chat_id, window_seconds
    )
    return row[0] if row else 0

async def create_antiraid_session(db, chat_id: int, triggered_by: str, ends_at=None, join_count: int = 0):
    row = await db.fetchrow(
        """INSERT INTO antiraid_sessions (chat_id, triggered_by, ends_at, join_count)
           VALUES ($1, $2, $3, $4) RETURNING id""",
        chat_id, triggered_by, ends_at, join_count
    )
    return row['id']

async def get_active_session(db, chat_id: int):
    return await db.fetchrow(
        "SELECT * FROM antiraid_sessions WHERE chat_id = $1 AND is_active = TRUE LIMIT 1",
        chat_id
    )

async def end_antiraid_session(db, session_id: int):
    await db.execute(
        "UPDATE antiraid_sessions SET is_active = FALSE WHERE id = $1",
        session_id
    )

async def increment_session_joins(db, session_id: int):
    await db.execute(
        "UPDATE antiraid_sessions SET join_count = join_count + 1 WHERE id = $1",
        session_id
    )

async def get_session_join_count(db, session_id: int) -> int:
    row = await db.fetchrow("SELECT join_count FROM antiraid_sessions WHERE id = $1", session_id)
    return row['join_count'] if row else 0

async def log_member_event(db, chat_id: int, user, event_type: str, meta: dict = None):
    # user can be a telegram.User or an object with id, username, full_name
    user_id = user.id
    username = getattr(user, 'username', None)
    full_name = getattr(user, 'full_name', None)
    
    import json
    await db.execute(
        """INSERT INTO member_events (chat_id, user_id, username, full_name, event_type, meta)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        chat_id, user_id, username, full_name, event_type, json.dumps(meta or {})
    )
