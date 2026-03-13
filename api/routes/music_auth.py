"""
API routes for music authentication
Used by Mini App to add/manage userbot accounts for music streaming
"""

import logging
import base64
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from bot.userbot.music_auth import (
    MusicAuthSession, start_phone_auth, complete_phone_auth,
    start_qr_auth, check_qr_auth, session_string_auth
)
import db.ops.music_new as db_music
from bot.utils.crypto import decrypt_token
from config import settings
from api.auth import get_current_user

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


class UpdateRiskFeeRequest(BaseModel):
    userbot_id: int
    risk_fee: int


class BanUserbotRequest(BaseModel):
    userbot_id: int
    ban_reason: Optional[str] = None


def _get_db():
    """Get database pool"""
    from db.client import db
    return db.pool


async def _verify_bot_owner(bot_id: int, user: dict):
    """Verify that the user owns the bot"""
    from db.ops.bots import get_bot_by_id
    
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Get bot and verify ownership
    bot = await get_bot_by_id(pool, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    if bot["owner_user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")


# Global store for in-progress auth sessions
# user_id -> MusicAuthSession
_auth_sessions = {}


@router.post("/bots/{bot_id}/music/auth/start-phone")
async def start_phone_auth_endpoint(
    bot_id: int,
    request: StartPhoneRequest,
    user: dict = Depends(get_current_user)
):
    """
    Start phone authentication for music userbot.
    Returns: { ok: true, requires_otp: true }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        auth = MusicAuthSession(bot_id)
        result = await start_phone_auth(auth, request.phone)

        if not result.ok:
            raise HTTPException(status_code=400, detail=result.error)

        _auth_sessions[user["id"]] = auth
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
    request: VerifyOTPRequest,
    user: dict = Depends(get_current_user)
):
    """
    Verify OTP code for phone authentication.
    Returns: { ok: true } or { ok: false, requires_2fa: true }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        auth = _auth_sessions.get(user["id"])
        if not auth or auth.owner_bot_id != bot_id:
            raise HTTPException(status_code=400, detail="Session expired. Please start over.")

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
            encrypted_session=result.session_string,
            phone=auth.phone
        )

        del _auth_sessions[user["id"]]
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
    request: Verify2FARequest,
    user: dict = Depends(get_current_user)
):
    """
    Verify 2FA password for phone authentication.
    Returns: { ok: true, tg_name, tg_username }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        auth = _auth_sessions.get(user["id"])
        if not auth or auth.owner_bot_id != bot_id:
            raise HTTPException(status_code=400, detail="Session expired. Please start over.")

        result = await complete_phone_auth(auth, "", password=request.password)

        if not result.ok:
            raise HTTPException(status_code=400, detail=result.error)

        # Save to DB
        await db_music.save_music_userbot(
            pool,
            owner_bot_id=bot_id,
            tg_user_id=result.tg_user_id,
            tg_name=result.tg_name,
            tg_username=result.tg_username,
            encrypted_session=result.session_string,
            phone=auth.phone
        )

        del _auth_sessions[user["id"]]
        return {
            "ok": True,
            "tg_name": result.tg_name,
            "tg_username": result.tg_username,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MUSIC_API] 2FA verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/music/auth/start-qr")
async def start_qr_auth_endpoint(
    bot_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Generate QR code for music userbot authentication.
    Returns: { ok: true, qr_image_base64: "..." }
    """
    await _verify_bot_owner(bot_id, user)
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

        _auth_sessions[user["id"]] = auth
        return {
            "ok": True,
            "qr_image_base64": img_b64,
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] QR auth start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/music/auth/qr-status")
async def check_qr_status_endpoint(
    bot_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Check QR code scan status (polling endpoint).
    Returns: { ok: true, scanned: true/false, ... }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        auth = _auth_sessions.get(user["id"])
        if not auth or auth.owner_bot_id != bot_id or auth.method != "qr":
            return {
                "ok": False,
                "error": "Session not found",
            }

        # Non-blocking check
        result = await check_qr_auth(auth, timeout=1)

        if result.ok:
            # Save to DB
            await db_music.save_music_userbot(
                pool,
                owner_bot_id=bot_id,
                tg_user_id=result.tg_user_id,
                tg_name=result.tg_name,
                tg_username=result.tg_username,
                encrypted_session=result.session_string
            )
            del _auth_sessions[user["id"]]
            return {
                "ok": True,
                "scanned": True,
                "tg_name": result.tg_name,
                "tg_username": result.tg_username,
            }
        
        if result.error == "QR expired. Try again.":
             del _auth_sessions[user["id"]]
             return {
                 "ok": False,
                 "error": "QR Expired",
             }

        return {
            "ok": True,
            "scanned": False,
        }
    except Exception as e:
        logger.debug(f"[MUSIC_API] QR status check: {e}")
        return {
            "ok": True,
            "scanned": False,
        }



@router.post("/bots/{bot_id}/music/auth/session-string")
async def session_string_auth_endpoint(
    bot_id: int,
    request: SessionStringRequest,
    user: dict = Depends(get_current_user)
):
    """
    Authenticate using a Pyrogram session string.
    Returns: { ok: true, tg_name, tg_username }
    """
    await _verify_bot_owner(bot_id, user)
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


@router.get("/bots/{bot_id}/music/userbots")
async def get_music_userbots(
    bot_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Get all music userbot accounts for a bot.
    Returns: { ok: true, userbots: [{ id, tg_name, tg_username, risk_fee, is_banned, added_at, ... }] }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        userbots = await db_music.get_music_userbots(pool, bot_id, active_only=False)

        return {
            "ok": True,
            "userbots": [{
                "id": ub["id"],
                "tg_name": ub["tg_name"],
                "tg_username": ub["tg_username"],
                "risk_fee": ub.get("risk_fee", 0),
                "is_banned": ub.get("is_banned", False),
                "ban_reason": ub.get("ban_reason"),
                "is_active": ub["is_active"],
                "added_at": ub["added_at"].isoformat() if ub["added_at"] else None,
                "last_used_at": ub["last_used_at"].isoformat() if ub.get("last_used_at") else None,
            } for ub in userbots]
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] Get userbots failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/music/userbot")
async def get_music_userbot(
    bot_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Get music userbot information for a bot (legacy single userbot endpoint).
    Returns: { ok: true, userbot: { ... } } or { ok: true, userbot: null }
    """
    await _verify_bot_owner(bot_id, user)
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
                "id": ub["id"],
                "tg_name": ub["tg_name"],
                "tg_username": ub["tg_username"],
                "added_at": ub["added_at"].isoformat() if ub["added_at"] else None,
            }
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] Get userbot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/bots/{bot_id}/music/userbot/risk-fee")
async def update_userbot_risk_fee(
    bot_id: int,
    request: UpdateRiskFeeRequest,
    user: dict = Depends(get_current_user)
):
    """
    Update risk fee for a specific userbot.
    Returns: { ok: true }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        await db_music.update_userbot_risk_fee(
            pool, bot_id, request.userbot_id, request.risk_fee
        )
        return {"ok": True}
    except Exception as e:
        logger.error(f"[MUSIC_API] Update risk fee failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/music/userbot/ban")
async def ban_userbot_endpoint(
    bot_id: int,
    request: BanUserbotRequest,
    user: dict = Depends(get_current_user)
):
    """
    Ban a userbot for risk fee non-payment.
    Returns: { ok: true }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        await db_music.ban_userbot(
            pool, bot_id, request.userbot_id, request.ban_reason
        )
        return {"ok": True}
    except Exception as e:
        logger.error(f"[MUSIC_API] Ban userbot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bots/{bot_id}/music/userbot/unban")
async def unban_userbot_endpoint(
    bot_id: int,
    request: BanUserbotRequest,
    user: dict = Depends(get_current_user)
):
    """
    Unban a userbot.
    Returns: { ok: true }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        await db_music.unban_userbot(pool, bot_id, request.userbot_id)
        return {"ok": True}
    except Exception as e:
        logger.error(f"[MUSIC_API] Unban userbot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bots/{bot_id}/music/userbot/{userbot_id}")
async def delete_music_userbot(
    bot_id: int,
    userbot_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Delete a specific music userbot.
    Returns: { ok: true }
    """
    await _verify_bot_owner(bot_id, user)
    pool = _get_db()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        await db_music.delete_music_userbot(pool, bot_id, userbot_id)

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


@router.delete("/bots/{bot_id}/music/userbot")
async def delete_all_music_userbots(
    bot_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Delete all music userbots for a bot.
    Returns: { ok: true }
    """
    await _verify_bot_owner(bot_id, user)
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
        logger.error(f"[MUSIC_API] Delete userbots failed: {e}")
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
