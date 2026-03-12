import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

"""
Trust score: 0-100 per user per group.
Calculated from:
  - Activity score (0-40):  messages sent, days active
  - History score (0-40):   warn count, ban history, mute count (negative)
  - Engagement score (0-20): reactions given, polls voted, pinned messages read

Score thresholds:
  0-30:  Low trust → extra scrutiny, links blocked
  31-60: Medium trust → normal permissions
  61-85: High trust → auto-approve some actions
  86-100: Trusted → exempt from antiflood

Recalculated:
  - On every message (increment activity)
  - On every moderation action (decrement history)
  - Every 24h: full recalculation from DB stats

Store in Supabase: users table, trust_score column
"""

async def calculate_trust_score(user_id: int, chat_id: int, db_pool) -> int:
    """Calculate and persist trust score. Returns new score 0-100."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT message_count, warns FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
        if not row:
            return 50
        
        message_count = row['message_count']
        import json
        warns = row['warns']
        if isinstance(warns, str):
            warns = json.loads(warns)
        warn_count = len(warns)

        # Activity score (0-40)
        activity_score = min(40, message_count // 10) # 1 pt for every 10 msgs, up to 40

        # History score (0-40)
        history_score = max(0, 40 - (warn_count * 10)) # -10 pts for each warn, up to 40

        # Engagement score (0-20)
        engagement_score = 10 # Default base engagement

        new_score = activity_score + history_score + engagement_score
        new_score = max(0, min(100, new_score))

        old_row = await conn.fetchrow("SELECT trust_score FROM users WHERE user_id = $1 AND chat_id = $2", user_id, chat_id)
        old_score = old_row['trust_score'] if old_row else 50

        await conn.execute(
            "UPDATE users SET trust_score = $1 WHERE user_id = $2 AND chat_id = $3",
            new_score, user_id, chat_id
        )
        
        delta = new_score - old_score
        logger.info(f"[TRUST] Score updated | user_id={user_id} | chat_id={chat_id} | old={old_score} | new={new_score} | delta={delta}")
        return new_score

async def get_trust_score(user_id: int, chat_id: int, db_pool) -> int:
    """Fast DB read of current score."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT trust_score FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
        return row['trust_score'] if row else 50

async def apply_trust_consequences(user_id: int, chat_id: int, score: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Apply restrictions or grant privileges based on score."""
    # Placeholder for logic like restricting links for score < 30
    pass
