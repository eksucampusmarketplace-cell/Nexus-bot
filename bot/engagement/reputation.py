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

log = logging.getLogger("rep")

DAILY_REP_LIMIT = 3


async def give_rep(
    pool,
    chat_id: int,
    from_user_id: int,
    to_user_id: int,
    bot_id: int,
    amount: int = 1,
    reason: str = None,
    is_admin: bool = False,
) -> tuple[bool, str]:
    """
    Give reputation to a member.
    Validates: not self, not bot, daily limit (unless admin).
    Records in rep_transactions.
    Updates member_reputation.
    Checks badge conditions.
    Returns (success, message)
    """
    try:
        from db.ops.engagement import (
            get_daily_rep_count, increment_daily_rep, update_rep,
        )
        from bot.engagement.badges import check_and_award_badges

        if from_user_id == to_user_id:
            return False, "❌ You can't give rep to yourself."

        if amount < 0 and not is_admin:
            return False, "❌ Only admins can give negative rep."

        if not is_admin:
            today = date.today()
            given = await get_daily_rep_count(pool, chat_id, from_user_id, bot_id, today)
            if given >= DAILY_REP_LIMIT:
                return False, f"❌ You've used all {DAILY_REP_LIMIT} rep for today."

        result = await update_rep(pool, chat_id, from_user_id, to_user_id, bot_id, amount, reason)

        if not is_admin and amount > 0:
            today = date.today()
            await increment_daily_rep(pool, chat_id, from_user_id, bot_id, today)

        new_score = result.get("rep_score", 0)
        await check_and_award_badges(pool, chat_id, to_user_id, bot_id, "rep_received", new_score)

        received_total = result.get("total_received", 0)
        await check_and_award_badges(pool, chat_id, from_user_id, bot_id, "rep_given", received_total)

        log.info(f"[REP] Give | chat={chat_id} from={from_user_id} to={to_user_id} amount={amount}")
        return True, f"✅ {'+'  if amount >= 0 else ''}{amount} rep given."
    except Exception as e:
        log.error(f"[REP] give_rep error | chat={chat_id} err={e}")
        return False, f"❌ Failed: {e}"


async def get_reputation(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
) -> dict:
    """Get reputation info for a member."""
    from db.ops.engagement import get_member_rep, get_rep_leaderboard
    rep = await get_member_rep(pool, chat_id, user_id, bot_id)
    board = await get_rep_leaderboard(pool, chat_id, bot_id, limit=100)
    rank = next((i + 1 for i, r in enumerate(board) if r["user_id"] == user_id), 0)
    rep["rank_in_group"] = rank
    return rep


async def get_rep_leaderboard(
    pool,
    chat_id: int,
    bot_id: int,
    limit: int = 10,
) -> list[dict]:
    """Top members by reputation score."""
    from db.ops.engagement import get_rep_leaderboard as db_get_rep_lb
    return await db_get_rep_lb(pool, chat_id, bot_id, limit)


async def get_daily_remaining(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
) -> int:
    """How many more rep can this user give today."""
    from db.ops.engagement import get_daily_rep_count
    today = date.today()
    given = await get_daily_rep_count(pool, chat_id, user_id, bot_id, today)
    return max(0, DAILY_REP_LIMIT - given)
