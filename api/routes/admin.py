"""
api/routes/admin.py

Admin routes for memory management and system stats.
Owner notification preferences and history.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import get_current_user
from config import settings

log = logging.getLogger("admin_api")
router = APIRouter()


class NotificationPreference(BaseModel):
    muted: bool


@router.get("/api/admin/memory")
async def memory_stats(request: Request, user: dict = Depends(get_current_user)):
    """Superadmin only — process memory stats."""
    if user.get("id") != settings.OWNER_ID:
        raise HTTPException(status_code=403)
    lazy = request.app.state.lazy_manager
    return lazy.get_memory_usage() if lazy else {}


@router.get("/api/admin/stats")
async def admin_stats(request: Request, user: dict = Depends(get_current_user)):
    """Owner-only — system-wide stats for the owner dashboard.
    
    For main owner (OWNER_ID): Returns system-wide stats
    For clone owners: Returns stats for their own clones only
    """
    pool = request.app.state.db
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    is_main_owner = user.get("id") == settings.OWNER_ID
    user_id = user.get("id")
    
    # For clone owners, get their bot IDs first
    bot_ids = []
    if not is_main_owner:
        bot_ids = await pool.fetch(
            "SELECT bot_id FROM bots WHERE owner_user_id = $1 AND is_primary = FALSE",
            user_id
        )
        bot_ids = [r['bot_id'] for r in bot_ids]
    
    if is_main_owner:
        # Main owner: system-wide stats
        bots = await pool.fetchval(
            "SELECT COUNT(*) FROM bots WHERE status='active' AND is_primary=FALSE"
        )
        groups = await pool.fetchval("SELECT COUNT(*) FROM groups")
        users = await pool.fetchval("SELECT COUNT(DISTINCT user_id) FROM users")
    elif bot_ids:
        # Clone owner: stats for their bots only
        bots = len(bot_ids)
        groups = await pool.fetchval(
            "SELECT COUNT(DISTINCT chat_id) FROM clone_bot_groups WHERE bot_id = ANY($1) AND is_active = TRUE",
            bot_ids
        )
        users = await pool.fetchval(
            """SELECT COUNT(DISTINCT user_id) FROM group_members gm
               JOIN clone_bot_groups cbg ON gm.chat_id = cbg.chat_id
               WHERE cbg.bot_id = ANY($1) AND cbg.is_active = TRUE""",
            bot_ids
        )
    else:
        bots = 0
        groups = 0
        users = 0
    
    return {"bots": bots or 0, "groups": groups or 0, "users": users or 0, "is_main_owner": is_main_owner}


@router.get("/api/clone-owner/stats")
async def clone_owner_stats(request: Request, user: dict = Depends(get_current_user)):
    """Clone owner stats - returns stats specific to the clone owner's bots."""
    pool = request.app.state.db
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    user_id = user.get("id")
    
    # Get all bots owned by this user (excluding primary)
    bots = await pool.fetch(
        """SELECT bot_id, username, display_name, status, group_limit,
                  webhook_active, death_reason, created_at
           FROM bots WHERE owner_user_id = $1 AND is_primary = FALSE
           ORDER BY created_at DESC""",
        user_id
    )
    
    if not bots:
        return {
            "bots": [],
            "total_groups": 0,
            "total_users": 0,
            "active_bots": 0,
            "error_bots": 0
        }
    
    bot_ids = [b['bot_id'] for b in bots]
    
    # Get group counts per bot
    group_counts = await pool.fetch(
        """SELECT cbg.bot_id, COUNT(*) as group_count
           FROM clone_bot_groups cbg
           WHERE cbg.bot_id = ANY($1) AND cbg.is_active = TRUE
           GROUP BY cbg.bot_id""",
        bot_ids
    )
    group_count_map = {r['bot_id']: r['group_count'] for r in group_counts}
    
    # Get total unique users across all their bot groups
    total_users = await pool.fetchval(
        """SELECT COUNT(DISTINCT user_id) FROM group_members gm
           JOIN clone_bot_groups cbg ON gm.chat_id = cbg.chat_id
           WHERE cbg.bot_id = ANY($1) AND cbg.is_active = TRUE""",
        bot_ids
    )
    
    active_bots = sum(1 for b in bots if b['status'] == 'active')
    error_bots = sum(1 for b in bots if b['status'] == 'dead')
    
    # Format bots with group counts
    formatted_bots = []
    for b in bots:
        formatted_bots.append({
            "bot_id": b['bot_id'],
            "username": b['username'],
            "display_name": b['display_name'],
            "status": b['status'],
            "group_limit": b['group_limit'],
            "webhook_active": b['webhook_active'],
            "death_reason": b['death_reason'],
            "groups_count": group_count_map.get(b['bot_id'], 0),
            "created_at": b['created_at'].isoformat() if b.get('created_at') else None
        })
    
    return {
        "bots": formatted_bots,
        "total_groups": sum(group_count_map.values()),
        "total_users": total_users or 0,
        "active_bots": active_bots,
        "error_bots": error_bots
    }


