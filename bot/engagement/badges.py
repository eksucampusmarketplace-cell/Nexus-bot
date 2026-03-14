"""
bot/engagement/badges.py

Badge system — members earn badges for achievements.

Default badges (seeded at setup):
🌱 Newcomer — First message in group
💬 Chatterbox — 100 messages sent
🗣️ Active — 500 messages sent
📣 Veteran — 1000 messages sent
⭐ Rising Star — Reach level 5
🌟 Star — Reach level 10
💫 Legend — Reach level 20
👑 Elite — Reach level 50
🔥 On Fire — 7 day streak
♾️ Dedicated — 30 day streak
💎 Diamond — 100 day streak
👍 Helpful — Receive 10 rep
🏆 Respected — Receive 50 rep
🎮 Gamer — Win 10 games
🎯 Champion — Win 50 games
🤝 Generous — Give 20 rep to others

Log prefix: [BADGES]
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

log = logging.getLogger("badges")

# Default badge definitions
DEFAULT_BADGES = [
    {
        "name": "Newcomer",
        "emoji": "🌱",
        "condition_type": "first_join",
        "condition_value": 1,
        "description": "First message in group",
    },
    {
        "name": "Chatterbox",
        "emoji": "💬",
        "condition_type": "messages",
        "condition_value": 100,
        "description": "100 messages sent",
    },
    {
        "name": "Active",
        "emoji": "🗣️",
        "condition_type": "messages",
        "condition_value": 500,
        "description": "500 messages sent",
    },
    {
        "name": "Veteran",
        "emoji": "📣",
        "condition_type": "messages",
        "condition_value": 1000,
        "description": "1000 messages sent",
    },
    {
        "name": "Rising Star",
        "emoji": "⭐",
        "condition_type": "level",
        "condition_value": 5,
        "description": "Reach level 5",
    },
    {
        "name": "Star",
        "emoji": "🌟",
        "condition_type": "level",
        "condition_value": 10,
        "description": "Reach level 10",
    },
    {
        "name": "Legend",
        "emoji": "💫",
        "condition_type": "level",
        "condition_value": 20,
        "description": "Reach level 20",
    },
    {
        "name": "Elite",
        "emoji": "👑",
        "condition_type": "level",
        "condition_value": 50,
        "description": "Reach level 50",
    },
    {
        "name": "On Fire",
        "emoji": "🔥",
        "condition_type": "streak",
        "condition_value": 7,
        "description": "7 day streak",
    },
    {
        "name": "Dedicated",
        "emoji": "♾️",
        "condition_type": "streak",
        "condition_value": 30,
        "description": "30 day streak",
    },
    {
        "name": "Diamond",
        "emoji": "💎",
        "condition_type": "streak",
        "condition_value": 100,
        "description": "100 day streak",
    },
    {
        "name": "Helpful",
        "emoji": "👍",
        "condition_type": "rep",
        "condition_value": 10,
        "description": "Receive 10 rep",
    },
    {
        "name": "Respected",
        "emoji": "🏆",
        "condition_type": "rep",
        "condition_value": 50,
        "description": "Receive 50 rep",
    },
    {
        "name": "Gamer",
        "emoji": "🎮",
        "condition_type": "game_wins",
        "condition_value": 10,
        "description": "Win 10 games",
    },
    {
        "name": "Champion",
        "emoji": "🎯",
        "condition_type": "game_wins",
        "condition_value": 50,
        "description": "Win 50 games",
    },
    {
        "name": "Generous",
        "emoji": "🤝",
        "condition_type": "rep_given",
        "condition_value": 20,
        "description": "Give 20 rep to others",
    },
]


async def seed_default_badges(pool, bot_id: int, chat_id: int = None):
    """Insert default badges for a new bot if not already seeded."""
    try:
        async with pool.acquire() as conn:
            for badge in DEFAULT_BADGES:
                await conn.execute(
                    """
                    INSERT INTO badges
                        (bot_id, chat_id, name, emoji, description, condition_type, condition_value)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT DO NOTHING
                    """,
                    bot_id,
                    chat_id,
                    badge["name"],
                    badge["emoji"],
                    badge["description"],
                    badge["condition_type"],
                    badge["condition_value"],
                )

        log.info(f"[BADGES] Seeded default badges for bot {bot_id}")

    except Exception as e:
        log.error(f"[BADGES] Error seeding badges: {e}")


async def check_and_award_badges(
    pool, chat_id: int, user_id: int, bot_id: int, trigger: str, value: int = None
) -> list[dict]:
    """
    Check if member qualifies for any new badges.
    trigger: "message" | "level_up" | "rep_received" |
    "rep_given" | "game_win" | "streak" | "admin_grant"
    Returns list of newly earned badges.
    Each badge returned triggers a congratulation message.
    """
    new_badges = []

    try:
        async with pool.acquire() as conn:
            # Get all badges that match the trigger type
            badges = await conn.fetch(
                """
                SELECT * FROM badges
                WHERE bot_id=$1 AND (chat_id=$2 OR chat_id IS NULL)
                AND condition_type=$3
                """,
                bot_id,
                chat_id,
                _map_trigger_to_condition(trigger),
            )

            # Get member's current stats
            member_row = await conn.fetchrow(
                """
                SELECT * FROM member_xp
                WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
                """,
                chat_id,
                user_id,
                bot_id,
            )

            rep_row = await conn.fetchrow(
                """
                SELECT rep_score, total_given FROM member_reputation
                WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
                """,
                chat_id,
                user_id,
                bot_id,
            )

            # Get existing badges
            existing = await conn.fetch(
                """
                SELECT badge_id FROM member_badges
                WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
                """,
                chat_id,
                user_id,
                bot_id,
            )
            existing_ids = {row["badge_id"] for row in existing}

            for badge in badges:
                if badge["id"] in existing_ids:
                    continue

                # Check if condition is met
                if _check_condition(
                    badge["condition_type"], badge["condition_value"], member_row, rep_row, value
                ):
                    # Award badge
                    await conn.execute(
                        """
                        INSERT INTO member_badges
                            (chat_id, user_id, bot_id, badge_id, earned_at)
                        VALUES ($1, $2, $3, $4, NOW())
                        """,
                        chat_id,
                        user_id,
                        bot_id,
                        badge["id"],
                    )

                    new_badges.append(
                        {
                            "id": badge["id"],
                            "name": badge["name"],
                            "emoji": badge["emoji"],
                            "description": badge["description"],
                        }
                    )

                    log.info(f"[BADGES] Awarded '{badge['name']}' to user {user_id}")

        return new_badges

    except Exception as e:
        log.error(f"[BADGES] Error checking badges: {e}")
        return []


def _map_trigger_to_condition(trigger: str) -> str:
    """Map trigger type to condition_type."""
    mapping = {
        "message": "messages",
        "level_up": "level",
        "rep_received": "rep",
        "rep_given": "rep_given",
        "game_win": "game_wins",
        "streak": "streak",
        "first_join": "first_join",
    }
    return mapping.get(trigger, trigger)


def _check_condition(
    condition_type: str, condition_value: int, member_row, rep_row, trigger_value: int = None
) -> bool:
    """Check if condition is met based on member stats."""
    if condition_type == "messages":
        return (member_row and member_row["total_messages"] or 0) >= condition_value

    if condition_type == "level":
        return (member_row and member_row["level"] or 1) >= condition_value

    if condition_type == "streak":
        return (member_row and member_row["streak_days"] or 0) >= condition_value

    if condition_type == "rep":
        return (rep_row and rep_row["rep_score"] or 0) >= condition_value

    if condition_type == "rep_given":
        return (rep_row and rep_row["total_given"] or 0) >= condition_value

    if condition_type == "game_wins":
        # Game wins would be tracked separately
        return trigger_value is not None and trigger_value >= condition_value

    if condition_type == "first_join":
        return True

    return False


async def get_member_badges(pool, chat_id: int, user_id: int, bot_id: int) -> list[dict]:
    """Get all badges earned by a member."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT b.id, b.name, b.emoji, b.description, b.is_rare, mb.earned_at
                FROM member_badges mb
                JOIN badges b ON mb.badge_id = b.id
                WHERE mb.chat_id=$1 AND mb.user_id=$2 AND mb.bot_id=$3
                ORDER BY mb.earned_at DESC
                """,
                chat_id,
                user_id,
                bot_id,
            )

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "emoji": row["emoji"],
                    "description": row["description"],
                    "is_rare": row["is_rare"],
                    "earned_at": row["earned_at"].isoformat() if row["earned_at"] else None,
                }
                for row in rows
            ]

    except Exception as e:
        log.error(f"[BADGES] Error getting member badges: {e}")
        return []


async def grant_badge_manually(
    pool, chat_id: int, user_id: int, bot_id: int, badge_id: int, granted_by: int
) -> bool:
    """Admin manually awards a badge."""
    try:
        async with pool.acquire() as conn:
            # Check if badge exists
            badge = await conn.fetchrow("SELECT id FROM badges WHERE id=$1", badge_id)

            if not badge:
                return False

            # Check if already has badge
            existing = await conn.fetchrow(
                """
                SELECT id FROM member_badges
                WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3 AND badge_id=$4
                """,
                chat_id,
                user_id,
                bot_id,
                badge_id,
            )

            if existing:
                return False

            await conn.execute(
                """
                INSERT INTO member_badges
                    (chat_id, user_id, bot_id, badge_id, earned_at, granted_by)
                VALUES ($1, $2, $3, $4, NOW(), $5)
                """,
                chat_id,
                user_id,
                bot_id,
                badge_id,
                granted_by,
            )

            log.info(
                f"[BADGES] Manually granted badge {badge_id} to user {user_id} by {granted_by}"
            )
            return True

    except Exception as e:
        log.error(f"[BADGES] Error granting badge: {e}")
        return False


async def create_custom_badge(
    pool,
    bot_id: int,
    chat_id: int,
    name: str,
    emoji: str,
    description: str,
    condition_type: str,
    condition_value: int,
    is_rare: bool = False,
) -> Optional[int]:
    """Create a custom badge for a group."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO badges
                    (bot_id, chat_id, name, emoji, description,
                     condition_type, condition_value, is_rare)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                bot_id,
                chat_id,
                name,
                emoji,
                description,
                condition_type,
                condition_value,
                is_rare,
            )

            if row:
                log.info(f"[BADGES] Created custom badge '{name}' for chat {chat_id}")
                return row["id"]

    except Exception as e:
        log.error(f"[BADGES] Error creating badge: {e}")

    return None


