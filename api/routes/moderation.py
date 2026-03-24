import logging
import time
from functools import lru_cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db.ops.moderation as mod_db
from api.auth import get_current_user
from bot.handlers.moderation.utils import publish_event
from db.client import db

router = APIRouter(prefix="/api/groups/{chat_id}", tags=["moderation"])
logger = logging.getLogger(__name__)

# Cache for admin verification: {chat_id:user_id} -> (timestamp, is_admin)
_admin_cache = {}
ADMIN_CACHE_TTL = 60  # 60 seconds


async def verify_admin(chat_id: int, user: dict):
    from config import settings as _cfg

    user_id = user.get("id")
    if user_id and user_id == _cfg.OWNER_ID:
        return
    if not user_id:
        raise HTTPException(403, "Not authenticated")

    cache_key = f"{chat_id}:{user_id}"
    now = time.time()

    # Check cache
    if cache_key in _admin_cache:
        cached_time, is_admin = _admin_cache[cache_key]
        if now - cached_time < ADMIN_CACHE_TTL:
            if not is_admin:
                raise HTTPException(403, "You are not an admin of this group")
            return

    from bot.registry import get_all

    bots = get_all()
    if not bots:
        raise HTTPException(503, "Bot unavailable")
    for bot_id, app in bots.items():
        try:
            member = await app.bot.get_chat_member(chat_id, user_id)
            if member.status in ("administrator", "creator"):
                _admin_cache[cache_key] = (now, True)
                return
        except Exception as e:
            logger.warning(f'[verify_admin] bot {bot_id} failed chat={chat_id} user={user_id}: {e}')
            continue

    # DB fallback: check if user owns the bot associated with this group
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT owner_user_id FROM bots WHERE token_hash = "
            "(SELECT bot_token_hash FROM groups WHERE chat_id=$1)",
            chat_id,
        )
        if row and row["owner_user_id"] == user_id:
            logger.info(f'[verify_admin] Allowing owner {user_id} via DB fallback')
            return  # owner always passes

    raise HTTPException(403, "Could not verify admin status — ensure bot is admin in group")


class BanRequest(BaseModel):
    user_id: int
    reason: str
    duration: Optional[str] = None


class MuteRequest(BaseModel):
    user_id: int
    reason: Optional[str] = None
    duration: Optional[str] = "1h"


class WarnRequest(BaseModel):
    user_id: int
    reason: Optional[str] = None


class KickRequest(BaseModel):
    user_id: int
    reason: Optional[str] = None


class BulkActionRequest(BaseModel):
    user_ids: List[int]
    action: str
    duration: Optional[str] = None
    reason: Optional[str] = None