@router.get("/api/clone-owner/groups")
async def clone_owner_groups(request: Request, user: dict = Depends(get_current_user)):
    """Get all groups across all clone bots owned by this user."""
    pool = request.app.state.db
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    user_id = user.get("id")
    
    # Get all active groups for all clone bots owned by this user
    groups = await pool.fetch(
        """SELECT g.chat_id, g.title, g.member_count, g.photo_small,
                  cbg.bot_id, b.username as bot_username, b.display_name as bot_name
           FROM groups g
           JOIN clone_bot_groups cbg ON g.chat_id = cbg.chat_id
           JOIN bots b ON b.bot_id = cbg.bot_id
           WHERE b.owner_user_id = $1 AND cbg.is_active = TRUE
           ORDER BY g.title""",
        user_id
    )
    
    return [
        {
            "chat_id": g['chat_id'],
            "title": g['title'],
            "member_count": g['member_count'],
            "photo_small": g['photo_small'],
            "bot_id": g['bot_id'],
            "bot_username": g['bot_username'],
            "bot_name": g['bot_name']
        }
        for g in groups
    ]


@router.post("/api/admin/ml/retrain")
async def retrain_ml_model(request: Request, user: dict = Depends(get_current_user)):
    """Only accessible by OWNER_ID. Calls classifier.train() in a background task."""
    if user.get("id") != settings.OWNER_ID:
        raise HTTPException(status_code=403)

    import asyncio

    from bot.ml.spam_classifier import classifier

    async def _retrain():
        result = await classifier.train()
        # In a real scenario, we would notify the owner here.
        # For now, just log it.
        log.info(f"ML Retraining complete: {result}")

    asyncio.create_task(_retrain())
    return {"status": "training_started"}


# ═══════════════════════════════════════════════════════════════════════════════
# Owner Notification Preferences API
# ═══════════════════════════════════════════════════════════════════════════════

# List of all 16 error types from ERROR_CATALOG
ALL_ERROR_TYPES = [
    "PRIVACY_MODE_ON",
    "WEBHOOK_FAILED",
    "WEBHOOK_MISSING_UPDATES",
    "BOT_NOT_ADMIN",
    "BOT_CANT_DELETE",
    "BOT_CANT_RESTRICT",
    "BOT_KICKED",
    "GROUPS_NOT_APPEARING",
    "FED_BAN_PROPAGATION_FAILED",
    "CAPTCHA_WEBAPP_URL_MISSING",
    "INVALID_TOKEN",
    "MISSING_ENV_VAR",
    "SUPABASE_CONNECTION_FAILED",
    "ML_TRAINING_COMPLETE",
    "ML_TRAINING_FAILED",
    "ANALYTICS_ERROR",
]