async def get_all_badges(pool, bot_id: int, chat_id: int = None) -> list[dict]:
    """Get all badges available (global + group-specific)."""
    try:
        async with pool.acquire() as conn:
            if chat_id:
                rows = await conn.fetch(
                    """
                    SELECT b.*,
                           COUNT(mb.id) as earned_count
                    FROM badges b
                    LEFT JOIN member_badges mb ON b.id = mb.badge_id
                    WHERE b.bot_id=$1 AND (b.chat_id=$2 OR b.chat_id IS NULL)
                    GROUP BY b.id
                    ORDER BY b.condition_value, b.name
                    """,
                    bot_id,
                    chat_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT b.*,
                           COUNT(mb.id) as earned_count
                    FROM badges b
                    LEFT JOIN member_badges mb ON b.id = mb.badge_id
                    WHERE b.bot_id=$1 AND b.chat_id IS NULL
                    GROUP BY b.id
                    ORDER BY b.condition_value, b.name
                    """,
                    bot_id,
                )

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "emoji": row["emoji"],
                    "description": row["description"],
                    "condition_type": row["condition_type"],
                    "condition_value": row["condition_value"],
                    "is_rare": row["is_rare"],
                    "earned_count": row["earned_count"],
                }
                for row in rows
            ]

    except Exception as e:
        log.error(f"[BADGES] Error getting badges: {e}")
        return []
