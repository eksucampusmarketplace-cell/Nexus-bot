"""
Trust score: 0-100 per user per group.
Calculated from:
  - Activity score (0-40):  messages sent, days active
  - History score (0-40):   warn count, ban history, mute count (negative)
  - Engagement score (0-20): reactions given, polls voted (tracked via report_count penalty)

Score thresholds:
  0-30:  Low trust → links blocked, extra flood scrutiny
  31-60: Medium trust → normal permissions
  61-85: High trust → auto-approve some actions
  86-100: Trusted → exempt from antiflood

Recalculated:
  - On every message (increment activity)
  - On every moderation action (decrement history)
  - Every 24h: full recalculation from DB stats

Store in Supabase: users table, trust_score column
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_LOW_TRUST_THRESHOLD    = 30
_HIGH_TRUST_THRESHOLD   = 86
_RESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
)
_FULL_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False,
)


async def calculate_trust_score(user_id: int, chat_id: int, db_pool) -> int:
    """Calculate and persist trust score. Returns new score 0-100."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT message_count, warns, is_banned, is_muted, report_count
               FROM users
               WHERE user_id = $1 AND chat_id = $2""",
            user_id, chat_id
        )
        if not row:
            return 50

        message_count = row["message_count"] or 0
        warns = row["warns"]
        if isinstance(warns, str):
            try:
                warns = json.loads(warns)
            except Exception:
                warns = []
        warn_count    = len(warns) if isinstance(warns, list) else 0
        report_count  = row["report_count"] or 0
        is_banned     = row["is_banned"] or False
        is_muted      = row["is_muted"] or False

        # Activity score (0-40): 1 pt per 10 messages, capped at 40
        activity_score = min(40, message_count // 10)

        # History score (0-40): deduct 10 per warn, 5 per report
        history_score = max(0, 40 - (warn_count * 10) - (report_count * 5))
        if is_banned:
            history_score = 0
        elif is_muted:
            history_score = max(0, history_score - 10)

        # Engagement score (0-20): base 10, +2 per day active (up to 10 days bonus)
        days_active_row = await conn.fetchval(
            """SELECT COUNT(DISTINCT DATE(last_seen)) FROM users
               WHERE user_id = $1 AND chat_id = $2""",
            user_id, chat_id
        )
        days_active     = int(days_active_row or 1)
        engagement_score = min(20, 10 + min(10, (days_active - 1) * 2))

        new_score = activity_score + history_score + engagement_score
        new_score = max(0, min(100, new_score))

        old_row = await conn.fetchrow(
            "SELECT trust_score FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
        old_score = old_row["trust_score"] if old_row else 50

        await conn.execute(
            "UPDATE users SET trust_score = $1 WHERE user_id = $2 AND chat_id = $3",
            new_score, user_id, chat_id
        )

        delta = new_score - old_score
        logger.debug(
            f"[TRUST] Score updated | user_id={user_id} | chat_id={chat_id} "
            f"| old={old_score} | new={new_score} | delta={delta:+d}"
        )
        return new_score


async def get_trust_score(user_id: int, chat_id: int, db_pool) -> int:
    """Fast DB read of current score."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT trust_score FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )
    return row["trust_score"] if row else 50


async def apply_trust_consequences(
    user_id: int,
    chat_id: int,
    score: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Apply restrictions or grant privileges based on trust score.

    Low trust  (0-30)  → restrict media, stickers, forwards, web previews
    Medium trust (31-85) → no extra restriction beyond group defaults
    High trust (86-100) → ensure full permissions are restored (lift prior low-trust limits)
    """
    bot = context.bot

    try:
        if score <= _LOW_TRUST_THRESHOLD:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=_RESTRICTED_PERMISSIONS,
            )
            logger.info(
                f"[TRUST] Low-trust restriction applied | "
                f"user_id={user_id} chat_id={chat_id} score={score}"
            )
        elif score >= _HIGH_TRUST_THRESHOLD:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=_FULL_PERMISSIONS,
            )
            logger.info(
                f"[TRUST] High-trust permissions restored | "
                f"user_id={user_id} chat_id={chat_id} score={score}"
            )
    except Exception as e:
        logger.debug(
            f"[TRUST] Could not apply consequences | "
            f"user_id={user_id} chat_id={chat_id} error={e}"
        )
