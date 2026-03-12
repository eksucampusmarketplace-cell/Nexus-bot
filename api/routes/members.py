from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth import get_current_user
from db.client import db
import json

router = APIRouter(prefix="/api/groups/{chat_id}/members")

@router.get("")
async def list_members(chat_id: int, user: dict = Depends(get_current_user)):
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users WHERE chat_id = $1 ORDER BY last_seen DESC LIMIT 100", chat_id)
        res = []
        for r in rows:
            d = dict(r)
            if isinstance(d['warns'], str):
                d['warns'] = json.loads(d['warns'])
            res.append(d)
        return res


@router.post("/bulk")
async def bulk_member_action(chat_id: int, request: Request):
    """Execute bulk action on multiple members."""
    owner_id = request.state.user_id
    db_conn = db.pool
    body     = await request.json()
    action   = body.get("action")
    user_ids = body.get("user_ids", [])
    duration = body.get("duration", "")

    if not user_ids or len(user_ids) > 50:
        raise HTTPException(status_code=400, detail="1-50 user_ids required")

    VALID = {"ban","mute","kick","approve","unapprove","warn"}
    if action not in VALID:
        raise HTTPException(status_code=400, detail=f"action must be one of {VALID}")

    # Get bot app for this group
    from bot.registry import get_all
    bots = get_all()
    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break

    if not bot_app:
        raise HTTPException(status_code=503, detail="Bot service unavailable")

    results = []
    for uid in user_ids:
        try:
            if action == "ban":
                await bot_app.bot.ban_chat_member(chat_id, uid)
            elif action == "mute":
                from telegram import ChatPermissions
                await bot_app.bot.restrict_chat_member(
                    chat_id, uid, ChatPermissions(can_send_messages=False)
                )
            elif action == "kick":
                await bot_app.bot.ban_chat_member(chat_id, uid)
                await bot_app.bot.unban_chat_member(chat_id, uid)
            elif action == "approve":
                await db_conn.execute(
                    "INSERT INTO approved_users (chat_id,user_id) VALUES ($1,$2) "
                    "ON CONFLICT DO NOTHING", chat_id, uid
                )
            elif action == "unapprove":
                await db_conn.execute(
                    "DELETE FROM approved_users WHERE chat_id=$1 AND user_id=$2",
                    chat_id, uid
                )
            elif action == "warn":
                await db_conn.execute(
                    "INSERT INTO user_warnings (chat_id,user_id,reason) VALUES ($1,$2,'bulk warn')",
                    chat_id, uid
                )
            results.append({"user_id": uid, "ok": True})
        except Exception as e:
            results.append({"user_id": uid, "ok": False, "error": str(e)[:100]})

    # Publish SSE event
    from api.routes.events import EventBus
    await EventBus.publish(chat_id, "bulk_action", {
        "action": action, "count": len(user_ids),
        "success": sum(1 for r in results if r["ok"])
    })

    return {"ok": True, "results": results}
