"""
api/routes/community_vote.py

Community vote configuration API endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_auth
from db.client import db

router = APIRouter(prefix="/api/groups/{chat_id}/community-vote", tags=["community_vote"])
logger = logging.getLogger(__name__)


class VoteSettings(BaseModel):
    enabled: bool = False
    threshold: int = 5
    timeout: int = 10
    action: str = "ban"
    auto_detect_scams: bool = True


@router.get("")
async def get_vote_settings(chat_id: int, user: dict = Depends(require_auth)):
    """Get community vote settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT community_vote_enabled, vote_threshold, vote_timeout,
                          vote_action, auto_detect_scams
                   FROM groups WHERE chat_id = $1""",
                chat_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Group not found")

        return {
            "enabled": row["community_vote_enabled"] if row else False,
            "threshold": row["vote_threshold"] if row else 5,
            "timeout": row["vote_timeout"] if row else 10,
            "action": row["vote_action"] if row else "ban",
            "autoDetectScams": row["auto_detect_scams"] if row else True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get vote settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch vote settings")


@router.post("")
async def save_vote_settings(
    chat_id: int, settings: VoteSettings, user: dict = Depends(require_auth)
):
    """Save community vote settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """UPDATE groups 
                   SET community_vote_enabled = $1, vote_threshold = $2, vote_timeout = $3,
                       vote_action = $4, auto_detect_scams = $5
                   WHERE chat_id = $6""",
                settings.enabled,
                settings.threshold,
                settings.timeout,
                settings.action,
                settings.auto_detect_scams,
                chat_id,
            )

        return {"ok": True, "enabled": settings.enabled}
    except Exception as e:
        logger.error(f"Failed to save vote settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save vote settings")
