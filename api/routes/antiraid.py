"""
api/routes/antiraid.py

REST API for anti-raid management.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from db.client import db
from db.ops.automod import update_group_setting

router = APIRouter(prefix="/api/groups/{chat_id}/antiraid", tags=["antiraid"])
global_router = APIRouter(tags=["antiraid"])
logger = logging.getLogger(__name__)


async def _get_antiraid_settings(chat_id: int) -> dict:
    import json
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
    if not row:
        return {}
    settings = row["settings"] or {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except Exception:
            settings = {}
    return settings


@router.get("")
async def get_antiraid_status(chat_id: int, user: dict = Depends(get_current_user)):
    try:
        settings = await _get_antiraid_settings(chat_id)

        async with db.pool.acquire() as conn:
            active_session = await conn.fetchrow(
                "SELECT * FROM antiraid_sessions WHERE chat_id = $1 AND is_active = TRUE ORDER BY triggered_at DESC LIMIT 1",
                chat_id,
            )
            recent_joins = await conn.fetchval(
                "SELECT COUNT(*) FROM recent_joins WHERE chat_id = $1 AND joined_at > NOW() - INTERVAL '1 minute'",
                chat_id,
            ) or 0

        lockdown_active = bool(active_session)
        threat_level = "low"
        if recent_joins >= 20:
            threat_level = "critical"
        elif recent_joins >= 10:
            threat_level = "high"
        elif recent_joins >= 5:
            threat_level = "medium"

        return {
            "enabled": settings.get("antiraid_enabled", True),
            "threat_level": threat_level,
            "joins_per_minute": recent_joins,
            "lockdown_active": lockdown_active,
            "captcha_active": settings.get("captcha_enabled", False),
            "settings": {
                "antiraid_mode": settings.get("antiraid_mode", "restrict"),
                "antiraid_threshold": settings.get("antiraid_threshold", 10),
                "antiraid_duration_mins": settings.get("antiraid_duration_mins", 30),
                "auto_antiraid_enabled": settings.get("auto_antiraid_enabled", False),
                "auto_antiraid_threshold": settings.get("auto_antiraid_threshold", 15),
                "captcha_enabled": settings.get("captcha_enabled", False),
                "captcha_mode": settings.get("captcha_mode", "button"),
                "captcha_timeout_mins": settings.get("captcha_timeout_mins", 5),
                "captcha_kick_on_timeout": settings.get("captcha_kick_on_timeout", True),
            },
            "active_incident": dict(active_session) if active_session else None,
        }
    except Exception as e:
        logger.error(f"[AntiRaid API] get_antiraid_status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings")
async def update_antiraid_settings(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    valid_keys = [
        "antiraid_enabled", "antiraid_mode", "antiraid_threshold",
        "antiraid_duration_mins", "auto_antiraid_enabled", "auto_antiraid_threshold",
        "captcha_enabled", "captcha_mode", "captcha_timeout_mins", "captcha_kick_on_timeout",
    ]
    try:
        for k in valid_keys:
            if k in body:
                await update_group_setting(db.pool, chat_id, k, body[k])
        return {"ok": True}
    except Exception as e:
        logger.error(f"[AntiRaid API] update_settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lockdown")
async def activate_lockdown(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    try:
        from bot.registry import get_all
        bots = get_all()
        if not bots:
            raise HTTPException(status_code=503, detail="Bot unavailable")

        bot_app = next(iter(bots.values()))
        reason = body.get("reason", "Manual lockdown via Mini App")

        from db.ops.automod import update_group_setting
        await update_group_setting(db.pool, chat_id, "antiraid_enabled", True)

        try:
            await bot_app.bot.set_chat_permissions(
                chat_id,
                permissions={"can_send_messages": False},
            )
        except Exception as tg_err:
            logger.warning(f"[AntiRaid API] Could not set chat permissions: {tg_err}")

        async with db.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO antiraid_sessions (chat_id, triggered_by, join_count) VALUES ($1, $2, 0)",
                chat_id, reason,
            )

        return {"ok": True, "lockdown": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AntiRaid API] activate_lockdown error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/lockdown")
async def deactivate_lockdown(chat_id: int, user: dict = Depends(get_current_user)):
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE antiraid_sessions SET is_active = FALSE WHERE chat_id = $1 AND is_active = TRUE",
                chat_id,
            )

        from bot.registry import get_all
        bots = get_all()
        if bots:
            bot_app = next(iter(bots.values()))
            try:
                from telegram import ChatPermissions
                await bot_app.bot.set_chat_permissions(
                    chat_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_invite_users=True,
                    ),
                )
            except Exception as tg_err:
                logger.warning(f"[AntiRaid API] Could not restore chat permissions: {tg_err}")

        return {"ok": True, "lockdown": False}
    except Exception as e:
        logger.error(f"[AntiRaid API] deactivate_lockdown error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incidents")
async def list_incidents(chat_id: int, page: int = 1, user: dict = Depends(get_current_user)):
    try:
        limit = 20
        offset = (page - 1) * limit
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM antiraid_sessions WHERE chat_id = $1 ORDER BY triggered_at DESC LIMIT $2 OFFSET $3",
                chat_id, limit, offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM antiraid_sessions WHERE chat_id = $1", chat_id
            ) or 0
        return {
            "ok": True,
            "data": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
        }
    except Exception as e:
        logger.error(f"[AntiRaid API] list_incidents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/raiders")
async def list_raiders(chat_id: int, page: int = 1, user: dict = Depends(get_current_user)):
    """List users flagged as raiders for this group."""
    try:
        offset = (page - 1) * 20
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT rm.user_id, rm.username, rm.first_name, rm.joined_at,
                          rm.was_banned, ars.triggered_at as raid_time
                   FROM raid_members rm
                   JOIN antiraid_sessions ars ON rm.session_id = ars.id
                   WHERE ars.chat_id = $1
                   ORDER BY rm.joined_at DESC
                   LIMIT 20 OFFSET $2""",
                chat_id, offset,
            )
            total = await conn.fetchval(
                """SELECT COUNT(*) FROM raid_members rm
                   JOIN antiraid_sessions ars ON rm.session_id = ars.id
                   WHERE ars.chat_id = $1""",
                chat_id,
            ) or 0
        return {
            "ok": True,
            "raiders": [dict(r) for r in rows],
            "total": total,
            "page": page,
        }
    except Exception as e:
        logger.error(f"[AntiRaid API] list_raiders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def antiraid_stats(chat_id: int, user: dict = Depends(get_current_user)):
    try:
        async with db.pool.acquire() as conn:
            total_sessions = await conn.fetchval(
                "SELECT COUNT(*) FROM antiraid_sessions WHERE chat_id = $1", chat_id
            ) or 0
            recent_joins = await conn.fetchval(
                "SELECT COUNT(*) FROM recent_joins WHERE chat_id = $1 AND joined_at > NOW() - INTERVAL '24 hours'",
                chat_id,
            ) or 0
            blocked_joins = await conn.fetchval(
                "SELECT COUNT(*) FROM member_events WHERE chat_id = $1 AND event_type = 'antiraid_block' AND created_at > NOW() - INTERVAL '7 days'",
                chat_id,
            ) or 0

        return {
            "ok": True,
            "total_incidents": total_sessions,
            "joins_last_24h": recent_joins,
            "blocked_last_7d": blocked_joins,
        }
    except Exception as e:
        logger.error(f"[AntiRaid API] antiraid_stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@global_router.get("/api/antiraid/banlist")
async def get_global_banlist(page: int = 1, user: dict = Depends(get_current_user)):
    try:
        offset = (page - 1) * 50
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, flagged_at, flagged_by_chat, reason, is_active
                FROM raid_ban_list
                WHERE is_active = TRUE
                ORDER BY flagged_at DESC
                LIMIT 50 OFFSET $1
                """,
                offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM raid_ban_list WHERE is_active = TRUE"
            ) or 0
        return {
            "ok": True,
            "ban_list": [dict(r) for r in rows],
            "total": total,
            "page": page,
        }
    except Exception as e:
        logger.error(f"[AntiRaid API] get_global_banlist error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@global_router.post("/api/antiraid/banlist")
async def add_to_global_banlist(body: dict, user: dict = Depends(get_current_user)):
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(400, "user_id required")
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO raid_ban_list (user_id, flagged_at, flagged_by_chat, reason, is_active)
                VALUES ($1, NOW(), $2, $3, TRUE)
                ON CONFLICT (user_id) DO UPDATE
                SET is_active = TRUE, reason = EXCLUDED.reason
                """,
                user_id,
                body.get("chat_id"),
                body.get("reason", ""),
            )
        return {"ok": True}
    except Exception as e:
        logger.error(f"[AntiRaid API] add_to_global_banlist error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@global_router.delete("/api/antiraid/banlist/{user_id}")
async def remove_from_global_banlist(user_id: int, user: dict = Depends(get_current_user)):
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE raid_ban_list SET is_active = FALSE WHERE user_id = $1", user_id
            )
        return {"ok": True}
    except Exception as e:
        logger.error(f"[AntiRaid API] remove_from_global_banlist error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