@router.post("/bans")
async def ban_user(chat_id: int, req: BanRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    from bot.registry import get_all

    bots = get_all()
    if not bots:
        raise HTTPException(503, "Bot not running — cannot execute action")

    admin_name = user.get("first_name", "Admin")
    reason = req.reason or "Banned via Mini App"
    target_name = f"User {req.user_id}"
    tg_success = False
    last_error = None

    for bid, app in bots.items():
        try:
            member = await app.bot.get_chat_member(chat_id, req.user_id)
            target_name = member.user.mention_html()
            await app.bot.ban_chat_member(chat_id, req.user_id)
            await app.bot.send_message(
                chat_id=chat_id,
                text=f"🚫 <b>Banned</b>\nUser: {target_name}\nReason: {reason}\nBy: {admin_name}",
                parse_mode="HTML"
            )
            tg_success = True
            break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[BAN] bot {bid} failed: {e}")
            continue

    if not tg_success:
        raise HTTPException(502, f"Telegram action failed: {last_error}")

    # DB write in its own try/except — never let a DB error hide a successful action
    try:
        await mod_db.ban_user(chat_id, req.user_id, user.get("id", 0), reason)
    except Exception as e:
        logger.error(f"[BAN] DB write failed: {e}")

    await publish_event(chat_id, "mod_action", {
        "action": "ban", "target_id": req.user_id,
        "reason": reason, "admin_id": user.get("id", 0),
        "admin_name": admin_name,
    })
    return {"ok": True}


@router.get("/bans")
async def get_bans(chat_id: int, page: int = 1, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    bans = await mod_db.get_all_bans(chat_id, page=page)
    return {"ok": True, "data": [dict(b) for b in bans]}


@router.delete("/bans/{target_user_id}")
async def unban_user(chat_id: int, target_user_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM mod_logs WHERE chat_id=$1 AND target_id=$2 AND action='ban'",
            chat_id,
            target_user_id,
        )
    await publish_event(
        chat_id,
        "mod_action",
        {"action": "unban", "target_id": target_user_id, "admin_id": user.get("id", 0)},
    )
    return {"ok": True}


@router.get("/locks")
async def get_locks(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    locks = await mod_db.get_locks(chat_id)
    # Filter only valid lock keys to avoid returning internal DB columns like chat_id
    if isinstance(locks, dict):
        filtered_locks = {k: v for k, v in locks.items() if k in VALID_LOCK_KEYS}
    else:
        # If locks is an asyncpg Record
        filtered_locks = {k: v for k, v in dict(locks).items() if k in VALID_LOCK_KEYS}

    return {
        "ok": True,
        "data": filtered_locks,
    }


VALID_LOCK_KEYS = {
    "photo",
    "video",
    "sticker",
    "gif",
    "voice",
    "audio",
    "document",
    "link",
    "forward",
    "poll",
    "contact",
    "video_note",
    "all",
}


@router.put("/locks")
async def update_locks(chat_id: int, locks: dict, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    if not locks:
        return {"ok": True}

    # Only process valid lock keys
    valid_locks = {k: v for k, v in locks.items() if k in VALID_LOCK_KEYS and isinstance(v, bool)}
    if not valid_locks:
        return {"ok": True}

    columns = ", ".join(valid_locks.keys())
    placeholders = ", ".join([f"${i+2}" for i in range(len(valid_locks))])
    values = list(valid_locks.values())

    query = f"""
        INSERT INTO locks (chat_id, {columns}) VALUES ($1, {placeholders})
        ON CONFLICT (chat_id) DO UPDATE SET {", ".join([f"{k}=EXCLUDED.{k}" for k in valid_locks.keys()])}
    """
    async with db.pool.acquire() as conn:
        await conn.execute(query, chat_id, *values)

        # Also sync to settings JSON for engine to read settings['locks']
        settings_row = await conn.fetchrow(
            "SELECT settings FROM groups WHERE chat_id = $1", chat_id
        )
        import json

        settings_json = settings_row["settings"] if settings_row else {}
        if isinstance(settings_json, str):
            try:
                settings_json = json.loads(settings_json)
            except Exception:
                settings_json = {}

        # Sync lock settings to nested 'locks' object
        locks_dict = settings_json.setdefault("locks", {})
        locks_dict.update(valid_locks)

        await conn.execute(
            "UPDATE groups SET settings = $1::jsonb WHERE chat_id = $2",
            json.dumps(settings_json),
            chat_id,
        )

    for k, v in valid_locks.items():
        await publish_event(chat_id, "lock_change", {"lock_type": k, "enabled": v})

    return {"ok": True}


@router.get("/mod-log")
async def get_mod_log(
    chat_id: int,
    page: int = 1,
    limit: int = 50,
    action_type: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    offset = (page - 1) * limit
    async with db.pool.acquire() as conn:
        if action_type:
            rows = await conn.fetch(
                """SELECT ml.*, u.username as target_username, u.first_name as target_first_name,
                          bu.username as admin_username
                   FROM mod_logs ml
                   LEFT JOIN users u ON u.user_id = ml.target_id AND u.chat_id = ml.chat_id
                   LEFT JOIN users bu ON bu.user_id = ml.admin_id AND bu.chat_id = ml.chat_id
                   WHERE ml.chat_id=$1 AND ml.action=$2
                   ORDER BY ml.done_at DESC LIMIT $3 OFFSET $4""",
                chat_id,
                action_type,
                limit,
                offset,
            )
        else:
            rows = await conn.fetch(
                """SELECT ml.*, u.username as target_username, u.first_name as target_first_name,
                          bu.username as admin_username
                   FROM mod_logs ml
                   LEFT JOIN users u ON u.user_id = ml.target_id AND u.chat_id = ml.chat_id
                   LEFT JOIN users bu ON bu.user_id = ml.admin_id AND bu.chat_id = ml.chat_id
                   WHERE ml.chat_id=$1
                   ORDER BY ml.done_at DESC LIMIT $2 OFFSET $3""",
                chat_id,
                limit,
                offset,
            )
    return [dict(r) for r in rows]


@router.get("/warnings")
async def get_warnings(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT w.user_id, COUNT(*) as count, u.username, u.first_name
               FROM warnings w LEFT JOIN users u ON u.user_id = w.user_id AND u.chat_id = w.chat_id
               WHERE w.chat_id=$1 AND w.is_active=TRUE 
               GROUP BY w.user_id, u.username, u.first_name
               ORDER BY count DESC""",
            chat_id,
        )
    return [dict(r) for r in rows]


@router.get("/warnings/{target_user_id}")
async def get_user_warnings(
    chat_id: int, target_user_id: int, user: dict = Depends(get_current_user)
):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        count_row = await conn.fetchrow(
            "SELECT COUNT(*) FROM warnings WHERE chat_id=$1 AND user_id=$2 AND is_active=TRUE",
            chat_id,
            target_user_id,
        )
        logs = await conn.fetch(
            "SELECT * FROM mod_logs WHERE chat_id=$1 AND target_id=$2 AND action='warn' ORDER BY done_at DESC LIMIT 20",
            chat_id,
            target_user_id,
        )
    return {
        "warning": {"count": count_row["count"] if count_row else 0},
        "history": [dict(r) for r in logs],
    }


@router.post("/warnings")
async def warn_user(chat_id: int, req: WarnRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    from bot.registry import get_all

    bots = get_all()
    if not bots:
        raise HTTPException(503, "Bot not running")

    admin_name = user.get("first_name", "Admin")
    reason = req.reason or "Warned via Mini App"
    target_name = f"User {req.user_id}"
    tg_success = False
    last_error = None

    # First write to DB
    warn_count = 0
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO warnings (chat_id, user_id, reason, issued_by) VALUES ($1,$2,$3,$4)",
                chat_id, req.user_id, reason, user.get("id", 0)
            )
            await conn.execute(
                "INSERT INTO mod_logs (chat_id, target_id, action, reason, admin_id) "
                "VALUES ($1,$2,'warn',$3,$4)",
                chat_id, req.user_id, reason, user.get("id", 0)
            )
            warn_count = await conn.fetchval(
                "SELECT COUNT(*) FROM warnings WHERE chat_id=$1 AND user_id=$2 AND is_active=TRUE",
                chat_id, req.user_id
            )
    except Exception as e:
        logger.error(f"[WARN] DB write failed: {e}")
        raise HTTPException(500, f"Database error: {e}")

    # Then send Telegram message
    for bid, app in bots.items():
        try:
            member = await app.bot.get_chat_member(chat_id, req.user_id)
            target_name = member.user.mention_html()
            warn_text = (
                f"⚠️ <b>Warning Issued</b>\n"
                f"User: {target_name}\n"
                f"Reason: {reason}\n"
                f"Warnings: {warn_count}\n"
                f"By: {admin_name}"
            )
            await app.bot.send_message(
                chat_id=chat_id,
                text=warn_text,
                parse_mode="HTML"
            )
            tg_success = True
            break
        except Exception as tg_err:
            last_error = str(tg_err)
            logger.warning(f"[WARN] bot {bid} failed: {tg_err}")
            continue

    if not tg_success:
        raise HTTPException(502, f"Telegram action failed: {last_error}")

    await publish_event(chat_id, "warn_change", {"user_id": req.user_id, "action": "warn"})
    return {"ok": True, "warn_count": warn_count}


@router.delete("/warnings/{warning_id}")
async def remove_warning(chat_id: int, warning_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE warnings SET is_active=FALSE WHERE chat_id=$1 AND id=$2", chat_id, warning_id
        )
    return {"ok": True}


@router.delete("/warnings/{target_user_id}/all")
async def reset_all_warnings(
    chat_id: int, target_user_id: int, user: dict = Depends(get_current_user)
):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE warnings SET is_active=FALSE WHERE chat_id=$1 AND user_id=$2",
            chat_id,
            target_user_id,
        )
    return {"ok": True}


@router.get("/warn-settings")
async def get_warn_settings(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
    import json

    settings = row["settings"] if row else {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except Exception:
            settings = {}
    return {
        "warn_max": settings.get("warn_max", 3),
        "warn_action": settings.get("warn_action", "mute_24h"),
        "warn_expiry": settings.get("warn_expiry", "never"),
    }


@router.put("/warn-settings")
async def update_warn_settings(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    import json

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
        settings = row["settings"] if row else {}
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except Exception:
                settings = {}
        settings.update(
            {k: v for k, v in body.items() if k in ("warn_max", "warn_action", "warn_expiry")}
        )
        await conn.execute(
            "UPDATE groups SET settings=$1 WHERE chat_id=$2", json.dumps(settings), chat_id
        )
    return {"ok": True}


@router.get("/mutes")
async def get_mutes(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ml.*, u.username, u.first_name FROM mod_logs ml
               LEFT JOIN users u ON u.user_id = ml.target_id AND u.chat_id = ml.chat_id
               WHERE ml.chat_id=$1 AND ml.action='mute'
               ORDER BY ml.done_at DESC LIMIT 50""",
            chat_id,
        )
    return [dict(r) for r in rows]


@router.post("/mutes")
async def mute_user(chat_id: int, req: MuteRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    import re
    from datetime import datetime, timedelta, timezone

    from telegram import ChatPermissions

    from bot.registry import get_all

    bots = get_all()
    if not bots:
        raise HTTPException(503, "Bot not running")

    admin_name = user.get("first_name", "Admin")
    reason = req.reason or "No reason"
    duration_str = req.duration or "indefinite"
    target_name = "User"
    tg_success = False
    last_error = None

    unmute_dt = None
    if req.duration:
        match = re.match(r"^(\d+)([smhd])$", req.duration)
        if match:
            val, unit = int(match.group(1)), match.group(2)
            delta = {
                "s": timedelta(seconds=val),
                "m": timedelta(minutes=val),
                "h": timedelta(hours=val),
                "d": timedelta(days=val),
            }.get(unit)
            if delta:
                unmute_dt = datetime.now(tz=timezone.utc) + delta

    for bid, app in bots.items():
        try:
            member = await app.bot.get_chat_member(chat_id, req.user_id)
            target_name = member.user.mention_html()
            await app.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=req.user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=unmute_dt,
            )
            await app.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🔇 <b>Muted</b>\n"
                    f"User: {target_name}\n"
                    f"Duration: {duration_str}\n"
                    f"Reason: {reason}\n"
                    f"By: {admin_name}"
                ),
                parse_mode="HTML"
            )
            tg_success = True
            break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[MUTE] bot {bid} failed: {e}")
            continue

    if not tg_success:
        raise HTTPException(502, f"Mute failed: {last_error}")

    # DB write in its own try/except — never let a DB error hide a successful action
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO mod_logs (chat_id, target_id, target_name, action, reason, admin_id, admin_name, duration) VALUES ($1,$2,$3,'mute',$4,$5,$6,$7)",
                chat_id,
                req.user_id,
                target_name,
                reason,
                user.get("id", 0),
                admin_name,
                req.duration,
            )
    except Exception as e:
        logger.error(f"[MUTE] DB write failed: {e}")

    await publish_event(
        chat_id,
        "mod_action",
        {"action": "mute", "target_id": req.user_id, "admin_id": user.get("id", 0)},
    )
    return {"ok": True}


@router.delete("/mutes/{target_user_id}")
async def unmute_user(chat_id: int, target_user_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    from telegram import ChatPermissions

    from bot.registry import get_all

    bots = get_all()
    target_name = "User"
    for bid, app in bots.items():
        try:
            member = await app.bot.get_chat_member(chat_id, target_user_id)
            target_name = member.user.full_name
            await app.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_invite_users=True,
                ),
            )
            break
        except Exception:
            continue

    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO mod_logs (chat_id, target_id, target_name, action, reason, admin_id, admin_name) VALUES ($1,$2,$3,'unmute','Manual unmute via API',$4,$5)",
            chat_id,
            target_user_id,
            target_name,
            user.get("id", 0),
            user.get("first_name", "Admin"),
        )
    await publish_event(
        chat_id,
        "mod_action",
        {"action": "unmute", "target_id": target_user_id, "admin_id": user.get("id", 0)},
    )
    return {"ok": True}


