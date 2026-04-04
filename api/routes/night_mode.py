"""
api/routes/night_mode.py

Night mode / scheduled restrictions API endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_auth
from db.client import db

router = APIRouter(prefix="/api/groups/{chat_id}/night-mode", tags=["night_mode"])
logger = logging.getLogger(__name__)


class NightModeSettings(BaseModel):
    enabled: bool = False
    start_time: str = Field("23:00", alias="startTime")
    end_time: str = Field("07:00", alias="endTime")
    timezone: str = "UTC"
    night_message: Optional[str] = Field(None, alias="nightMessage")
    morning_message: Optional[str] = Field(None, alias="morningMessage")

    class Config:
        populate_by_name = True
        extra = "ignore"


@router.get("")
async def get_night_mode_settings(chat_id: int, user: dict = Depends(require_auth)):
    """Get night mode settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT night_mode_enabled, night_mode_start, night_mode_end,
                          night_mode_tz, night_message, morning_message
                   FROM groups WHERE chat_id = $1""",
                chat_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Group not found")

        return {
            "enabled": row["night_mode_enabled"] if row else False,
            "startTime": row["night_mode_start"] if row else "23:00",
            "endTime": row["night_mode_end"] if row else "07:00",
            "timezone": row["night_mode_tz"] if row else "UTC",
            "nightMessage": row["night_message"],
            "morningMessage": row["morning_message"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get night mode settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch night mode settings")


@router.post("")
async def save_night_mode_settings(
    chat_id: int, settings: NightModeSettings, user: dict = Depends(require_auth)
):
    """Save night mode settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """UPDATE groups 
                   SET night_mode_enabled = $1, night_mode_start = $2, night_mode_end = $3,
                       night_mode_tz = $4, night_message = $5, morning_message = $6
                   WHERE chat_id = $7""",
                settings.enabled,
                settings.start_time,
                settings.end_time,
                settings.timezone,
                settings.night_message,
                settings.morning_message,
                chat_id,
            )

        return {"ok": True, "enabled": settings.enabled}
    except Exception as e:
        logger.error(f"Failed to save night mode settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save night mode settings")