@router.get("/api/owner/notifications")
async def get_notification_preferences(request: Request, user: dict = Depends(get_current_user)):
    """
    Get owner's notification preferences.
    Returns list of error types and whether each is muted.
    """
    owner_id = user.get("id")
    pool = request.app.state.db

    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with pool.acquire() as conn:
            # Get all preferences for this owner
            prefs = await conn.fetch(
                "SELECT error_type, notify_dm FROM owner_error_prefs WHERE owner_id = $1", owner_id
            )

            # Create lookup dict
            pref_dict = {p["error_type"]: p["notify_dm"] for p in prefs}

            # Build response for all error types
            result = []
            for error_type in ALL_ERROR_TYPES:
                result.append(
                    {
                        "error_type": error_type,
                        "muted": not pref_dict.get(
                            error_type, True
                        ),  # Default to not muted (notify_dm=True)
                        "category": _get_error_category(error_type),
                    }
                )

            return {"preferences": result}

    except Exception as e:
        log.error(f"Failed to get notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch preferences")


@router.put("/api/owner/notifications/{error_type}")
async def update_notification_preference(
    error_type: str,
    pref: NotificationPreference,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Update owner's preference for a specific error type.
    muted=true to silence, muted=false to enable notifications.
    """
    owner_id = user.get("id")
    pool = request.app.state.db

    if error_type not in ALL_ERROR_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown error type: {error_type}")

    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with pool.acquire() as conn:
            # Upsert preference
            await conn.execute(
                """INSERT INTO owner_error_prefs (owner_id, error_type, notify_dm)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (owner_id, error_type)
                   DO UPDATE SET notify_dm = EXCLUDED.notify_dm""",
                owner_id,
                error_type,
                not pref.muted,
            )

        return {"success": True, "error_type": error_type, "muted": pref.muted}

    except Exception as e:
        log.error(f"Failed to update notification preference: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preference")


@router.get("/api/owner/notifications/history")
async def get_notification_history(
    request: Request, user: dict = Depends(get_current_user), limit: int = 50
):
    """
    Get last N notifications sent to the owner.
    Includes error_type, sent_at, bot_id, and bot_name if available.

    Bug #3 fix: Fixed SQL alias and added error handling.
    """
    owner_id = user.get("id")
    pool = request.app.state.db

    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with pool.acquire() as conn:
            # Bug #3 fix: Explicitly qualify all column references to avoid ambiguity
            # Use b.bot_id for bot lookup, en.bot_id for error_notifications
            rows = await conn.fetch(
                """SELECT en.error_type, en.sent_at, en.bot_id, en.owner_id, b.username as bot_name
                   FROM error_notifications en
                   LEFT JOIN bots b ON b.bot_id = en.bot_id
                   WHERE en.owner_id = $1
                   ORDER BY en.sent_at DESC
                   LIMIT $2""",
                owner_id,
                min(limit, 100),  # Max 100
            )

            result = []
            for row in rows:
                result.append(
                    {
                        "error_type": row["error_type"],
                        "sent_at": row["sent_at"].isoformat() if row["sent_at"] else None,
                        "bot_id": row["bot_id"],
                        "bot_name": row["bot_name"] or ("Primary" if row["bot_id"] else None),
                    }
                )

            return {"notifications": result}

    except Exception as e:
        # Bug #3 fix: Return empty list instead of 500 on DB errors
        log.error(f"Failed to get notification history: {e}")
        return {"notifications": []}


def _get_error_category(error_type: str) -> str:
    """Categorize error types for the UI."""
    clone_errors = [
        "PRIVACY_MODE_ON",
        "WEBHOOK_FAILED",
        "WEBHOOK_MISSING_UPDATES",
        "BOT_NOT_ADMIN",
        "BOT_CANT_DELETE",
        "BOT_CANT_RESTRICT",
        "BOT_KICKED",
        "GROUPS_NOT_APPEARING",
        "FED_BAN_PROPAGATION_FAILED",
        "CAPTCHA_WEBAPP_URL_MISSING",
        "INVALID_TOKEN",
    ]
    system_errors = ["MISSING_ENV_VAR", "SUPABASE_CONNECTION_FAILED", "ANALYTICS_ERROR"]
    ml_errors = ["ML_TRAINING_COMPLETE", "ML_TRAINING_FAILED"]

    if error_type in clone_errors:
        return "clone"
    elif error_type in system_errors:
        return "system"
    elif error_type in ml_errors:
        return "ml"
    return "other"
