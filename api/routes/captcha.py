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
from config import settings

router = APIRouter(prefix="/api/groups/{chat_id}/captcha", tags=["captcha"])
logger = logging.getLogger(__name__)


class CaptchaSettings(BaseModel):
    enabled: bool = False
    # Accepted modes: button, math, text (classic)
    # WebApp modes: emoji, word_scramble, odd_one_out, number_sequence, webapp
    type: str = "button"
    timeout: int = 300  # seconds
    kick_failures: int = 3  # max failed attempts before kick


@router.get("")
async def get_captcha_settings(chat_id: int, user: dict = Depends(require_auth)):
    """Get captcha settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT captcha_enabled, captcha_mode, captcha_timeout_mins, captcha_max_attempts
                   FROM groups WHERE chat_id = $1""",
                chat_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Group not found")

        return {
            "enabled": row["captcha_enabled"] if row else False,
            "type": row["captcha_mode"] if row else "button",
            "timeout": (row["captcha_timeout_mins"] or 5) * 60,
            "kick_failures": row["captcha_max_attempts"] if row else 3,
            "has_external_url": bool(settings.RENDER_EXTERNAL_URL),
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
                   SET captcha_enabled = $1, captcha_mode = $2, captcha_timeout_mins = $3, captcha_max_attempts = $4
                   WHERE chat_id = $5""",
                settings.enabled,
                settings.type,
                max(1, settings.timeout // 60),
                settings.kick_failures,
                chat_id,
            )

        return {
            "ok": True,
            "enabled": settings.enabled,
            "type": settings.type,
            "timeout": settings.timeout,
            "kick_failures": settings.kick_failures,
        }
    except Exception as e:
        logger.error(f"Failed to save captcha settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save captcha settings")
