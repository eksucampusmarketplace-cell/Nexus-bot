"""
api/routes/games.py

Game-related API endpoints for the Mini App games.
Handles XP awards from games and leaderboard data.
"""

from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user, require_auth
from db.client import db
from bot.handlers.xp import award_game_xp, get_leaderboard, get_user_rank

router = APIRouter(prefix="/api/groups")


@router.post("/{chat_id}/xp")
async def award_game_xp_endpoint(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    """
    Award XP earned from Mini App games.
    Called by game clients after game completion.
    """
    user_id = body.get("user_id")
    xp = body.get("xp", 0)

    if not user_id:
        raise HTTPException(400, "Missing user_id")

    # Cap XP at 500 per session
    xp = min(int(xp), 500)
    if xp <= 0:
        raise HTTPException(400, "Invalid XP amount")

    # Award XP and check for level up
    result = await award_game_xp(user_id, chat_id, xp)

    return {
        "awarded": xp,
        "total_xp": result["xp"] if result else None,
        "level_up": result["leveled_up"] if result else False,
        "new_level": result["level"] if result and result.get("leveled_up") else None,
    }


@router.get("/{chat_id}/leaderboard")
async def get_leaderboard_endpoint(
    chat_id: int, limit: int = 10, user: dict = Depends(require_auth)
):
    """
    Get XP leaderboard for a group.
    Returns top users by XP with their levels and badges.
    Reads from member_xp table (not dead users table).
    """
    if limit < 1 or limit > 50:
        limit = 10

    # Use db.pool to read from member_xp table
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT user_id, xp, level, messages_count 
               FROM member_xp 
               WHERE chat_id = $1 
               ORDER BY xp DESC 
               LIMIT $2""",
            chat_id, limit
        )
        leaderboard = []
        for row in rows:
            entry = dict(row)
            # Get user display info
            user_row = await conn.fetchrow(
                "SELECT first_name, username FROM users WHERE user_id = $1 AND chat_id = $2",
                entry["user_id"], chat_id
            )
            if user_row:
                entry["first_name"] = user_row.get("first_name", "Unknown")
                entry["username"] = user_row.get("username", "")
            leaderboard.append(entry)

    return {"chat_id": chat_id, "leaderboard": leaderboard, "count": len(leaderboard)}


@router.get("/{chat_id}/users/{user_id}/rank")
async def get_user_rank_endpoint(
    chat_id: int, user_id: int, user: dict = Depends(get_current_user)
):
    """
    Get a specific user's rank and stats.
    """
    rank_data = await get_user_rank(user_id, chat_id)

    if not rank_data:
        raise HTTPException(404, "User not found in group")

    return {"chat_id": chat_id, "user_id": user_id, "rank": rank_data}


@router.get("/{chat_id}/games/stats")
async def get_games_stats(chat_id: int, user: dict = Depends(get_current_user)):
    """
    Get aggregated games statistics for a group.
    """
    async with db.pool.acquire() as conn:
        # Total XP awarded in group
        total_xp = await conn.fetchval(
            "SELECT COALESCE(SUM(xp), 0) FROM users WHERE chat_id = $1", chat_id
        )

        # Total users with XP
        total_players = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE chat_id = $1 AND xp > 0", chat_id
        )

        # Users by level ranges
        level_dist = await conn.fetch(
            """SELECT 
                CASE 
                    WHEN level < 5 THEN '1-4'
                    WHEN level < 10 THEN '5-9'
                    WHEN level < 25 THEN '10-24'
                    ELSE '25+'
                END as range,
                COUNT(*) as count
               FROM users 
               WHERE chat_id = $1 AND xp > 0
               GROUP BY 1
               ORDER BY 1""",
            chat_id,
        )

    return {
        "chat_id": chat_id,
        "total_xp_awarded": total_xp,
        "total_players": total_players,
        "level_distribution": [dict(row) for row in level_dist],
    }
