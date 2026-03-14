"""
bot/engagement/badges.py

Badge system — members earn badges for achievements.

Default badges:
  🌱 Newcomer       — First message in group
  💬 Chatterbox     — 100 messages sent
  🗣️ Active         — 500 messages sent
  📣 Veteran        — 1000 messages sent
  ⭐ Rising Star    — Reach level 5
  🌟 Star           — Reach level 10
  💫 Legend         — Reach level 20
  👑 Elite          — Reach level 50
  🔥 On Fire        — 7 day streak
  ♾️ Dedicated      — 30 day streak
  💎 Diamond        — 100 day streak
  👍 Helpful        — Receive 10 rep
  🏆 Respected      — Receive 50 rep
  🎮 Gamer          — Win 10 games
  🎯 Champion       — Win 50 games
  🤝 Generous       — Give 20 rep to others

Log prefix: [BADGES]
"""

import asyncio
import logging
from typing import Optional

log = logging.getLogger("badges")

CONDITION_MAP = {
    "messages": "total_messages",
    "level": "level",
    "streak": "streak_days",
    "rep_received": "rep_score",
    "rep_given": "total_given",
    "game_wins": None,
    "admin_grant": None,
    "manual": None,
}


async def seed_default_badges(pool, bot_id: int):
    from db.ops.engagement import seed_default_badges as db_seed
    await db_seed(pool, bot_id)
    log.info(f"[BADGES] Default badges seeded | bot={bot_id}")


async def check_and_award_badges(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
    trigger: str,
    value: int = None
) -> list[dict]:
    try:
        from db.ops.engagement import get_all_badges, has_badge, award_badge, get_member_xp, get_member_rep

        badges = await get_all_badges(pool, bot_id, chat_id)
        newly_earned = []

        xp_data = await get_member_xp(pool, chat_id, user_id, bot_id)
        rep_data = await get_member_rep(pool, chat_id, user_id, bot_id)

        for badge in badges:
            ctype = badge.get("condition_type")
            cval = badge.get("condition_value", 0)
            badge_id = badge["id"]

            if await has_badge(pool, chat_id, user_id, bot_id, badge_id):
                continue

            qualified = False

            if ctype == "messages" and trigger in ("message", "level_up"):
                qualified = xp_data.get("total_messages", 0) >= cval
            elif ctype == "level" and trigger == "level_up":
                qualified = (value or xp_data.get("level", 1)) >= cval
            elif ctype == "streak" and trigger == "streak":
                qualified = (value or xp_data.get("streak_days", 0)) >= cval
            elif ctype == "rep_received" and trigger == "rep_received":
                qualified = (value or rep_data.get("rep_score", 0)) >= cval
            elif ctype == "rep_given" and trigger == "rep_given":
                qualified = (value or rep_data.get("total_given", 0)) >= cval
            elif ctype == "game_wins" and trigger == "game_win":
                qualified = (value or 0) >= cval

            if qualified:
                await award_badge(pool, chat_id, user_id, bot_id, badge_id)
                newly_earned.append(badge)
                log.info(
                    f"[BADGES] Awarded '{badge['name']}' | "
                    f"chat={chat_id} user={user_id}"
                )

        return newly_earned
    except Exception as e:
        log.error(f"[BADGES] check_and_award_badges error: {e}")
        return []


async def get_member_badges(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int
) -> list[dict]:
    from db.ops.engagement import get_member_badges as db_get
    return await db_get(pool, chat_id, user_id, bot_id)


async def grant_badge_manually(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
    badge_id: int,
    granted_by: int
) -> bool:
    try:
        from db.ops.engagement import award_badge
        await award_badge(pool, chat_id, user_id, bot_id, badge_id, granted_by)
        log.info(f"[BADGES] Manual grant | chat={chat_id} user={user_id} badge={badge_id} by={granted_by}")
        return True
    except Exception as e:
        log.error(f"[BADGES] grant_badge_manually error: {e}")
        return False
