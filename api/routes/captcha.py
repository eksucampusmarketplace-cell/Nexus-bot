"""
api/routes/captcha.py

Captcha configuration API endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_auth
from db.client import db

router = APIRouter(prefix="/api/groups/{chat_id}/captcha", tags=["captcha"])
logger = logging.getLogger(__name__)


class CaptchaSettings(BaseModel):
    enabled: bool = False
    type: str = "button"  # button, math, word
    timeout: int = 300  # seconds


@router.get("")
async def get_captcha_settings(chat_id: int, user: dict = Depends(require_auth)):
    """Get captcha settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT captcha_enabled, captcha_mode, captcha_timeout_mins
                   FROM groups WHERE chat_id = $1""",
                chat_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Group not found")

        return {
            "enabled": row["captcha_enabled"] if row else False,
            "type": row["captcha_mode"] if row else "button",
            "timeout": (row["captcha_timeout_mins"] or 5) * 60,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get captcha settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch captcha settings")


@router.post("")
async def save_captcha_settings(
    chat_id: int, settings: CaptchaSettings, user: dict = Depends(require_auth)
):
    """Save captcha settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """UPDATE groups 
                   SET captcha_enabled = $1, captcha_mode = $2, captcha_timeout_mins = $3
                   WHERE chat_id = $4""",
                settings.enabled,
                settings.type,
                max(1, settings.timeout // 60),
                chat_id,
            )

        return {
            "ok": True,
            "enabled": settings.enabled,
            "type": settings.type,
            "timeout": settings.timeout,
        }
    except Exception as e:
        logger.error(f"Failed to save captcha settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save captcha settings")