@router.post("/actions/kick")
async def kick_user(chat_id: int, req: KickRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    from bot.registry import get_all

    bots = get_all()
    if not bots:
        raise HTTPException(503, "Bot not running")

    admin_name = user.get("first_name", "Admin")
    reason = req.reason or "Kicked via Mini App"
    target_name = f"User {req.user_id}"
    tg_success = False
    last_error = None

    for bid, app in bots.items():
        try:
            member = await app.bot.get_chat_member(chat_id, req.user_id)
            target_name = member.user.mention_html()
            await app.bot.ban_chat_member(chat_id, req.user_id)
            await app.bot.unban_chat_member(chat_id, req.user_id)  # kick = ban+unban
            await app.bot.send_message(
                chat_id=chat_id,
                text=f"👢 <b>Kicked</b>\nUser: {target_name}\nReason: {reason}\nBy: {admin_name}",
                parse_mode="HTML"
            )
            tg_success = True
            break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[KICK] bot {bid} failed: {e}")
            continue

    if not tg_success:
        raise HTTPException(502, f"Telegram action failed: {last_error}")

    # DB write in its own try/except — never let a DB error hide a successful action
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO mod_logs (chat_id,target_id,target_name,action,reason,admin_id,admin_name)"
                " VALUES ($1,$2,$3,'kick',$4,$5,$6)",
                chat_id, req.user_id, target_name, reason,
                user.get("id", 0), admin_name
            )
    except Exception as e:
        logger.error(f"[KICK] DB write failed: {e}")

    await publish_event(chat_id, "mod_action", {"action": "kick", "target_id": req.user_id, "admin_id": user.get("id", 0)})
    return {"ok": True}


