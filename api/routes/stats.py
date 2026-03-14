"""
Bot statistics dashboard API
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
async def get_stats_overview(user: dict = Depends(get_current_user)):
    """
    Get bot overview statistics
    Returns aggregated stats across all groups
    """
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Get bot_id from user context
        bot_id = await _get_bot_id_from_user(user)

        stats = {
            "total_groups": 0,
            "active_groups_7d": 0,
            "total_users": 0,
            "active_users_7d": 0,
            "commands_today": 0,
            "music_plays_today": 0,
            "games_played_today": 0,
            "top_commands": [],
            "growth_chart": [],
        }

        # Get today's date
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        async with db.pool.acquire() as conn:
            # Total groups
            stats["total_groups"] = (
                await conn.fetchval(
                    "SELECT COUNT(DISTINCT chat_id) FROM groups WHERE bot_id = $1", bot_id
                )
                or 0
            )

            # Active groups (7 days)
            stats["active_groups_7d"] = (
                await conn.fetchval(
                    """SELECT COUNT(DISTINCT chat_id) FROM command_usage
                   WHERE bot_id = $1 AND date >= $2""",
                    bot_id,
                    week_ago,
                )
                or 0
            )

            # Total unique users
            stats["total_users"] = (
                await conn.fetchval(
                    "SELECT COUNT(DISTINCT user_id) FROM command_usage WHERE bot_id = $1", bot_id
                )
                or 0
            )

            # Active users (7 days)
            stats["active_users_7d"] = (
                await conn.fetchval(
                    """SELECT COUNT(DISTINCT user_id) FROM command_usage
                   WHERE bot_id = $1 AND date >= $2""",
                    bot_id,
                    week_ago,
                )
                or 0
            )

            # Today's stats
            daily_stats = await conn.fetchrow(
                """SELECT commands_count, music_plays, games_played
                   FROM bot_stats_daily WHERE bot_id = $1 AND date = $2""",
                bot_id,
                today,
            )

            if daily_stats:
                stats["commands_today"] = daily_stats["commands_count"] or 0
                stats["music_plays_today"] = daily_stats["music_plays"] or 0
                stats["games_played_today"] = daily_stats["games_played"] or 0

            # Top commands
            top_cmds = await conn.fetch(
                """SELECT command, COUNT(*) as count
                   FROM command_usage
                   WHERE bot_id = $1 AND date >= $2
                   GROUP BY command
                   ORDER BY count DESC
                   LIMIT 10""",
                bot_id,
                week_ago,
            )
            stats["top_commands"] = [
                {"command": r["command"], "count": r["count"]} for r in top_cmds
            ]

            # Growth chart (last 30 days)
            growth = await conn.fetch(
                """SELECT date, new_groups FROM bot_stats_daily
                   WHERE bot_id = $1 AND date >= $2
                   ORDER BY date ASC""",
                bot_id,
                today - timedelta(days=30),
            )
            stats["growth_chart"] = [
                {"date": r["date"].isoformat(), "new_groups": r["new_groups"]} for r in growth
            ]

        return {"ok": True, "stats": stats}

    except Exception as e:
        logger.error(f"[STATS] Error getting overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/{chat_id}")
async def get_chat_stats(chat_id: int, user: dict = Depends(get_current_user)):
    """Get statistics for a specific chat"""
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        bot_id = await _get_bot_id_from_user(user)

        async with db.pool.acquire() as conn:
            # Check access
            has_access = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM groups WHERE chat_id = $1 AND bot_id = $2)",
                chat_id,
                bot_id,
            )
            if not has_access:
                raise HTTPException(status_code=403, detail="No access to this group")

            # Get game scores
            scores = await conn.fetch(
                """SELECT game_type, COUNT(DISTINCT user_id) as players,
                   SUM(total_plays) as total_plays, MAX(high_score) as top_score
                   FROM game_scores WHERE chat_id = $1
                   GROUP BY game_type""",
                chat_id,
            )

            # Get command usage
            commands = await conn.fetch(
                """SELECT command, COUNT(*) as count
                   FROM command_usage WHERE chat_id = $1 AND date >= $2
                   GROUP BY command ORDER BY count DESC LIMIT 10""",
                chat_id,
                datetime.now().date() - timedelta(days=7),
            )

            return {
                "ok": True,
                "games": [
                    {
                        "type": r["game_type"],
                        "players": r["players"],
                        "total_plays": r["total_plays"],
                        "top_score": r["top_score"],
                    }
                    for r in scores
                ],
                "commands": [{"command": r["command"], "count": r["count"]} for r in commands],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[STATS] Error getting chat stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _get_bot_id_from_user(user: dict) -> int:
    """Extract bot_id from user's validated bot token"""
    import hashlib
    from db.client import db
    import db.ops.bots as db_ops_bots

    bot_token = user.get("validated_bot_token")
    if not bot_token or not db.pool:
        return 0

    token_hash = hashlib.sha256(bot_token.encode()).hexdigest()
    bot = await db_ops_bots.get_bot_by_token_hash(db.pool, token_hash)
    return bot.get("bot_id", 0) if bot else 0


# Export function to record stats
async def record_command_usage(pool, bot_id: int, command: str, user_id: int, chat_id: int):
    """Record a command usage for statistics"""
    from datetime import date

    try:
        today = date.today()

        async with pool.acquire() as conn:
            # Insert command usage
            await conn.execute(
                """INSERT INTO command_usage (date, bot_id, command, user_id, chat_id)
                   VALUES ($1, $2, $3, $4, $5)""",
                today,
                bot_id,
                command,
                user_id,
                chat_id,
            )

            # Update daily stats
            await conn.execute(
                """INSERT INTO bot_stats_daily (date, bot_id, commands_count)
                   VALUES ($1, $2, 1)
                   ON CONFLICT (date, bot_id) DO UPDATE
                   SET commands_count = bot_stats_daily.commands_count + 1""",
                today,
                bot_id,
            )
    except Exception as e:
        logger.error(f"[STATS] Error recording command: {e}")


async def record_game_played(pool, bot_id: int, game_type: str):
    """Record a game being played"""
    from datetime import date

    try:
        today = date.today()

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO bot_stats_daily (date, bot_id, games_played)
                   VALUES ($1, $2, 1)
                   ON CONFLICT (date, bot_id) DO UPDATE
                   SET games_played = bot_stats_daily.games_played + 1""",
                today,
                bot_id,
            )
    except Exception as e:
        logger.error(f"[STATS] Error recording game: {e}")


async def record_music_play(pool, bot_id: int):
    """Record a music play"""
    from datetime import date

    try:
        today = date.today()

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO bot_stats_daily (date, bot_id, music_plays)
                   VALUES ($1, $2, 1)
                   ON CONFLICT (date, bot_id) DO UPDATE
                   SET music_plays = bot_stats_daily.music_plays + 1""",
                today,
                bot_id,
            )
    except Exception as e:
        logger.error(f"[STATS] Error recording music play: {e}")
