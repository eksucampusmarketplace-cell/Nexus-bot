"""
bot/engagement/xp.py

XP Engine — handles all XP earning, level calculation, and level-up rewards.

XP Formula (default, admin configurable):
Message sent: +1 XP (max once per 60 seconds per user per group)
Daily check-in: +10 XP (once per calendar day)
Game win: +5 XP
Game participation: +1 XP
Admin grant: +N XP (admin decides, max 20 at once)

Level Formula:
Level 1: 0 XP
Level 2: 100 XP
Level 3: 250 XP
Level 4: 500 XP
Level 5: 900 XP
Level N (N>=6): xp_for_level(N-1) + N * 150

This creates a curve where early levels are quick
(feels rewarding) and later levels take real commitment.

Double XP events multiply all earnings by 2x.

Log prefix: [XP]
"""

import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("xp")


def xp_for_level(level: int) -> int:
    """
    Calculate total XP required to reach a given level.
    Level 1: 0
    Level 2: 100
    Level 3: 250
    Level 4: 500
    Level 5: 900
    Level N (N>=6): xp_for_level(N-1) + N * 150
    """
    if level <= 1:
        return 0
    if level == 2:
        return 100
    if level == 3:
        return 250
    if level == 4:
        return 500
    if level == 5:
        return 900

    total = 900
    for i in range(6, level + 1):
        total += i * 150
    return total


def calculate_level(xp: int) -> int:
    """
    Calculate level from total XP.
    Uses xp_for_level as the authoritative threshold source.
    Returns level integer (minimum 1).
    """
    if xp < 100:
        return 1
    if xp < 250:
        return 2
    if xp < 500:
        return 3
    if xp < 900:
        return 4

    level = 5
    while xp >= xp_for_level(level + 1):
        level += 1

    return level


def xp_to_next_level(current_xp: int) -> tuple[int, int]:
    """
    Returns (xp_needed, total_for_next_level).
    Used for progress bar in /rank and miniapp.
    """
    current_level = calculate_level(current_xp)
    next_level_xp = xp_for_level(current_level + 1)
    needed = next_level_xp - current_xp
    return needed, next_level_xp


