from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db.ops.moderation as mod_db
from api.auth import get_current_user
from bot.handlers.moderation.utils import publish_event
from db.client import db

router = APIRouter(prefix="/api/groups/{chat_id}", tags=["moderation"])


# Simple auth stub
async def verify_admin(chat_id: int, user: dict):
    # In real app, check if current user is admin of chat_id in our DB or via bot
    # For now, we'll assume they are authenticated via get_current_user
    pass


class BanRequest(BaseModel):
    user_id: int
    reason: str
    duration: Optional[str] = None


@router.post("/bans")
async def ban_user(chat_id: int, req: BanRequest, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    # Actually we should call the bot to ban, but here we just update DB
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
    return {"ok": True}


@router.get("/bans")
async def get_bans(chat_id: int, page: int = 1, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    bans = await mod_db.get_all_bans(chat_id, page=page)
    return {"ok": True, "data": bans}


@router.get("/locks")
async def get_locks(chat_id: int, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    locks = await mod_db.get_locks(chat_id)
    return {"ok": True, "data": locks}


@router.put("/locks")
async def update_locks(chat_id: int, locks: dict, user: dict = Depends(get_current_user)):
    await verify_admin(chat_id, user)
    # Update locks in DB
    if not locks:
        return {"ok": True}

    columns = ", ".join(locks.keys())
    placeholders = ", ".join([f"${i+2}" for i in range(len(locks))])
    values = list(locks.values())

    query = f"""
        INSERT INTO locks (chat_id, {columns}) VALUES ($1, {placeholders})
        ON CONFLICT (chat_id) DO UPDATE SET {", ".join([f"{k}=EXCLUDED.{k}" for k in locks.keys()])}
    """
    await db.execute(query, chat_id, *values)

    for k, v in locks.items():
        await publish_event(chat_id, "lock_change", {"lock_type": k, "enabled": v})

    return {"ok": True}
