import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import db.ops.moderation as mod_db
from api.auth import get_current_user
from bot.handlers.moderation.utils import publish_event
from db.client import db

router = APIRouter(prefix="/api/groups/{chat_id}", tags=["moderation"])
logger = logging.getLogger(__name__)


async def verify_admin(chat_id: int, user: dict):
    pass


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
    await mod_db.ban_user(chat_id, req.user_id, user.get("id", 0), req.reason)
    await publish_event(
        chat_id,
        "mod_action",
        {
            "action": "ban",
            "target_id": req.user_id,
            "reason": req.reason,
            "admin_id": user.get("id", 0),
            "admin_name": user.get("first_name", "Admin"),
        },
    )
    logger.info(f"[API][moderation][BAN] chat_id={chat_id} target={req.user_id} by={user.get('id')}")
    return {"ok": True}


@router.get("/bans")
async def get_bans(chat_id: int, page: int = 1, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    bans = await mod_db.get_all_bans(chat_id, page=page)
    return {"ok": True, "data": bans}


@router.delete("/bans/{target_user_id}")
async def unban_user(chat_id: int, target_user_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM moderation_log WHERE chat_id=$1 AND user_id=$2 AND action='ban'",
            chat_id, target_user_id
        )
    await publish_event(chat_id, "mod_action", {"action": "unban", "target_id": target_user_id, "admin_id": user.get("id", 0)})
    return {"ok": True}


@router.get("/locks")
async def get_locks(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    locks = await mod_db.get_locks(chat_id)
    return {"ok": True, "data": locks}


@router.put("/locks")
async def update_locks(chat_id: int, locks: dict, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    if not locks:
        return {"ok": True}

    valid_locks = {k: v for k, v in locks.items() if isinstance(v, bool)}
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

    for k, v in valid_locks.items():
        await publish_event(chat_id, "lock_change", {"lock_type": k, "enabled": v})

    return {"ok": True}


@router.get("/mod-log")
async def get_mod_log(
    chat_id: int,
    page: int = 1,
    limit: int = 50,
    action_type: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    await verify_admin(chat_id, user)
    offset = (page - 1) * limit
    async with db.pool.acquire() as conn:
        if action_type:
            rows = await conn.fetch(
                """SELECT ml.*, u.username as target_username, u.first_name as target_first_name,
                          bu.username as admin_username
                   FROM moderation_log ml
                   LEFT JOIN users u ON u.user_id = ml.user_id
                   LEFT JOIN users bu ON bu.user_id = ml.by_user_id
                   WHERE ml.chat_id=$1 AND ml.action=$2
                   ORDER BY ml.created_at DESC LIMIT $3 OFFSET $4""",
                chat_id, action_type, limit, offset
            )
        else:
            rows = await conn.fetch(
                """SELECT ml.*, u.username as target_username, u.first_name as target_first_name,
                          bu.username as admin_username
                   FROM moderation_log ml
                   LEFT JOIN users u ON u.user_id = ml.user_id
                   LEFT JOIN users bu ON bu.user_id = ml.by_user_id
                   WHERE ml.chat_id=$1
                   ORDER BY ml.created_at DESC LIMIT $2 OFFSET $3""",
                chat_id, limit, offset
            )
    return [dict(r) for r in rows]


@router.get("/warnings")
async def get_warnings(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT w.*, u.username, u.first_name
               FROM warnings w LEFT JOIN users u ON u.user_id = w.user_id
               WHERE w.chat_id=$1 AND w.count > 0 ORDER BY w.count DESC""",
            chat_id
        )
    return [dict(r) for r in rows]


@router.get("/warnings/{target_user_id}")
async def get_user_warnings(chat_id: int, target_user_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM warnings WHERE chat_id=$1 AND user_id=$2", chat_id, target_user_id
        )
        logs = await conn.fetch(
            "SELECT * FROM moderation_log WHERE chat_id=$1 AND user_id=$2 AND action='warn' ORDER BY created_at DESC LIMIT 20",
            chat_id, target_user_id
        )
    return {"warning": dict(row) if row else None, "history": [dict(r) for r in logs]}


@router.post("/warnings")
async def warn_user(chat_id: int, req: WarnRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM warnings WHERE chat_id=$1 AND user_id=$2", chat_id, req.user_id)
        if existing:
            new_count = (existing["count"] or 0) + 1
            await conn.execute("UPDATE warnings SET count=$1 WHERE chat_id=$2 AND user_id=$3", new_count, chat_id, req.user_id)
        else:
            await conn.execute("INSERT INTO warnings (chat_id, user_id, count) VALUES ($1,$2,1)", chat_id, req.user_id)
        await conn.execute(
            "INSERT INTO moderation_log (chat_id, user_id, action, reason, by_user_id) VALUES ($1,$2,'warn',$3,$4)",
            chat_id, req.user_id, req.reason or "", user.get("id", 0)
        )
    await publish_event(chat_id, "warn_change", {"user_id": req.user_id, "action": "warn"})
    return {"ok": True}


@router.delete("/warnings/{warning_id}")
async def remove_warning(chat_id: int, warning_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE warnings SET count = GREATEST(count-1, 0) WHERE chat_id=$1 AND id=$2",
            chat_id, warning_id
        )
    return {"ok": True}


@router.delete("/warnings/{target_user_id}/all")
async def reset_all_warnings(chat_id: int, target_user_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE warnings SET count=0 WHERE chat_id=$1 AND user_id=$2", chat_id, target_user_id)
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
        settings.update({k: v for k, v in body.items() if k in ("warn_max", "warn_action", "warn_expiry")})
        await conn.execute(
            "UPDATE groups SET settings=$1 WHERE chat_id=$2",
            json.dumps(settings), chat_id
        )
    return {"ok": True}


@router.get("/mutes")
async def get_mutes(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ml.*, u.username, u.first_name FROM moderation_log ml
               LEFT JOIN users u ON u.user_id = ml.user_id
               WHERE ml.chat_id=$1 AND ml.action='mute'
               ORDER BY ml.created_at DESC LIMIT 50""",
            chat_id
        )
    return [dict(r) for r in rows]


@router.post("/mutes")
async def mute_user(chat_id: int, req: MuteRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO moderation_log (chat_id, user_id, action, reason, by_user_id) VALUES ($1,$2,'mute',$3,$4)",
            chat_id, req.user_id, req.reason or "", user.get("id", 0)
        )
    await publish_event(chat_id, "mod_action", {"action": "mute", "target_id": req.user_id, "admin_id": user.get("id", 0)})
    return {"ok": True}


@router.delete("/mutes/{target_user_id}")
async def unmute_user(chat_id: int, target_user_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO moderation_log (chat_id, user_id, action, reason, by_user_id) VALUES ($1,$2,'unmute','Manual unmute via API',$3)",
            chat_id, target_user_id, user.get("id", 0)
        )
    await publish_event(chat_id, "mod_action", {"action": "unmute", "target_id": target_user_id, "admin_id": user.get("id", 0)})
    return {"ok": True}


@router.post("/actions/kick")
async def kick_user(chat_id: int, req: KickRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO moderation_log (chat_id, user_id, action, reason, by_user_id) VALUES ($1,$2,'kick',$3,$4)",
            chat_id, req.user_id, req.reason or "", user.get("id", 0)
        )
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
                    "INSERT INTO moderation_log (chat_id, user_id, action, reason, by_user_id) VALUES ($1,$2,$3,$4,$5)",
                    chat_id, uid, req.action, req.reason or "Bulk action", user.get("id", 0)
                )
            results.append({"user_id": uid, "ok": True})
        except Exception as e:
            results.append({"user_id": uid, "ok": False, "error": str(e)})
    return {"ok": True, "results": results}


@router.get("/filters")
async def get_filters(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM filters WHERE chat_id=$1 ORDER BY created_at DESC", chat_id)
    return [dict(r) for r in rows]


@router.post("/filters")
async def add_filter(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    keyword = body.get("keyword", "").strip().lower()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword required")
    reply = body.get("reply", "")
    async with db.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO filters (chat_id, keyword, reply_content) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
            chat_id, keyword, reply
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
        await conn.execute("UPDATE groups SET settings=$1 WHERE chat_id=$2", json.dumps(settings), chat_id)
    return {"ok": True}


@router.delete("/blacklist/{word}")
async def remove_blacklist_word(chat_id: int, word: str, user: dict = Depends(get_current_user)):
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
        words = settings.get("blacklist_words", [])
        settings["blacklist_words"] = [w for w in words if w != word]
        await conn.execute("UPDATE groups SET settings=$1 WHERE chat_id=$2", json.dumps(settings), chat_id)
    return {"ok": True}