class XPEngine:
    """Core XP engine for handling XP operations."""

    def __init__(self):
        self.log = logging.getLogger("xp")

    async def award_xp(
        self,
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
            if reason == "message" and await self.is_rate_limited(redis, chat_id, user_id):
                return {"ok": False, "error": "rate_limited"}

            if redis:
                double_xp_key = f"nexus:xp:double:{chat_id}:{bot_id}"
                double_active = await redis.exists(double_xp_key)
                if double_active:
                    amount *= 2

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT xp, level, total_messages FROM member_xp
                    WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
                    """,
                    chat_id,
                    user_id,
                    bot_id,
                )

                if row:
                    current_xp = row["xp"]
                    current_level = row["level"]
                    total_messages = row["total_messages"] or 0
                else:
                    current_xp = 0
                    current_level = 1
                    total_messages = 0

                new_xp = current_xp + amount
                new_level = calculate_level(new_xp)
                leveled_up = new_level > current_level

                is_message = reason == "message"
                new_total_messages = total_messages + (1 if is_message else 0)

                if is_message:
                    await conn.execute(
                        """
                        INSERT INTO member_xp
                            (chat_id, user_id, bot_id, xp, level, total_messages,
                             last_message_at, last_xp_at, streak_days)
                        VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW(), 0)
                        ON CONFLICT (chat_id, user_id, bot_id)
                        DO UPDATE SET
                            xp = EXCLUDED.xp,
                            level = EXCLUDED.level,
                            total_messages = $6,
                            last_message_at = NOW(),
                            last_xp_at = NOW()
                        """,
                        chat_id,
                        user_id,
                        bot_id,
                        new_xp,
                        new_level,
                        new_total_messages,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO member_xp
                            (chat_id, user_id, bot_id, xp, level, total_messages,
                             last_xp_at, streak_days)
                        VALUES ($1, $2, $3, $4, $5, $6, NOW(), 0)
                        ON CONFLICT (chat_id, user_id, bot_id)
                        DO UPDATE SET
                            xp = EXCLUDED.xp,
                            level = EXCLUDED.level,
                            last_xp_at = NOW()
                        """,
                        chat_id,
                        user_id,
                        bot_id,
                        new_xp,
                        new_level,
                        new_total_messages,
                    )

                await conn.execute(
                    """
                    INSERT INTO xp_transactions
                        (chat_id, user_id, bot_id, amount, reason, given_by)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    chat_id,
                    user_id,
                    bot_id,
                    amount,
                    reason,
                    given_by,
                )

            if leveled_up:
                await self._handle_level_up(
                    pool, redis, bot, chat_id, user_id, bot_id, new_level, current_level
                )

            self.log.info(
                f"[XP] Awarded {amount} XP to user {user_id} in chat {chat_id}"
            )

            return {
                "ok": True,
                "new_xp": new_xp,
                "new_level": new_level,
                "leveled_up": leveled_up,
                "previous_level": current_level,
            }

        except Exception as e:
            self.log.error(f"[XP] Error awarding XP: {e}")
            return {"ok": False, "error": str(e)}

    async def _handle_level_up(
        self,
        pool,
        redis,
        bot,
        chat_id: int,
        user_id: int,
        bot_id: int,
        new_level: int,
        previous_level: int,
    ):
        """Handle level up event - check rewards, badges, announce."""
        try:
            async with pool.acquire() as conn:
                await conn.fetch(
                    """
                    SELECT * FROM level_rewards
                    WHERE chat_id=$1 AND bot_id=$2 AND level=$3 AND is_active=TRUE
                    """,
                    chat_id,
                    bot_id,
                    new_level,
                )

                level_config = await conn.fetchrow(
                    """
                    SELECT title FROM level_config
                    WHERE chat_id=$1 AND bot_id=$2 AND level=$3
                    """,
                    chat_id,
                    bot_id,
                    new_level,
                )
                level_config["title"] if level_config else f"Level {new_level}"

            if redis:
                await redis.publish(
                    f"nexus:events:{chat_id}",
                    f'{{"type":"level_up","user_id":{user_id},'
                    f'"new_level":{new_level},"previous_level":{previous_level}}}',
                )

            self.log.info(
                f"[XP] User {user_id} leveled up to {new_level} in chat {chat_id}"
            )

            try:
                from bot.handlers.auto_role import check_auto_roles

                async with pool.acquire() as ar_conn:
                    xp_row = await ar_conn.fetchrow(
                        "SELECT xp FROM member_xp WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3",
                        chat_id,
                        user_id,
                        bot_id,
                    )
                    current_xp = xp_row["xp"] if xp_row else 0

                await check_auto_roles(
                    bot, pool, chat_id, user_id, bot_id, current_xp, new_level
                )
            except Exception as ar_err:
                self.log.debug(f"[XP] Auto-role check skipped: {ar_err}")

        except Exception as e:
            self.log.error(f"[XP] Error handling level up: {e}")

    async def deduct_xp(
        self,
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
        Remove XP from a member (admin action or penalty).
        Never goes below 0.
        Recalculates level (can de-level).
        Logs transaction.
        Returns {ok, new_xp, new_level}
        """
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT xp FROM member_xp
                    WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
                    """,
                    chat_id,
                    user_id,
                    bot_id,
                )

                if not row:
                    return {"ok": False, "error": "Member has no XP"}

                current_xp = row["xp"]
                new_xp = max(0, current_xp - amount)
                new_level = calculate_level(new_xp)

                await conn.execute(
                    """
                    UPDATE member_xp
                    SET xp=$1, level=$2
                    WHERE chat_id=$3 AND user_id=$4 AND bot_id=$5
                    """,
                    new_xp,
                    new_level,
                    chat_id,
                    user_id,
                    bot_id,
                )

                await conn.execute(
                    """
                    INSERT INTO xp_transactions
                        (chat_id, user_id, bot_id, amount, reason, given_by)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    chat_id,
                    user_id,
                    bot_id,
                    -amount,
                    reason,
                    given_by,
                )

            return {"ok": True, "new_xp": new_xp, "new_level": new_level}

        except Exception as e:
            self.log.error(f"[XP] Error deducting XP: {e}")
            return {"ok": False, "error": str(e)}

    async def get_leaderboard(
        self, pool, chat_id: int, bot_id: int, limit: int = 10, offset: int = 0
    ) -> list[dict]:
        """
        Get top members by XP for a group.
        Returns [{rank, user_id, xp, level}]
        """
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT user_id, xp, level,
                           ROW_NUMBER() OVER (ORDER BY xp DESC) as rank
                    FROM member_xp
                    WHERE chat_id=$1 AND bot_id=$2
                    ORDER BY xp DESC
                    LIMIT $3 OFFSET $4
                    """,
                    chat_id,
                    bot_id,
                    limit,
                    offset,
                )

                return [
                    {
                        "rank": row["rank"],
                        "user_id": row["user_id"],
                        "xp": row["xp"],
                        "level": row["level"],
                    }
                    for row in rows
                ]

        except Exception as e:
            self.log.error(f"[XP] Error getting leaderboard: {e}")
            return []

    async def get_member_rank(
        self, pool, chat_id: int, user_id: int, bot_id: int
    ) -> dict:
        """
        Get a specific member's rank position.
        Returns {rank, total_members, xp, level, xp_to_next, progress_pct}
        """
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT xp, level FROM member_xp
                    WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
                    """,
                    chat_id,
                    user_id,
                    bot_id,
                )

                if not row:
                    return {"rank": None, "total_members": 0}

                rank_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) + 1 as rank
                    FROM member_xp
                    WHERE chat_id=$1 AND bot_id=$2 AND xp > $3
                    """,
                    chat_id,
                    bot_id,
                    row["xp"],
                )

                total_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as total FROM member_xp
                    WHERE chat_id=$1 AND bot_id=$2
                    """,
                    chat_id,
                    bot_id,
                )

                xp_needed, next_level_xp = xp_to_next_level(row["xp"])
                prev_level_xp = xp_for_level(row["level"])
                progress_pct = 0
                if next_level_xp > prev_level_xp:
                    progress_pct = int(
                        ((row["xp"] - prev_level_xp) / (next_level_xp - prev_level_xp))
                        * 100
                    )

                return {
                    "rank": rank_row["rank"] if rank_row else None,
                    "total_members": total_row["total"] if total_row else 0,
                    "xp": row["xp"],
                    "level": row["level"],
                    "xp_to_next": xp_needed,
                    "progress_pct": progress_pct,
                }

        except Exception as e:
            self.log.error(f"[XP] Error getting member rank: {e}")
            return {"rank": None, "total_members": 0}

    async def is_rate_limited(self, redis, chat_id: int, user_id: int) -> bool:
        """
        Check if user is in cooldown for XP earning from messages.
        Redis key: nexus:xp:cooldown:{chat_id}:{user_id}
        TTL: 60 seconds default
        """
        if not redis:
            return False

        key = f"nexus:xp:cooldown:{chat_id}:{user_id}"
        exists = await redis.exists(key)
        if exists:
            return True

        await redis.setex(key, 60, "1")
        return False

    async def start_double_xp(
        self, pool, chat_id: int, bot_id: int, hours: int
    ) -> bool:
        """Enable double XP event for a group for N hours."""
        try:
            import datetime as dt
            until = datetime.now(timezone.utc) + dt.timedelta(hours=hours)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO xp_settings (chat_id, bot_id, double_xp_active, double_xp_until)
                    VALUES ($1, $2, TRUE, $3)
                    ON CONFLICT (chat_id, bot_id)
                    DO UPDATE SET double_xp_active=TRUE, double_xp_until=$3
                    """,
                    chat_id,
                    bot_id,
                    until,
                )
            return True
        except Exception as e:
            self.log.error(f"[XP] Error starting double XP: {e}")
            return False

    async def check_double_xp(self, pool, chat_id: int, bot_id: int) -> bool:
        """Check if double XP is currently active."""
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT double_xp_active, double_xp_until FROM xp_settings
                    WHERE chat_id=$1 AND bot_id=$2
                    """,
                    chat_id,
                    bot_id,
                )

                if not row or not row["double_xp_active"]:
                    return False

                if row["double_xp_until"] and row["double_xp_until"] < datetime.now(timezone.utc):
                    await conn.execute(
                        """
                        UPDATE xp_settings
                        SET double_xp_active=FALSE, double_xp_until=NULL
                        WHERE chat_id=$1 AND bot_id=$2
                        """,
                        chat_id,
                        bot_id,
                    )
                    return False

                return True

        except Exception as e:
            self.log.error(f"[XP] Error checking double XP: {e}")
            return False

    async def get_xp_settings(self, pool, chat_id: int, bot_id: int) -> dict:
        """Get XP settings for a group."""
        defaults = {
            "enabled": True,
            "xp_per_message": 1,
            "xp_per_daily": 10,
            "xp_per_game_win": 5,
            "xp_per_game_play": 1,
            "message_cooldown_s": 60,
            "level_up_announce": True,
        }
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM xp_settings
                    WHERE chat_id=$1 AND bot_id=$2
                    """,
                    chat_id,
                    bot_id,
                )

                if row:
                    return {
                        "enabled": row["enabled"],
                        "xp_per_message": row["xp_per_message"],
                        "xp_per_daily": row["xp_per_daily"],
                        "xp_per_game_win": row["xp_per_game_win"],
                        "xp_per_game_play": row["xp_per_game_play"],
                        "message_cooldown_s": row["message_cooldown_s"],
                        "level_up_announce": row["level_up_announce"],
                    }

                return defaults

        except Exception as e:
            self.log.error(f"[XP] Error getting XP settings: {e}")
            return defaults
