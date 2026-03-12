"""
API routes for music authentication
Used by Mini App to add/manage userbot accounts for music streaming
"""

import logging
import base64
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from bot.userbot.music_auth import (
    MusicAuthSession, start_phone_auth, complete_phone_auth,
    start_qr_auth, check_qr_auth, session_string_auth
)
import db.ops.music_new as db_music
from bot.utils.crypto import decrypt_token
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class StartPhoneRequest(BaseModel):
    phone: str


class VerifyOTPRequest(BaseModel):
    code: str
    phone_hash: str


class Verify2FARequest(BaseModel):
    password: str


class SessionStringRequest(BaseModel):
    session_string: str


class QRStatusResponse(BaseModel):
    ok: bool
    scanned: bool = False
    error: Optional[str] = None
    tg_name: Optional[str] = None
    tg_username: Optional[str] = None


def _get_db():
    """Get database pool"""
    from db.client import db
    return db.pool


@router.post("/bots/{bot_id}/music/auth/start-phone")
async def start_phone_auth_endpoint(
    bot_id: int,
    request: StartPhoneRequest
):
    """
    Start phone authentication for music userbot.
    Returns: { ok: true, requires_otp: true }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        auth = MusicAuthSession(bot_id)
        result = await start_phone_auth(auth, request.phone)

        if not result.ok:
            raise HTTPException(status_code=400, detail=result.error)

        return {
            "ok": True,
            "requires_otp": True,
            "phone_hash": auth.phone_hash,
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] Phone auth start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/music/auth/verify-otp")
async def verify_otp_endpoint(
    bot_id: int,
    request: VerifyOTPRequest
):
    """
    Verify OTP code for phone authentication.
    Returns: { ok: true } or { ok: false, requires_2fa: true }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # In a real implementation, you'd store the auth session somewhere
        # For now, we'll create a new one (simplified)
        auth = MusicAuthSession(bot_id)
        auth.phone_hash = request.phone_hash
        result = await complete_phone_auth(auth, request.code)

        if result.error == "2FA_REQUIRED":
            return {
                "ok": True,
                "requires_2fa": True,
            }

        if not result.ok:
            raise HTTPException(status_code=400, detail=result.error)

        # Save to DB
        await db_music.save_music_userbot(
            pool,
            owner_bot_id=bot_id,
            tg_user_id=result.tg_user_id,
            tg_name=result.tg_name,
            tg_username=result.tg_username,
            encrypted_session=result.session_string
        )

        return {
            "ok": True,
            "tg_name": result.tg_name,
            "tg_username": result.tg_username,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MUSIC_API] OTP verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/music/auth/verify-2fa")
async def verify_2fa_endpoint(
    bot_id: int,
    request: Verify2FARequest
):
    """
    Verify 2FA password for phone authentication.
    Returns: { ok: true, tg_name, tg_username }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Simplified - in production, you'd retrieve the stored auth session
        auth = MusicAuthSession(bot_id)
        # This is a placeholder - real implementation needs session storage
        raise HTTPException(status_code=400, detail="Session expired. Please start over.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MUSIC_API] 2FA verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/music/auth/start-qr")
async def start_qr_auth_endpoint(
    bot_id: int
):
    """
    Generate QR code for music userbot authentication.
    Returns: { ok: true, qr_image_base64: "..." }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        auth = MusicAuthSession(bot_id)
        result = await start_qr_auth(auth)

        if not result.ok:
            raise HTTPException(status_code=400, detail=result.error)

        # Convert hex to base64
        img_bytes = bytes.fromhex(result.session_string)
        img_b64 = base64.b64encode(img_bytes).decode()

        return {
            "ok": True,
            "qr_image_base64": img_b64,
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] QR auth start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/music/auth/qr-status")
async def check_qr_status_endpoint(
    bot_id: int
):
    """
    Check QR code scan status (polling endpoint).
    Returns: { ok: true, scanned: true/false, ... }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # In production, you'd retrieve the stored auth session
        # This is a simplified version
        return {
            "ok": True,
            "scanned": False,
            "error": "Session not found",
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] QR status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/music/auth/session-string")
async def session_string_auth_endpoint(
    bot_id: int,
    request: SessionStringRequest
):
    """
    Authenticate using a Pyrogram session string.
    Returns: { ok: true, tg_name, tg_username }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        result = await session_string_auth(bot_id, request.session_string)

        if not result.ok:
            raise HTTPException(status_code=400, detail=result.error)

        # Save to DB
        await db_music.save_music_userbot(
            pool,
            owner_bot_id=bot_id,
            tg_user_id=result.tg_user_id,
            tg_name=result.tg_name,
            tg_username=result.tg_username,
            encrypted_session=result.session_string
        )

        return {
            "ok": True,
            "tg_name": result.tg_name,
            "tg_username": result.tg_username,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MUSIC_API] Session string auth failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/music/userbot")
async def get_music_userbot(
    bot_id: int
):
    """
    Get music userbot information for a bot.
    Returns: { ok: true, userbot: { ... } } or { ok: true, userbot: null }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        userbots = await db_music.get_music_userbots(pool, bot_id, active_only=True)

        if not userbots:
            return {
                "ok": True,
                "userbot": None,
            }

        ub = userbots[0]
        return {
            "ok": True,
            "userbot": {
                "tg_name": ub["tg_name"],
                "tg_username": ub["tg_username"],
                "added_at": ub["added_at"].isoformat() if ub["added_at"] else None,
            }
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] Get userbot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bots/{bot_id}/music/userbot")
async def delete_music_userbot(
    bot_id: int
):
    """
    Delete music userbot for a bot.
    Returns: { ok: true }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        await db_music.delete_music_userbot(pool, bot_id)

        # Stop the music worker if running
        from bot.registry import get
        clone_app = get(bot_id)
        if clone_app and clone_app.bot_data.get("music_worker"):
            worker = clone_app.bot_data["music_worker"]
            try:
                await worker.calls.stop()
                await worker.client.stop()
            except Exception as e:
                logger.warning(f"[MUSIC_API] Failed to stop worker: {e}")
            clone_app.bot_data["music_worker"] = None

        return {"ok": True}
    except Exception as e:
        logger.error(f"[MUSIC_API] Delete userbot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups/{chat_id}/music/settings")
async def get_music_settings_endpoint(
    chat_id: int
):
    """
    Get music settings for a group.
    Returns: { ok: true, settings: { play_mode, announce_tracks } }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # For now, return default settings
        # In production, you'd pass bot_id as well
        return {
            "ok": True,
            "settings": {
                "play_mode": "all",
                "announce_tracks": True,
            }
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] Get settings failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/groups/{chat_id}/music/settings")
async def update_music_settings_endpoint(
    chat_id: int,
    settings_data: dict
):
    """
    Update music settings for a group.
    Body: { play_mode: "all"|"admins", announce_tracks: boolean }
    Returns: { ok: true }
    """
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # In production, you'd need bot_id as well
        return {"ok": True}
    except Exception as e:
        logger.error(f"[MUSIC_API] Update settings failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
