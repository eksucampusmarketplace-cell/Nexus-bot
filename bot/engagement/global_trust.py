"""
bot/engagement/global_trust.py

Global Trust Score System - Cross-group reputation tracking.
Users build a "Telegram reputation score" that follows them across ALL groups.

This is different from per-group reputation (member_reputation) in that:
- It's global: one score follows the user across ALL Nexus groups
- It's used for access control: admins can gate roles, giveaways, features based on it
- Network effects: users need good scores to participate in participating communities

Score ranges:
  0-30:   Low trust → restricted access
  31-60:  Medium trust → normal access  
  61-85:  High trust → premium access
  86-100: Trusted → full access + benefits

This creates network effects - users want high scores to participate anywhere.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("global_trust")

# Score thresholds
LOW_TRUST_THRESHOLD = 30
MEDIUM_TRUST_THRESHOLD = 60
HIGH_TRUST_THRESHOLD = 85
MAX_SCORE = 100
DEFAULT_SCORE = 50


async def get_global_trust_score(pool, user_id: int) -> int:
    """
    Get a user's global trust score across all groups.
    Returns score 0-100, default 50 if no history.
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT trust_score FROM global_user_trust
                WHERE user_id = $1
                """,
                user_id,
            )
            return row["trust_score"] if row else DEFAULT_SCORE
    except Exception as e:
        logger.error(f"[GLOBAL_TRUST] Error getting score: {e}")
        return DEFAULT_SCORE


async def update_global_trust_score(
    pool,
    user_id: int,
    delta: int,
    reason: str,
    group_id: Optional[int] = None,
) -> int:
    """
    Update a user's global trust score by delta (positive or negative).
    
    Returns the new score after update.
    """
    try:
        async with pool.acquire() as conn:
            # Get current score
            row = await conn.fetchrow(
                "SELECT trust_score FROM global_user_trust WHERE user_id = $1",
                user_id,
            )
            old_score = row["trust_score"] if row else DEFAULT_SCORE
            
            # Calculate new score
            new_score = max(0, min(MAX_SCORE, old_score + delta))
            
            # Upsert the score
            await conn.execute(
                """
                INSERT INTO global_user_trust (user_id, trust_score, last_updated)
                VALUES ($1, $2, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    trust_score = $2,
                    last_updated = NOW()
                """,
                user_id,
                new_score,
            )
            
            # Log the change
            await conn.execute(
                """
                INSERT INTO global_trust_history 
                    (user_id, old_score, new_score, change_amount, reason, group_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user_id,
                old_score,
                new_score,
                delta,
                reason,
                group_id,
            )
            
        logger.info(
            f"[GLOBAL_TRUST] Score updated | user={user_id} | "
            f"old={old_score} | new={new_score} | delta={delta:+d} | reason={reason}"
        )
        return new_score
        
    except Exception as e:
        logger.error(f"[GLOBAL_TRUST] Error updating score: {e}")
        return DEFAULT_SCORE


async def get_trust_tier(pool, user_id: int) -> str:
    """
    Get the trust tier name for a user.
    Returns: 'low', 'medium', 'high', 'trusted'
    """
    score = await get_global_trust_score(pool, user_id)
    
    if score >= HIGH_TRUST_THRESHOLD:
        return "trusted"
    elif score >= MEDIUM_TRUST_THRESHOLD:
        return "high"
    elif score >= LOW_TRUST_THRESHOLD:
        return "medium"
    else:
        return "low"


async def check_trust_requirement(
    pool,
    user_id: int,
    required_tier: str,
) -> tuple[bool, str]:
    """
    Check if a user meets a trust requirement.
    
    Args:
        pool: Database pool
        user_id: User to check
        required_tier: One of 'low', 'medium', 'high', 'trusted'
    
    Returns:
        (meets_requirement, current_tier)
    """
    tier = await get_trust_tier(pool, user_id)
    
    tier_levels = {
        "low": 0,
        "medium": 1,
        "high": 2,
        "trusted": 3,
    }
    
    user_level = tier_levels.get(tier, 0)
    required_level = tier_levels.get(required_tier, 0)
    
    return (user_level >= required_level, tier)


async def get_global_leaderboard(pool, limit: int = 20) -> list[dict]:
    """
    Get top users by global trust score.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, trust_score, last_updated
                FROM global_user_trust
                ORDER BY trust_score DESC
                LIMIT $1
                """,
                limit,
            )
            
            return [
                {
                    "user_id": row["user_id"],
                    "trust_score": row["trust_score"],
                    "last_updated": row["last_updated"].isoformat() if row["last_updated"] else None,
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"[GLOBAL_TRUST] Error getting leaderboard: {e}")
        return []


async def get_trust_history(pool, user_id: int, limit: int = 10) -> list[dict]:
    """
    Get a user's trust score history.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT old_score, new_score, change_amount, reason, group_id, created_at
                FROM global_trust_history
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )
            
            return [
                {
                    "old_score": row["old_score"],
                    "new_score": row["new_score"],
                    "change_amount": row["change_amount"],
                    "reason": row["reason"],
                    "group_id": row["group_id"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"[GLOBAL_TRUST] Error getting history: {e}")
        return []


async def sync_group_trust_to_global(pool, user_id: int, chat_id: int, bot_id: int) -> None:
    """
    Sync a user's per-group reputation to their global score.
    Called when they leave a group or on a periodic basis.
    """
    try:
        async with pool.acquire() as conn:
            # Get their reputation in this group
            row = await conn.fetchrow(
                """
                SELECT rep_score FROM member_reputation
                WHERE user_id = $1 AND chat_id = $2 AND bot_id = $3
                """,
                user_id,
                chat_id,
                bot_id,
            )
            
            if row and row["rep_score"] > 0:
                # Convert group rep to global trust contribution
                # Scale: 100 rep in a group = +1 to global trust (capped)
                contribution = min(5, row["rep_score"] // 100)
                
                if contribution > 0:
                    await update_global_trust_score(
                        pool,
                        user_id,
                        contribution,
                        f"group_rep_sync:{chat_id}",
                        chat_id,
                    )
                    
    except Exception as e:
        logger.debug(f"[GLOBAL_TRUST] Sync error: {e}")
