"""
api/routes/bots.py

API routes for bot management.
All routes require authentication via get_current_user.
"""

import asyncio
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List

from api.auth import get_current_user
from bot.registry import register as registry_register, deregister as registry_deregister, get as registry_get
from bot.factory import create_application
from bot.utils.crypto import encrypt_token, hash_token, mask_token, validate_token_format, decrypt_token
from db.ops.bots import (
    get_bot_by_id, get_bot_by_token_hash,
    get_bots_by_owner, insert_bot,
    update_bot_status, delete_bot,
    count_recent_clone_attempts, log_clone_attempt
)
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots", tags=["bots"])

CLONE_RATE_LIMIT = 5


@router.get("")
async def list_bots(user: dict = Depends(get_current_user)):
    """Get all bots owned by the authenticated user."""
    from db.client import db
    
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    user_id = user.get("id")
    bots = await get_bots_by_owner(db.pool, user_id)
    
    # Filter sensitive fields
    for bot in bots:
        bot.pop("token_encrypted", None)
        bot.pop("token_hash", None)
    
    return bots


@router.post("/clone")
async def clone_bot(request: Request, user: dict = Depends(get_current_user)):
    """
    Clone a new bot by providing a token.
    Runs the same 5-layer validation as the conversational flow.
    """
    from db.client import db
    
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    user_id = user.get("id")
    
    # Access control
    if settings.CLONE_ACCESS == "owner_only" and user_id != settings.OWNER_ID:
        raise HTTPException(status_code=403, detail={"error": "Cloning is restricted to the bot owner", "code": "ACCESS_DENIED"})
    
    body = await request.json()
    token = body.get("token", "").strip()
    
    if not token:
        raise HTTPException(status_code=400, detail={"error": "Token is required", "code": "MISSING_TOKEN"})
    
    # Layer 1: Rate limit
    attempts = await count_recent_clone_attempts(db.pool, user_id, window_minutes=60)
    if attempts >= CLONE_RATE_LIMIT:
        await log_clone_attempt(db.pool, user_id, False, "rate_limited")
        raise HTTPException(status_code=429, detail={"error": f"Max {CLONE_RATE_LIMIT} attempts per hour", "code": "RATE_LIMITED"})
    
    # Layer 2: Format check
    if not validate_token_format(token):
        await log_clone_attempt(db.pool, user_id, False, "invalid_format")
        raise HTTPException(status_code=400, detail={"error": "Invalid token format", "code": "INVALID_FORMAT"})
    
    # Layer 3: Deduplication
    token_hash = hash_token(token)
    existing = await get_bot_by_token_hash(db.pool, token_hash)
    if existing:
        reason = "already_registered_dead" if existing["status"] == "dead" else "already_registered"
        await log_clone_attempt(db.pool, user_id, False, reason, token_hash)
        raise HTTPException(status_code=409, detail={"error": "Token already registered", "code": reason})
    
    # Layer 4: Live Telegram validation
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            tg_data = resp.json()
    except httpx.TimeoutException:
        await log_clone_attempt(db.pool, user_id, False, "telegram_timeout", token_hash)
        raise HTTPException(status_code=503, detail={"error": "Telegram API timeout", "code": "TIMEOUT"})
    except Exception as e:
        await log_clone_attempt(db.pool, user_id, False, f"network_error: {e}", token_hash)
        raise HTTPException(status_code=503, detail={"error": "Network error", "code": "NETWORK_ERROR"})
    
    if not tg_data.get("ok"):
        err_desc = tg_data.get("description", "Unknown error")
        await log_clone_attempt(db.pool, user_id, False, f"telegram_rejected: {err_desc}", token_hash)
        raise HTTPException(status_code=400, detail={"error": f"Telegram rejected token: {err_desc}", "code": "TELEGRAM_REJECTED"})
    
    bot_info = tg_data["result"]
    cloned_bot_id = bot_info["id"]
    cloned_username = bot_info["username"]
    cloned_name = bot_info["first_name"]
    
    # Step 1: Clear any pre-existing webhook
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook", json={"drop_pending_updates": True})
    
    # Step 2: Save to DB
    render_url = settings.RENDER_EXTERNAL_URL
    webhook_url = f"{render_url}/webhook/{cloned_bot_id}"
    
    await insert_bot(db.pool, {
        "bot_id": cloned_bot_id,
        "username": cloned_username,
        "display_name": cloned_name,
        "token_encrypted": encrypt_token(token),
        "token_hash": token_hash,
        "owner_user_id": user_id,
        "webhook_url": webhook_url,
        "is_primary": False,
        "status": "active",
        "webhook_active": False,
    })
    
    # Step 3: Register webhook with retries
    webhook_ok = False
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                wh_resp = await client.post(
                    f"https://api.telegram.org/bot{token}/setWebhook",
                    json={
                        "url": webhook_url,
                        "allowed_updates": ["message", "callback_query", "chat_member", "new_chat_members"],
                        "drop_pending_updates": True
                    }
                )
                wh_data = wh_resp.json()
                if wh_data.get("ok"):
                    webhook_ok = True
                    break
        except Exception as e:
            logger.warning(f"[API] setWebhook attempt {attempt} failed: {e}")
        
        await asyncio.sleep(5)
    
    if not webhook_ok:
        await update_bot_status(db.pool, cloned_bot_id, "active", webhook_active=False)
        raise HTTPException(status_code=500, detail={"error": "Webhook registration failed", "code": "WEBHOOK_FAILED"})
    
    await update_bot_status(db.pool, cloned_bot_id, "active", webhook_active=True)
    
    # Step 4: Spin up PTB Application
    clone_app = create_application(token, is_primary=False)
    clone_app.bot_data["db_pool"] = db.pool
    await clone_app.initialize()
    await clone_app.start()
    await registry_register(cloned_bot_id, clone_app)
    
    await log_clone_attempt(db.pool, user_id, True, None, token_hash)
    
    return {
        "bot_id": cloned_bot_id,
        "username": cloned_username,
        "display_name": cloned_name,
        "status": "active",
        "webhook_url": webhook_url
    }


