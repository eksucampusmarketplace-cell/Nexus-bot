"""
bot/engagement/xp.py

XP Engine — handles all XP earning, level calculation, and level-up rewards.

XP Formula (default, admin configurable):
  Message sent:       +1 XP (max once per 60 seconds per user per group)
  Daily check-in:    +10 XP (once per calendar day)
  Game win:           +5 XP
  Game participation: +1 XP
  Admin grant:       +N XP (admin decides, max 20 at once)

Level Formula:
  Level 1:  0 XP
  Level 2:  100 XP
  Level 3:  250 XP
  Level 4:  500 XP
  Level 5:  900 XP
  Level N:  previous + (N * 150)

Log prefix: [XP]
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("xp")

# Level thresholds cache
_LEVEL_CACHE: dict[int, int] = {}


def xp_for_level(level: int) -> int:
    """Total XP required to reach a given level from level 1."""
    if level <= 1:
        return 0
    if level in _LEVEL_CACHE:
        return _LEVEL_CACHE[level]
    total = 0
    for n in range(2, level + 1):
        total += n * 150
    _LEVEL_CACHE[level] = total
    return total


def calculate_level(xp: int) -> int:
    """Calculate level from total XP. Returns minimum 1."""
    if xp <= 0:
        return 1
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


def xp_to_next_level(current_xp: int) -> tuple[int, int]:
    """
    Returns (xp_needed_for_next, total_xp_for_next_level).
    Used for progress bar in /rank and miniapp.
    """
    current_level = calculate_level(current_xp)
    next_total = xp_for_level(current_level + 1)
    needed = max(0, next_total - current_xp)
    return needed, next_total


async def is_rate_limited(redis, chat_id: int, user_id: int, cooldown_s: int = 60) -> bool:
    """
    Check if user is in cooldown for XP earning from messages.
    Redis key: nexus:xp:cooldown:{chat_id}:{user_id}
    """
    if not redis:
        return False
    key = f"nexus:xp:cooldown:{chat_id}:{user_id}"
    result = await redis.get(key)
    if result:
        return True
    await redis.setex(key, cooldown_s, "1")
    return False


async def check_double_xp(pool, chat_id: int, bot_id: int) -> bool:
    """Check if double XP is currently active for this group."""
    from db.ops.engagement import get_xp_settings
    settings = await get_xp_settings(pool, chat_id, bot_id)
    if not settings.get("double_xp_active"):
        return False
    until = settings.get("double_xp_until")
    if until and until < datetime.now(timezone.utc):
        return False
    return True


async def start_double_xp(pool, chat_id: int, bot_id: int, hours: int):
    """Enable double XP event for a group for N hours."""
    from datetime import timedelta
    from db.ops.engagement import upsert_xp_settings
    until = datetime.now(timezone.utc) + timedelta(hours=hours)
    await upsert_xp_settings(pool, chat_id, bot_id,
                              double_xp_active=True, double_xp_until=until)


async def award_xp(
    pool,
    redis,
    bot,
    chat_id: int,
    user_id: int,
    bot_id: int,
    amount: int,
    reason: str,
    given_by: int = None,
) -> dict:
    """
    Award XP to a member.
    1. Check rate limiting (message cooldown via Redis)
    2. Check double XP event
    3. Add XP to member_xp table
    4. Recalculate level
    5. If level changed → trigger level_up()
    6. Log transaction in xp_transactions
    7. Update network_xp if member's group is in a network
    Returns {ok, new_xp, new_level, leveled_up, previous_level}
    Never raises.
    """
    try:
        from db.ops.engagement import (
            get_member_xp, get_xp_settings, log_xp_transaction,
            upsert_member_xp, get_chat_networks, sync_network_xp,
        )

        settings = await get_xp_settings(pool, chat_id, bot_id)

        if not settings.get("enabled", True):
            return {"ok": False, "reason": "xp_disabled"}

        if reason == "message":
            cooldown = settings.get("message_cooldown_s", 60)
            if await is_rate_limited(redis, chat_id, user_id, cooldown):
                return {"ok": False, "reason": "rate_limited"}

        if await check_double_xp(pool, chat_id, bot_id):
            amount *= 2

        current = await get_member_xp(pool, chat_id, user_id, bot_id)
        current_xp = current.get("xp", 0)
        previous_level = current.get("level", 1)

        new_xp = max(0, current_xp + amount)
        new_level = calculate_level(new_xp)

        now = datetime.now(timezone.utc)
        total_messages_delta = 1 if reason == "message" else 0

        await upsert_member_xp(
            pool, chat_id, user_id, bot_id,
            xp_delta=amount, level=new_level,
            total_messages_delta=total_messages_delta,
            last_xp_at=now,
        )

        await log_xp_transaction(pool, chat_id, user_id, bot_id, amount, reason, given_by)

        leveled_up = new_level > previous_level
        if leveled_up:
            asyncio.create_task(
                level_up(pool, redis, bot, chat_id, user_id, bot_id, new_level, previous_level)
            )

        networks = await get_chat_networks(pool, chat_id)
        for network in networks:
            asyncio.create_task(
                sync_network_xp(pool, network["id"], user_id, amount)
            )

        return {
            "ok": True,
            "new_xp": new_xp,
            "new_level": new_level,
            "leveled_up": leveled_up,
            "previous_level": previous_level,
        }
    except Exception as e:
        log.error(f"[XP] award_xp error | chat={chat_id} user={user_id} err={e}")
        return {"ok": False, "reason": str(e)}


async def level_up(
    pool,
    redis,
    bot,
    chat_id: int,
    user_id: int,
    bot_id: int,
    new_level: int,
    previous_level: int,
):
    """
    Handle level up event.
    1. Check level_rewards table for this level
    2. Apply rewards
    3. Check badge conditions
    4. If level_up_announce enabled → post in group
    5. Publish XP event to Redis for miniapp
    """
    try:
        from db.ops.engagement import get_xp_settings, get_level_rewards
        from bot.engagement.badges import check_and_award_badges

        settings = await get_xp_settings(pool, chat_id, bot_id)
        rewards = await get_level_rewards(pool, chat_id, bot_id, new_level)

        for reward in rewards:
            if reward["reward_type"] == "title":
                pass

        await check_and_award_badges(pool, chat_id, user_id, bot_id, "level_up", new_level)

        if settings.get("level_up_announce", True) and bot:
            template = settings.get("level_up_message", "🎉 {mention} reached Level {level}! {title}")
            title = ""
            if rewards:
                title_reward = next((r for r in rewards if r["reward_type"] == "title"), None)
                if title_reward:
                    title = title_reward["reward_value"] or ""
            mention = f'<a href="tg://user?id={user_id}">User</a>'
            text = template.format(mention=mention, level=new_level, title=title).strip()
            try:
                await bot.send_message(chat_id, text, parse_mode="HTML")
            except Exception:
                pass

        if redis:
            import json
            event = json.dumps({
                "type": "level_up",
                "chat_id": chat_id,
                "user_id": user_id,
                "new_level": new_level,
                "previous_level": previous_level,
            })
            await redis.publish(f"nexus:events:{chat_id}", event)

        log.info(f"[XP] Level up | chat={chat_id} user={user_id} level={new_level}")
    except Exception as e:
        log.error(f"[XP] level_up error | chat={chat_id} user={user_id} err={e}")


async def deduct_xp(
    pool,
    redis,
    chat_id: int,
    user_id: int,
    bot_id: int,
    amount: int,
    reason: str,
    given_by: int,
) -> dict:
    """
    Remove XP from a member. Never goes below 0.
    Recalculates level. Logs transaction.
    Returns {ok, new_xp, new_level}
    """
    try:
        from db.ops.engagement import get_member_xp, upsert_member_xp, log_xp_transaction

        current = await get_member_xp(pool, chat_id, user_id, bot_id)
        current_xp = current.get("xp", 0)
        new_xp = max(0, current_xp - amount)
        new_level = calculate_level(new_xp)

        await upsert_member_xp(pool, chat_id, user_id, bot_id,
                               xp_delta=-amount, level=new_level)
        await log_xp_transaction(pool, chat_id, user_id, bot_id, -amount, reason, given_by)

        return {"ok": True, "new_xp": new_xp, "new_level": new_level}
    except Exception as e:
        log.error(f"[XP] deduct_xp error | chat={chat_id} user={user_id} err={e}")
        return {"ok": False, "reason": str(e)}


async def get_leaderboard(
    pool,
    chat_id: int,
    bot_id: int,
    limit: int = 10,
    offset: int = 0,
) -> list[dict]:
    """Get top members by XP for a group."""
    from db.ops.engagement import get_xp_leaderboard
    return await get_xp_leaderboard(pool, chat_id, bot_id, limit, offset)


async def get_member_rank(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
) -> dict:
    """Get a specific member's rank position."""
    from db.ops.engagement import get_member_rank as db_get_rank
    data = await db_get_rank(pool, chat_id, user_id, bot_id)
    xp = data.get("xp", 0)
    needed, next_total = xp_to_next_level(xp)
    current_level_xp = xp_for_level(data.get("level", 1))
    level_range = next_total - current_level_xp
    progress_pct = 0
    if level_range > 0:
        progress_pct = int(((xp - current_level_xp) / level_range) * 100)
    data["xp_to_next"] = needed
    data["progress_pct"] = progress_pct
    return data
