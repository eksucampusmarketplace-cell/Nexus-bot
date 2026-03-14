"""
bot/engagement/reputation.py

Reputation system — members give +rep to each other.
Max 3 rep given per day per user.
Cannot give rep to yourself.
Cannot give rep to bots.
Admins can give rep without daily limit.
Negative rep only available to admins.

Log prefix: [REP]
"""

import logging
from datetime import date
from typing import Optional

log = logging.getLogger("rep")

DAILY_REP_LIMIT = 3


async def give_rep(
    pool,
    chat_id: int,
    from_user_id: int,
    to_user_id: int,
    bot_id: int,
    amount: int = 1,
    reason: Optional[str] = None,
    is_admin: bool = False
) -> tuple[bool, str]:
    from db.ops.engagement import (
        get_daily_rep_count, increment_daily_rep, update_rep,
        get_member_rep
    )
    from bot.engagement.badges import check_and_award_badges
    import asyncio

    if from_user_id == to_user_id:
        return False, "❌ You can't give rep to yourself."

    if amount < 0 and not is_admin:
        return False, "❌ Only admins can give negative rep."

    today = date.today()
    if not is_admin:
        count = await get_daily_rep_count(pool, chat_id, from_user_id, bot_id, today)
        if count >= DAILY_REP_LIMIT:
            return False, f"❌ You've used all {DAILY_REP_LIMIT} rep for today. Come back tomorrow!"

    await update_rep(pool, chat_id, from_user_id, to_user_id, bot_id, amount, reason)
    if not is_admin:
        await increment_daily_rep(pool, chat_id, from_user_id, bot_id, today)

    rep_data = await get_member_rep(pool, chat_id, to_user_id, bot_id)
    new_total = rep_data.get("rep_score", 0)

    asyncio.create_task(
        check_and_award_badges(pool, chat_id, to_user_id, bot_id, "rep_received", new_total)
    )
    asyncio.create_task(
        check_and_award_badges(pool, chat_id, from_user_id, bot_id, "rep_given",
                               rep_data.get("total_given", 0) + 1)
    )

    log.info(f"[REP] Given | chat={chat_id} from={from_user_id} to={to_user_id} amount={amount}")
    return True, f"✅ +{amount} rep given."


async def get_reputation(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int
) -> dict:
    from db.ops.engagement import get_member_rep, get_rep_leaderboard

    rep_data = await get_member_rep(pool, chat_id, user_id, bot_id)
    leaderboard = await get_rep_leaderboard(pool, chat_id, bot_id, limit=100)
    rank = 0
    for entry in leaderboard:
        if entry["user_id"] == user_id:
            rank = entry["rank"]
            break

    return {**rep_data, "rank_in_group": rank}


async def get_rep_leaderboard(
    pool,
    chat_id: int,
    bot_id: int,
    limit: int = 10
) -> list[dict]:
    from db.ops.engagement import get_rep_leaderboard as db_get
    return await db_get(pool, chat_id, bot_id, limit)


async def get_daily_remaining(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int
) -> int:
    from db.ops.engagement import get_daily_rep_count
    today = date.today()
    used = await get_daily_rep_count(pool, chat_id, user_id, bot_id, today)
    return max(0, DAILY_REP_LIMIT - used)
