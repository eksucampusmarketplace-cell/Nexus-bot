"""
bot/engagement/xp.py

XP Engine — handles all XP earning, level calculation, and level-up rewards.

XP Formula (default, admin configurable):
  Message sent:       +1 XP (max once per 60 seconds per user per group)
  Daily check-in:     +10 XP (once per calendar day)
  Game win:           +5 XP
  Game participation: +1 XP
  Admin grant:        +N XP (admin decides, max 20 at once)

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
from typing import Optional

log = logging.getLogger("xp")

_LEVEL_THRESHOLDS: dict[int, int] = {}


def _build_thresholds():
    thresholds = {1: 0}
    xp = 0
    for level in range(2, 101):
        xp += level * 150
        thresholds[level] = xp
    return thresholds


def _get_thresholds() -> dict[int, int]:
    global _LEVEL_THRESHOLDS
    if not _LEVEL_THRESHOLDS:
        _LEVEL_THRESHOLDS = _build_thresholds()
    return _LEVEL_THRESHOLDS


def xp_for_level(level: int) -> int:
    if level <= 1:
        return 0
    thresholds = _get_thresholds()
    return thresholds.get(level, sum(i * 150 for i in range(2, level + 1)))


def calculate_level(xp: int) -> int:
    if xp <= 0:
        return 1
    thresholds = _get_thresholds()
    level = 1
    for lvl, required in sorted(thresholds.items()):
        if xp >= required:
            level = lvl
        else:
            break
    return max(1, level)


def xp_to_next_level(current_xp: int) -> tuple[int, int]:
    current_level = calculate_level(current_xp)
    next_level = current_level + 1
    total_for_next = xp_for_level(next_level)
    total_for_current = xp_for_level(current_level)
    xp_in_level = current_xp - total_for_current
    xp_needed = total_for_next - current_xp
    return xp_needed, total_for_next


async def is_rate_limited(redis, chat_id: int, user_id: int) -> bool:
    if not redis:
        return False
    key = f"nexus:xp:cooldown:{chat_id}:{user_id}"
    result = await redis.get(key)
    return result is not None


async def _set_cooldown(redis, chat_id: int, user_id: int, seconds: int):
    if not redis:
        return
    key = f"nexus:xp:cooldown:{chat_id}:{user_id}"
    await redis.setex(key, seconds, "1")


async def check_double_xp(pool, chat_id: int, bot_id: int) -> bool:
    from db.ops.engagement import get_xp_settings
    from datetime import datetime, timezone
    settings = await get_xp_settings(pool, chat_id, bot_id)
    if not settings.get("double_xp_active"):
        return False
    until = settings.get("double_xp_until")
    if until and until < datetime.now(timezone.utc):
        return False
    return True


async def start_double_xp(pool, chat_id: int, bot_id: int, hours: int):
    from datetime import datetime, timezone, timedelta
    until = datetime.now(timezone.utc) + timedelta(hours=hours)
    from db.ops.engagement import upsert_xp_settings
    await upsert_xp_settings(
        pool, chat_id, bot_id,
        double_xp_active=True, double_xp_until=until
    )
    log.info(f"[XP] Double XP started | chat={chat_id} hours={hours} until={until}")


async def level_up(
    pool, redis, bot,
    chat_id: int, user_id: int, bot_id: int,
    new_level: int, previous_level: int
):
    from db.ops.engagement import get_level_rewards, get_xp_settings
    from bot.engagement.badges import check_and_award_badges

    log.info(f"[XP] Level up! | chat={chat_id} user={user_id} {previous_level}→{new_level}")

    rewards = await get_level_rewards(pool, chat_id, bot_id, new_level)
    title = None
    for reward in rewards:
        if reward["reward_type"] == "title":
            title = reward["reward_value"]

    settings = await get_xp_settings(pool, chat_id, bot_id)
    if settings.get("level_up_announce", True) and bot:
        try:
            mention = f"user {user_id}"
            try:
                member = await bot.get_chat_member(chat_id, user_id)
                name = member.user.first_name if member and member.user else str(user_id)
                mention = f"<a href='tg://user?id={user_id}'>{name}</a>"
            except Exception:
                pass
            template = settings.get(
                "level_up_message", "🎉 {mention} reached Level {level}! {title}"
            )
            text = template.format(
                mention=mention,
                level=new_level,
                title=title or ""
            ).strip()
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            log.warning(f"[XP] Failed to announce level up: {e}")

    asyncio.create_task(
        check_and_award_badges(pool, chat_id, user_id, bot_id, "level_up", new_level)
    )

    if redis:
        try:
            import json
            event = json.dumps({
                "type": "level_up",
                "chat_id": chat_id,
                "user_id": user_id,
                "new_level": new_level,
                "previous_level": previous_level,
            })
            await redis.publish(f"nexus:events:{chat_id}", event)
        except Exception:
            pass


async def award_xp(
    pool,
    redis,
    bot,
    chat_id: int,
    user_id: int,
    bot_id: int,
    amount: int,
    reason: str,
    given_by: Optional[int] = None
) -> dict:
    try:
        from db.ops.engagement import (
            get_xp_settings, get_member_xp, update_member_xp_direct,
            log_xp_transaction, upsert_xp_settings
        )

        settings = await get_xp_settings(pool, chat_id, bot_id)
        if not settings.get("enabled", True):
            return {"ok": False, "reason": "xp_disabled"}

        cooldown = settings.get("message_cooldown_s", 60)
        if reason == "message" and await is_rate_limited(redis, chat_id, user_id):
            return {"ok": False, "reason": "rate_limited"}

        if await check_double_xp(pool, chat_id, bot_id):
            amount = amount * 2

        current = await get_member_xp(pool, chat_id, user_id, bot_id)
        current_xp = current.get("xp", 0)
        previous_level = current.get("level", 1)

        new_xp = max(0, current_xp + amount)
        new_level = calculate_level(new_xp)

        await update_member_xp_direct(pool, chat_id, user_id, bot_id, new_xp, new_level)
        await log_xp_transaction(pool, chat_id, user_id, bot_id, amount, reason, given_by)

        if reason == "message":
            await _set_cooldown(redis, chat_id, user_id, cooldown)

        leveled_up = new_level > previous_level
        if leveled_up:
            asyncio.create_task(
                level_up(pool, redis, bot, chat_id, user_id, bot_id, new_level, previous_level)
            )

        try:
            from db.ops.engagement import get_chat_networks, sync_network_xp
            networks = await get_chat_networks(pool, chat_id)
            for network in networks:
                asyncio.create_task(
                    sync_network_xp(pool, network["id"], user_id, amount)
                )
        except Exception:
            pass

        if redis:
            try:
                import json
                event = json.dumps({
                    "type": "xp_earned",
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "amount": amount,
                    "reason": reason,
                    "new_total": new_xp,
                })
                await redis.publish(f"nexus:events:{chat_id}", event)
            except Exception:
                pass

        return {
            "ok": True,
            "new_xp": new_xp,
            "new_level": new_level,
            "leveled_up": leveled_up,
            "previous_level": previous_level,
        }
    except Exception as e:
        log.error(f"[XP] award_xp error: {e}")
        return {"ok": False, "reason": str(e)}


async def deduct_xp(
    pool,
    redis,
    chat_id: int,
    user_id: int,
    bot_id: int,
    amount: int,
    reason: str,
    given_by: int
) -> dict:
    try:
        from db.ops.engagement import get_member_xp, update_member_xp_direct, log_xp_transaction

        current = await get_member_xp(pool, chat_id, user_id, bot_id)
        current_xp = current.get("xp", 0)
        new_xp = max(0, current_xp - amount)
        new_level = calculate_level(new_xp)

        await update_member_xp_direct(pool, chat_id, user_id, bot_id, new_xp, new_level)
        await log_xp_transaction(pool, chat_id, user_id, bot_id, -amount, reason, given_by)

        log.info(f"[XP] Deducted | chat={chat_id} user={user_id} -{amount} reason={reason}")
        return {"ok": True, "new_xp": new_xp, "new_level": new_level}
    except Exception as e:
        log.error(f"[XP] deduct_xp error: {e}")
        return {"ok": False, "reason": str(e)}


async def get_leaderboard(
    pool,
    chat_id: int,
    bot_id: int,
    limit: int = 10,
    offset: int = 0
) -> list[dict]:
    from db.ops.engagement import get_xp_leaderboard
    return await get_xp_leaderboard(pool, chat_id, bot_id, limit, offset)


async def get_member_rank(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int
) -> dict:
    from db.ops.engagement import get_member_rank as db_get_rank, get_member_xp
    rank_data = await db_get_rank(pool, chat_id, user_id, bot_id)
    xp_data = await get_member_xp(pool, chat_id, user_id, bot_id)
    xp = xp_data.get("xp", 0)
    level = xp_data.get("level", 1)
    xp_needed, total_next = xp_to_next_level(xp)
    xp_for_current = xp_for_level(level)
    level_xp_range = total_next - xp_for_current
    progress_pct = int((xp - xp_for_current) / max(1, level_xp_range) * 100)
    return {
        **rank_data,
        "xp": xp,
        "level": level,
        "xp_to_next": xp_needed,
        "progress_pct": min(100, progress_pct),
    }
