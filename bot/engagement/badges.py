"""
bot/engagement/badges.py

Badge system — members earn badges for achievements.

Default badges (seeded at setup):
🌱 Newcomer    — First message in group
💬 Chatterbox  — 100 messages sent
🗣️ Active      — 500 messages sent
📣 Veteran     — 1000 messages sent
⭐ Rising Star — Reach level 5
🌟 Star        — Reach level 10
💫 Legend      — Reach level 20
👑 Elite       — Reach level 50
🔥 On Fire     — 7 day streak
♾️ Dedicated   — 30 day streak
💎 Diamond     — 100 day streak
👍 Helpful     — Receive 10 rep
🏆 Respected   — Receive 50 rep
🎮 Gamer       — Win 10 games
🎯 Champion    — Win 50 games
🤝 Generous    — Give 20 rep to others

Log prefix: [BADGES]
"""

import logging

log = logging.getLogger("badges")

TRIGGER_CONDITIONS = {
    "message": ["message", "messages"],
    "level_up": ["level"],
    "rep_received": ["rep_received"],
    "rep_given": ["rep_given"],
    "game_win": ["game_wins"],
    "streak": ["streak"],
}


async def seed_default_badges(pool, bot_id: int):
    """Insert default badges for a new bot if not already seeded."""
    from db.ops.engagement import seed_default_badges as db_seed
    await db_seed(pool, bot_id)
    log.info(f"[BADGES] Seeded default badges | bot={bot_id}")


async def check_and_award_badges(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
    trigger: str,
    value: int = None,
) -> list[dict]:
    """
    Check if member qualifies for any new badges.
    trigger: "message" | "level_up" | "rep_received" |
             "rep_given" | "game_win" | "streak" | "admin_grant"
    Returns list of newly earned badges.
    """
    try:
        from db.ops.engagement import (
            get_all_badges, get_member_badges, award_badge, get_member_xp,
        )

        relevant_conditions = TRIGGER_CONDITIONS.get(trigger, [])
        if not relevant_conditions and trigger != "admin_grant":
            return []

        all_badges = await get_all_badges(pool, bot_id, chat_id)
        earned_badges = await get_member_badges(pool, chat_id, user_id, bot_id)
        earned_ids = {b["badge_id"] for b in earned_badges}

        newly_earned = []
        for badge in all_badges:
            if badge["id"] in earned_ids:
                continue
            ctype = badge.get("condition_type", "")
            cvalue = badge.get("condition_value", 0)

            if ctype not in relevant_conditions:
                continue

            qualifies = False
            if value is not None and value >= cvalue:
                qualifies = True
            elif ctype in ("message", "messages"):
                mx = await get_member_xp(pool, chat_id, user_id, bot_id)
                if mx.get("total_messages", 0) >= cvalue:
                    qualifies = True

            if qualifies:
                awarded = await award_badge(pool, chat_id, user_id, bot_id, badge["id"])
                if awarded:
                    newly_earned.append(badge)
                    log.info(
                        f"[BADGES] Awarded '{badge['name']}' | "
                        f"chat={chat_id} user={user_id}"
                    )

        return newly_earned
    except Exception as e:
        log.error(f"[BADGES] check_and_award_badges error | err={e}")
        return []


async def get_member_badges(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
) -> list[dict]:
    """Get all badges earned by a member."""
    from db.ops.engagement import get_member_badges as db_get
    return await db_get(pool, chat_id, user_id, bot_id)


async def grant_badge_manually(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
    badge_id: int,
    granted_by: int,
) -> bool:
    """Admin manually awards a badge."""
    from db.ops.engagement import award_badge
    result = await award_badge(pool, chat_id, user_id, bot_id, badge_id, granted_by)
    if result:
        log.info(f"[BADGES] Manual grant | badge={badge_id} user={user_id} by={granted_by}")
    return result