@router.delete("/{bot_id}")
async def delete_bot_route(bot_id: int, user: dict = Depends(get_current_user)):
    """Delete a bot clone."""
    from db.client import db
    
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    user_id = user.get("id")
    
    bot_record = await get_bot_by_id(db.pool, bot_id)
    
    if not bot_record:
        raise HTTPException(status_code=404, detail={"error": "Bot not found"})
    
    if bot_record["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail={"error": "Not authorized"})
    
    if bot_record.get("is_primary"):
        raise HTTPException(status_code=403, detail={"error": "Cannot delete primary bot"})
    
    # Full teardown
    token = decrypt_token(bot_record["token_encrypted"])
    
    # 1. Delete webhook
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook", json={"drop_pending_updates": True})
    except Exception as e:
        logger.warning(f"[API] deleteWebhook failed: {e}")
    
    # 2. Deregister
    await registry_deregister(bot_id)
    
    # 3. Delete from DB
    await delete_bot(db.pool, bot_id)
    
    return {"status": "deleted", "bot_id": bot_id}


@router.get("/{bot_id}/status")
async def get_bot_status(bot_id: int, user: dict = Depends(get_current_user)):
    """Get live status of a bot."""
    from db.client import db
    
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    user_id = user.get("id")
    
    bot_record = await get_bot_by_id(db.pool, bot_id)
    
    if not bot_record:
        raise HTTPException(status_code=404, detail={"error": "Bot not found"})
    
    if bot_record["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail={"error": "Not authorized"})
    
    # Get live webhook info from Telegram
    token = decrypt_token(bot_record["token_encrypted"])
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getWebhookInfo")
            webhook_info = resp.json().get("result", {})
    except Exception as e:
        webhook_info = {"error": str(e)}
    
    return {
        "webhook_url": webhook_info.get("url"),
        "pending_update_count": webhook_info.get("pending_update_count"),
        "last_error_message": webhook_info.get("last_error_message"),
        "last_error_date": webhook_info.get("last_error_date"),
        "is_in_registry": registry_get(bot_id) is not None,
        "db_status": bot_record["status"]
    }


@router.post("/{bot_id}/reauth")
async def reauth_bot(bot_id: int, request: Request, user: dict = Depends(get_current_user)):
    """Re-authenticate a dead bot with a new token."""
    from db.client import db
    
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    user_id = user.get("id")
    
    bot_record = await get_bot_by_id(db.pool, bot_id)
    
    if not bot_record:
        raise HTTPException(status_code=404, detail={"error": "Bot not found"})
    
    if bot_record["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail={"error": "Not authorized"})
    
    body = await request.json()
    new_token = body.get("token", "").strip()
    
    if not new_token:
        raise HTTPException(status_code=400, detail={"error": "Token is required"})
    
    # Validate new token
    if not validate_token_format(new_token):
        raise HTTPException(status_code=400, detail={"error": "Invalid token format"})
    
    # Verify with Telegram
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{new_token}/getMe")
            tg_data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail={"error": "Telegram API error"})
    
    if not tg_data.get("ok"):
        raise HTTPException(status_code=400, detail={"error": "Token rejected by Telegram"})
    
    bot_info = tg_data["result"]
    if bot_info["id"] != bot_id:
        raise HTTPException(status_code=400, detail={"error": "Token bot_id doesn't match"})
    
    # Update DB with new token
    new_token_hash = hash_token(new_token)
    await db.pool.execute(
        "UPDATE bots SET token_encrypted = $1, token_hash = $2, status = 'active', death_reason = NULL WHERE bot_id = $3",
        encrypt_token(new_token),
        new_token_hash,
        bot_id
    )
    
    # Re-register webhook
    render_url = settings.RENDER_EXTERNAL_URL
    webhook_url = f"{render_url}/webhook/{bot_id}"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(f"https://api.telegram.org/bot{new_token}/setWebhook", json={"url": webhook_url})
        await update_bot_status(db.pool, bot_id, "active", webhook_active=True)
    except Exception as e:
        await update_bot_status(db.pool, bot_id, "active", webhook_active=False)
    
    return {"status": "reauthenticated", "bot_id": bot_id}


@router.get("/{bot_id}/groups")
async def get_bot_groups(bot_id: int, user: dict = Depends(get_current_user)):
    """Get all groups managed by a specific bot."""
    from db.client import db
    
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    user_id = user.get("id")
    
    bot_record = await get_bot_by_id(db.pool, bot_id)
    
    if not bot_record:
        raise HTTPException(status_code=404, detail={"error": "Bot not found"})
    
    if bot_record["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail={"error": "Not authorized"})
    
    # Get groups for this bot using token_hash
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT chat_id, title, member_count, last_active FROM groups WHERE bot_token_hash = $1",
            bot_record["token_hash"]
        )
    
    return [dict(r) for r in rows]
