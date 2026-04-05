"""
api/routes/name_history.py

Name history (Sangmata) API endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_auth
from db.client import db

router = APIRouter(prefix="/api/groups/{chat_id}/name-history", tags=["name_history"])
logger = logging.getLogger(__name__)


class HistorySettings(BaseModel):
    enabled: bool = False
    limit: int = 10


@router.get("")
async def get_history_settings(chat_id: int, user: dict = Depends(require_auth)):
    """Get name history settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT name_history_enabled, name_history_limit
                   FROM groups WHERE chat_id = $1""",
                chat_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Group not found")

        return {
            "enabled": row["name_history_enabled"] if row else False,
            "limit": row["name_history_limit"] if row else 10,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get history settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history settings")


@router.post("")
async def save_history_settings(
    chat_id: int, settings: HistorySettings, user: dict = Depends(require_auth)
):
    """Save name history settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """UPDATE groups 
                   SET name_history_enabled = $1, name_history_limit = $2
                   WHERE chat_id = $3""",
                settings.enabled,
                settings.limit,
                chat_id,
            )

        return {"ok": True, "enabled": settings.enabled, "limit": settings.limit}
    except Exception as e:
        logger.error(f"Failed to save history settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save history settings")


@router.get("/recent")
async def get_recent_name_changes(chat_id: int, user: dict = Depends(require_auth)):
    """Get recent name changes for a group."""
    try:
        async with db.pool.acquire() as conn:
            # Check if history tracking is enabled
            enabled = await conn.fetchval(
                "SELECT name_history_enabled FROM groups WHERE chat_id = $1", chat_id
            )

            if not enabled:
                return []

            # Get the configured limit (NH-03 fix: honor the configured limit, not hardcoded 20)
            limit_val = await conn.fetchval(
                "SELECT COALESCE(name_history_limit, 20) FROM groups WHERE chat_id = $1",
                chat_id,
            )

            # Get recent name changes with proper old/new name fields
            # NH-03 fix: include username-only changes (WHERE old_first_name OR old_username)
            # NH-03 fix: use username as fallback when first_name is empty
            rows = await conn.fetch(
                """SELECT uhh.user_id,
                          CASE
                            WHEN uhh.last_name IS NOT NULL AND uhh.last_name != '' 
                            THEN COALESCE(NULLIF(uhh.first_name,''), uhh.username, 'Unknown') || ' ' || uhh.last_name
                            ELSE COALESCE(NULLIF(uhh.first_name,''), uhh.username, 'Unknown')
                          END as user_name,
                          CASE
                            WHEN uhh.old_last_name IS NOT NULL AND uhh.old_last_name != '' 
                            THEN COALESCE(uhh.old_first_name, '') || ' ' || COALESCE(uhh.old_last_name, '')
                            ELSE COALESCE(uhh.old_first_name, '')
                          END as old_name,
                          uhh.old_username,
                          uhh.username,
                          uhh.changed_at
                   FROM user_name_history uhh
                   WHERE uhh.source_chat_id = $1
                     AND (uhh.old_first_name IS NOT NULL OR uhh.old_username IS NOT NULL)
                   ORDER BY uhh.changed_at DESC
                   LIMIT $2""",
                chat_id,
                limit_val,
            )

        return [
            {
                "user_id": r["user_id"],
                "user_name": r["user_name"] or r["username"] or "Unknown",
                "old_name": r["old_name"] or r["old_username"] or "",
                "changed_at": r["changed_at"].isoformat() if r["changed_at"] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get recent name changes: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch name history")
