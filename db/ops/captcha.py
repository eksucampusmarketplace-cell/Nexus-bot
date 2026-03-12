"""
db/ops/captcha.py
Database operations for CAPTCHA.
"""

import logging
from datetime import datetime, timezone
import json

log = logging.getLogger(__name__)

async def create_challenge(db, chat_id, user_id, challenge_id, mode, answer, message_id, expires_at):
    await db.execute(
        """INSERT INTO captcha_challenges (chat_id, user_id, challenge_id, mode, answer, message_id, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        chat_id, user_id, challenge_id, mode, answer, message_id, expires_at
    )

async def get_challenge_by_id(db, challenge_id):
    return await db.fetchrow(
        "SELECT * FROM captcha_challenges WHERE challenge_id = $1",
        challenge_id
    )

async def get_pending_challenge(db, chat_id, user_id):
    return await db.fetchrow(
        """SELECT * FROM captcha_challenges 
           WHERE chat_id = $1 AND user_id = $2 AND passed = FALSE AND expires_at > NOW()
           ORDER BY created_at DESC LIMIT 1""",
        chat_id, user_id
    )

async def mark_challenge_passed(db, challenge_id):
    await db.execute(
        "UPDATE captcha_challenges SET passed = TRUE WHERE challenge_id = $1",
        challenge_id
    )

async def increment_attempts(db, challenge_id):
    row = await db.fetchrow(
        "UPDATE captcha_challenges SET attempts = attempts + 1 WHERE challenge_id = $1 RETURNING attempts",
        challenge_id
    )
    return row['attempts'] if row else 0

async def log_member_event(db, chat_id, user_id, event_type, meta=None):
    # This might overlap with antiraid.log_member_event, but usually we'd have it in one place or imported.
    # To keep it simple as per instructions, I'll use the one from antiraid if needed or redefine.
    # Actually, I'll just redefine it here to avoid circular imports if any, or better yet, a central member_events op.
    # But I'll stick to the provided structure.
    
    # Let's try to get user details if possible, otherwise just id
    # In some contexts we only have user_id
    await db.execute(
        """INSERT INTO member_events (chat_id, user_id, event_type, meta)
           VALUES ($1, $2, $3, $4)""",
        chat_id, user_id, event_type, json.dumps(meta or {})
    )