@router.post("/bulk-action")
async def bulk_action(chat_id: int, req: BulkActionRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    results = []
    for uid in req.user_ids:
        try:
            if req.action == "ban":
                await mod_db.ban_user(chat_id, uid, user.get("id", 0), req.reason or "Bulk action")
            async with db.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO mod_logs (chat_id, target_id, action, reason, admin_id, admin_name) VALUES ($1,$2,$3,$4,$5,$6)",
                    chat_id,
                    uid,
                    req.action,
                    req.reason or "Bulk action",
                    user.get("id", 0),
                    user.get("first_name", "Admin"),
                )
            results.append({"user_id": uid, "ok": True})
        except Exception as e:
            results.append({"user_id": uid, "ok": False, "error": str(e)})
    return {"ok": True, "results": results}


@router.get("/filters")
async def get_filters(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, chat_id, keyword, 
                      COALESCE(reply_content, response) as reply_content,
                      added_by, added_at, created_at 
               FROM filters WHERE chat_id=$1 ORDER BY created_at DESC NULLS LAST""",
            chat_id,
        )
    return [dict(r) for r in rows]


@router.post("/filters")
async def add_filter(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    keyword = body.get("keyword", "").strip().lower()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword required")
    reply_content = body.get("reply_content", body.get("reply", ""))
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO filters (chat_id, keyword, reply_content, response) VALUES ($1,$2,$3,$3) ON CONFLICT (chat_id, keyword) DO UPDATE SET reply_content = EXCLUDED.reply_content, response = EXCLUDED.response",
            chat_id,
            keyword,
            reply_content,
        )
    return {"ok": True}


@router.delete("/filters/{filter_id}")
async def delete_filter(chat_id: int, filter_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM filters WHERE chat_id=$1 AND id=$2", chat_id, filter_id)
    return {"ok": True}


@router.get("/blacklist")
async def get_blacklist(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
    import json

    settings = row["settings"] if row else {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except Exception:
            settings = {}
    return {"words": settings.get("blacklist_words", [])}


@router.post("/blacklist")
async def add_blacklist_word(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    word = body.get("word", "").strip().lower()
    if not word:
        raise HTTPException(status_code=400, detail="word required")
    import json

    async with db.pool.acquire() as conn:
        # 1. Write to the blacklist TABLE (this is what message_guard reads)
        await conn.execute(
            """INSERT INTO blacklist (chat_id, word, action, added_by, added_at)
               VALUES ($1, $2, $3, $4, NOW())
               ON CONFLICT (chat_id, word) DO NOTHING""",
            chat_id, word, "delete", user.get("id", 0)
        )

        # 2. ALSO write to settings JSON (for Mini App display)
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
        settings = row["settings"] if row else {}
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except Exception:
                settings = {}
        words = settings.get("blacklist_words", [])
        if word not in words:
            words.append(word)
        settings["blacklist_words"] = words
        await conn.execute(
            "UPDATE groups SET settings=$1 WHERE chat_id=$2", json.dumps(settings), chat_id
        )
    return {"ok": True}


@router.delete("/blacklist/{word}")
async def remove_blacklist_word(chat_id: int, word: str, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    import json

    async with db.pool.acquire() as conn:
        # 1. Delete from blacklist TABLE
        await conn.execute(
            "DELETE FROM blacklist WHERE chat_id=$1 AND word=$2",
            chat_id, word.lower()
        )

        # 2. Also remove from settings JSON
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
        settings = row["settings"] if row else {}
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except Exception:
                settings = {}
        words = settings.get("blacklist_words", [])
        settings["blacklist_words"] = [w for w in words if w != word.lower()]
        await conn.execute(
            "UPDATE groups SET settings=$1 WHERE chat_id=$2", json.dumps(settings), chat_id
        )
    return {"ok": True}
