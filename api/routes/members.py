from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth import get_current_user
from db.client import db
import json

router = APIRouter(prefix="/api/groups/{chat_id}")

@router.get("/members")
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


@router.get("/members/events")
async def get_member_events(
    chat_id: int, request: Request,
    event_type: str = None, limit: int = 50
):
    # db   = request.app.state.db
    async with db.pool.acquire() as conn:
        q    = """
            SELECT * FROM member_events
            WHERE chat_id=$1
            {type_filter}
            ORDER BY created_at DESC
            LIMIT $2
        """
        if event_type:
            rows = await conn.fetch(
                q.format(type_filter="AND event_type=$3"),
                chat_id, limit, event_type
            )
        else:
            rows = await conn.fetch(
                q.format(type_filter=""), chat_id, limit
            )
    return [dict(r) for r in rows]


@router.get("/members/approved")
async def get_approved(chat_id: int):
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT am.*, u.username FROM approved_members am "
            "LEFT JOIN users u ON am.user_id = u.user_id AND am.chat_id = u.chat_id "
            "WHERE am.chat_id=$1 ORDER BY approved_at DESC",
            chat_id
        )
    return [dict(r) for r in rows]


@router.post("/members/{user_id}/approve")
async def approve_member(chat_id: int, user_id: int, request: Request):
    approver = request.state.user_id
    async with db.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO approved_members (chat_id, user_id, approved_by)
               VALUES ($1,$2,$3)
               ON CONFLICT (chat_id, user_id) DO NOTHING""",
            chat_id, user_id, approver
        )
    return {"ok": True}


@router.delete("/members/{user_id}/approve")
async def unapprove_member(chat_id: int, user_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM approved_members WHERE chat_id=$1 AND user_id=$2",
            chat_id, user_id
        )
    return {"ok": True}


@router.post("/members/bulk")
async def bulk_action(chat_id: int, request: Request):
    body    = await request.json()
    user_ids = body.get("user_ids", [])
    action  = body.get("action")

    if not user_ids or action not in ("ban", "mute", "approve", "kick", "unapprove", "warn"):
        raise HTTPException(status_code=400, detail="Invalid request")

    results = {"ok": [], "failed": []}
    
    # Get bot app for this group
    from bot.registry import get_all
    bots = get_all()
    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break

    async with db.pool.acquire() as conn:
        for uid in user_ids[:50]:  # max 50 per bulk action
            try:
                if action == "approve":
                    await conn.execute(
                        """INSERT INTO approved_members
                           (chat_id, user_id, approved_by)
                           VALUES ($1,$2,$3)
                           ON CONFLICT (chat_id, user_id) DO NOTHING""",
                        chat_id, uid, request.state.user_id
                    )
                elif action == "unapprove":
                    await conn.execute(
                        "DELETE FROM approved_members WHERE chat_id=$1 AND user_id=$2",
                        chat_id, uid
                    )
                elif bot_app:
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
                results["ok"].append(uid)
            except Exception:
                results["failed"].append(uid)

    return results


@router.get("/antiraid/status")
async def antiraid_status(chat_id: int):
    async with db.pool.acquire() as conn:
        session = await conn.fetchrow(
            """SELECT * FROM antiraid_sessions
               WHERE chat_id=$1 AND is_active=TRUE
               ORDER BY triggered_at DESC LIMIT 1""",
            chat_id
        )
    return dict(session) if session else {"active": False}


@router.put("/antiraid/settings")
async def update_antiraid_settings(chat_id: int, request: Request):
    body = await request.json()
    from db.ops.automod import update_group_setting

    keys = [
        "antiraid_enabled", "antiraid_mode", "antiraid_threshold",
        "antiraid_duration_mins", "auto_antiraid_enabled",
        "auto_antiraid_threshold", "captcha_enabled", "captcha_mode",
        "captcha_timeout_mins", "captcha_kick_on_timeout"
    ]
    for k in keys:
        if k in body:
            await update_group_setting(db.pool, chat_id, k, body[k])

    return {"ok": True}

@router.post("/antiraid/toggle")
async def toggle_antiraid(chat_id: int, request: Request):
    body = await request.json()
    enable = body.get("enable", False)
    
    # Need to call the bot handler or trigger it.
    # Since we have the bot app and settings, we can call manual_toggle_raid.
    from bot.registry import get_all
    bots = get_all()
    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break
    
    if not bot_app:
        raise HTTPException(status_code=503, detail="Bot service unavailable")
        
    from db.ops.automod import get_group_settings
    settings = await get_group_settings(db.pool, chat_id)
    from bot.antiraid.engine import manual_toggle_raid
    
    result = await manual_toggle_raid(
        bot_app.bot, chat_id, enable, settings, db.pool, request.state.user_id
    )
    return {"ok": True, "result": result}
