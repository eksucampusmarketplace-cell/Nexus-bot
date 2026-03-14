"""
bot/handlers/xp.py

Gamification system: XP, levels, badges, and streaks.
Award XP on messages and track user progress.
"""

import json
import logging
from datetime import date
from db.client import db

logger = logging.getLogger(__name__)

# XP Configuration
XP_PER_MESSAGE = 2
XP_PER_CLEAN_DAY = 10  # No warnings that day
XP_WARN_PENALTY = 25
XP_LEVEL_MULTIPLIER = 100

# Badge definitions
BADGES = {
    "first_100": {"name": "Century", "icon": "💯", "xp": 100},
    "first_1000": {"name": "Veteran", "icon": "🏆", "xp": 1000},
    "streak_7": {"name": "Weekly", "icon": "🔥", "xp": 0, "streak": 7},
    "streak_30": {"name": "Monthly", "icon": "⚡", "xp": 0, "streak": 30},
    "level_5": {"name": "Rising", "icon": "📈", "level": 5},
    "level_10": {"name": "Elite", "icon": "👑", "level": 10},
    "level_25": {"name": "Legend", "icon": "🔱", "level": 25},
}


def xp_for_level(level: int) -> int:
    """Calculate XP required to reach a specific level."""
    return level * level * XP_LEVEL_MULTIPLIER


def level_from_xp(xp: int) -> int:
    """Calculate level from total XP."""
    if xp <= 0:
        return 1
    import math

    return int(math.sqrt(xp / XP_LEVEL_MULTIPLIER)) + 1


async def award_message_xp(user_id: int, chat_id: int) -> dict | None:
    """
    Award XP for a message. Returns level-up data if user leveled up or earned badges.

    Returns:
        dict with keys: leveled_up, level, xp, earned_badges
        or None if no significant event occurred
    """
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT xp, level, streak_days, last_active_date, badges
               FROM users WHERE user_id=$1 AND chat_id=$2""",
            user_id,
            chat_id,
        )
        if not row:
            return None

        new_xp = (row["xp"] or 0) + XP_PER_MESSAGE
        current_level = row["level"] or 1
        leveled_up = False
        new_level = current_level

        # Check for level up
        while new_xp >= xp_for_level(new_level + 1):
            new_level += 1
            leveled_up = True

        # Streak calculation
        today = date.today()
        last_active = row["last_active_date"]
        streak = row["streak_days"] or 0

        if last_active != today:
            if last_active and (today - last_active).days == 1:
                streak += 1  # Continuing streak
            else:
                streak = 1  # New streak

        # Badge checks
        badges = json.loads(row["badges"] or "[]")
        earned = []

        for badge_id, badge_data in BADGES.items():
            if badge_id in badges:
                continue

            # Check XP-based badges
            if badge_data.get("xp") and new_xp >= badge_data["xp"]:
                badges.append(badge_id)
                earned.append(badge_data)
            # Check streak-based badges
            elif badge_data.get("streak") and streak >= badge_data["streak"]:
                badges.append(badge_id)
                earned.append(badge_data)
            # Check level-based badges
            elif badge_data.get("level") and new_level >= badge_data["level"]:
                badges.append(badge_id)
                earned.append(badge_data)

        # Update database
        await conn.execute(
            """UPDATE users 
               SET xp=$1, level=$2, streak_days=$3, 
                   last_active_date=$4, badges=$5::jsonb
               WHERE user_id=$6 AND chat_id=$7""",
            new_xp,
            new_level,
            streak,
            today,
            json.dumps(badges),
            user_id,
            chat_id,
        )

        if leveled_up or earned:
            return {
                "leveled_up": leveled_up,
                "level": new_level,
                "xp": new_xp,
                "earned_badges": earned,
                "streak": streak,
            }
        return None


async def award_game_xp(user_id: int, chat_id: int, xp_amount: int) -> dict | None:
    """
    Award XP from games. Returns level-up data if applicable.
    """
    # Cap XP per game session
    xp_amount = min(xp_amount, 500)
    if xp_amount <= 0:
        return None

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xp, level FROM users WHERE user_id=$1 AND chat_id=$2", user_id, chat_id
        )
        if not row:
            return None

        new_xp = (row["xp"] or 0) + xp_amount
        current_level = row["level"] or 1
        new_level = current_level
        leveled_up = False

        while new_xp >= xp_for_level(new_level + 1):
            new_level += 1
            leveled_up = True

        await conn.execute(
            "UPDATE users SET xp=$1, level=$2 WHERE user_id=$3 AND chat_id=$4",
            new_xp,
            new_level,
            user_id,
            chat_id,
        )

        if leveled_up:
            return {"leveled_up": True, "level": new_level, "xp": new_xp}
        return None


async def get_leaderboard(chat_id: int, limit: int = 10) -> list:
    """Get XP leaderboard for a group."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT user_id, first_name, username, xp, level, badges
               FROM users 
               WHERE chat_id=$1 AND xp > 0
               ORDER BY xp DESC
               LIMIT $2""",
            chat_id,
            limit,
        )
        return [dict(row) for row in rows]


async def get_user_rank(user_id: int, chat_id: int) -> dict | None:
    """Get user's rank and stats in a group."""
    async with db.pool.acquire() as conn:
        # Get user's stats
        user_row = await conn.fetchrow(
            "SELECT xp, level, badges, streak_days FROM users WHERE user_id=$1 AND chat_id=$2",
            user_id,
            chat_id,
        )
        if not user_row:
            return None

        # Get rank
        rank = await conn.fetchval(
            """SELECT COUNT(*) + 1 FROM users 
               WHERE chat_id=$1 AND xp > $2""",
            chat_id,
            user_row["xp"] or 0,
        )

        # Get total users with XP
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE chat_id=$1 AND xp > 0", chat_id
        )

        return {
            "rank": rank,
            "total": total,
            "xp": user_row["xp"] or 0,
            "level": user_row["level"] or 1,
            "badges": json.loads(user_row["badges"] or "[]"),
            "streak_days": user_row["streak_days"] or 0,
        }
