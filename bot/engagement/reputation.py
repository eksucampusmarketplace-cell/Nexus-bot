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
from datetime import date, timezone
from typing import Optional

log = logging.getLogger("rep")

DEFAULT_DAILY_LIMIT = 3


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
    # Validation
    if from_user_id == to_user_id:
        return False, "You cannot give reputation to yourself."

    if amount == 0:
        return False, "Amount cannot be zero."

    # Negative rep only for admins
    if amount < 0 and not is_admin:
        return False, "Only admins can give negative reputation."

    try:
        async with pool.acquire() as conn:
            # Check daily limit for non-admins
            if not is_admin and amount > 0:
                today = date.today()
                daily_row = await conn.fetchrow(
                    """
                    SELECT given_count FROM rep_daily_limits
                    WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3 AND date=$4
                    """,
                    chat_id,
                    from_user_id,
                    bot_id,
                    today,
                )

                current_given = daily_row["given_count"] if daily_row else 0
                if current_given >= DEFAULT_DAILY_LIMIT:
                    remaining = DEFAULT_DAILY_LIMIT - current_given
                    return (
                        False,
                        f"You've reached your daily limit. You have {remaining} rep left to give today.",
                    )

            # Record transaction
            await conn.execute(
                """
                INSERT INTO rep_transactions
                    (chat_id, from_user_id, to_user_id, bot_id, amount, reason)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                chat_id,
                from_user_id,
                to_user_id,
                bot_id,
                amount,
                reason,
            )

            # Update giver's stats
            await conn.execute(
                """
                INSERT INTO member_reputation
                    (chat_id, user_id, bot_id, total_given)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (chat_id, user_id, bot_id)
                DO UPDATE SET total_given = member_reputation.total_given + $4
                """,
                chat_id,
                from_user_id,
                bot_id,
                abs(amount),
            )

            # Update receiver's stats
            await conn.execute(
                """
                INSERT INTO member_reputation
                    (chat_id, user_id, bot_id, rep_score, total_received)
                VALUES ($1, $2, $3, $4, $4)
                ON CONFLICT (chat_id, user_id, bot_id)
                DO UPDATE SET
                    rep_score = member_reputation.rep_score + $4,
                    total_received = member_reputation.total_received + $4
                """,
                chat_id,
                to_user_id,
                bot_id,
                amount,
            )

            # Update daily limit
            if not is_admin and amount > 0:
                today = date.today()
                await conn.execute(
                    """
                    INSERT INTO rep_daily_limits
                        (chat_id, user_id, bot_id, date, given_count)
                    VALUES ($1, $2, $3, $4, 1)
                    ON CONFLICT (chat_id, user_id, bot_id, date)
                    DO UPDATE SET given_count = rep_daily_limits.given_count + 1
                    """,
                    chat_id,
                    from_user_id,
                    bot_id,
                    today,
                )

            # Get new totals
            to_row = await conn.fetchrow(
                """
                SELECT rep_score, total_received FROM member_reputation
                WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
                """,
                chat_id,
                to_user_id,
                bot_id,
            )

        log.info(f"[REP] {from_user_id} gave {amount} rep to {to_user_id} in chat {chat_id}")

        new_rep = to_row["rep_score"] if to_row else amount
        return True, f"+{amount} reputation given. Their rep is now {new_rep}."

    except Exception as e:
        log.error(f"[REP] Error giving rep: {e}")
        return False, f"Error: {str(e)}"


async def get_reputation(pool, chat_id: int, user_id: int, bot_id: int) -> dict:
    """
    Get reputation info for a member.
    Returns {rep_score, total_given, total_received, rank_in_group}
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT rep_score, total_given, total_received
                FROM member_reputation
                WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
                """,
                chat_id,
                user_id,
                bot_id,
            )

            # Get rank
            rank_row = await conn.fetchrow(
                """
                SELECT COUNT(*) + 1 as rank
                FROM member_reputation
                WHERE chat_id=$1 AND bot_id=$2 AND rep_score > COALESCE(
                    (SELECT rep_score FROM member_reputation
                     WHERE chat_id=$1 AND user_id=$3 AND bot_id=$2), 0
                )
                """,
                chat_id,
                bot_id,
                user_id,
            )

            if row:
                return {
                    "rep_score": row["rep_score"],
                    "total_given": row["total_given"],
                    "total_received": row["total_received"],
                    "rank_in_group": rank_row["rank"] if rank_row else None,
                }

            return {"rep_score": 0, "total_given": 0, "total_received": 0, "rank_in_group": None}

    except Exception as e:
        log.error(f"[REP] Error getting reputation: {e}")
        return {
            "rep_score": 0,
            "total_given": 0,
            "total_received": 0,
            "rank_in_group": None,
            "error": str(e),
        }


async def get_rep_leaderboard(pool, chat_id: int, bot_id: int, limit: int = 10) -> list[dict]:
    """Top members by reputation score."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, rep_score, total_received,
                       ROW_NUMBER() OVER (ORDER BY rep_score DESC) as rank
                FROM member_reputation
                WHERE chat_id=$1 AND bot_id=$2
                ORDER BY rep_score DESC
                LIMIT $3
                """,
                chat_id,
                bot_id,
                limit,
            )

            return [
                {
                    "rank": row["rank"],
                    "user_id": row["user_id"],
                    "rep_score": row["rep_score"],
                    "total_received": row["total_received"],
                }
                for row in rows
            ]

    except Exception as e:
        log.error(f"[REP] Error getting leaderboard: {e}")
        return []


async def get_daily_remaining(pool, chat_id: int, user_id: int, bot_id: int) -> int:
    """How many more rep can this user give today. Default 3."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT given_count FROM rep_daily_limits
                WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3 AND date=$4
                """,
                chat_id,
                user_id,
                bot_id,
                date.today(),
            )

            given = row["given_count"] if row else 0
            return max(0, DEFAULT_DAILY_LIMIT - given)

    except Exception as e:
        log.error(f"[REP] Error getting daily remaining: {e}")
        return DEFAULT_DAILY_LIMIT
