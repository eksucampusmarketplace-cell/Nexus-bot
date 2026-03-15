from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth import get_current_user
from db.client import db
from db.ops.groups import get_user_managed_groups, get_group, update_group_settings
from db.ops.logs import get_recent_logs
from bot.utils.crypto import hash_token
import json

router = APIRouter()


@router.get("")
async def list_groups(user: dict = Depends(get_current_user)):
    bot_token = user.get("validated_bot_token")
    if not bot_token:
        # Fallback to all groups if no bot context (unlikely with get_current_user)
        return await get_user_managed_groups(user["id"])

    token_hash = hash_token(bot_token)

    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM groups WHERE bot_token_hash = $1", token_hash)
        res = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("settings"), str):
                try:
                    d["settings"] = json.loads(d["settings"])
                except Exception:
                    d["settings"] = {}
            elif not d.get("settings"):
                d["settings"] = {}
            res.append(d)
        return res


@router.get("/{chat_id}")
async def group_details(chat_id: int, user: dict = Depends(get_current_user)):
    group = await get_group(chat_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.put("/{chat_id}/settings")
async def update_settings(chat_id: int, settings: dict, user: dict = Depends(get_current_user)):
    # In a real app, verify user is admin in chat_id
    await update_group_settings(chat_id, settings)
    return {"status": "ok"}


@router.put("/{chat_id}/settings/bulk")
async def bulk_update_settings(chat_id: int, request: Request):
    """Bulk update multiple settings at once (for templates)."""
    body = await request.json()
    settings = body.get("settings", {})

    from db.ops.automod import bulk_update_group_settings

    await bulk_update_group_settings(db.pool, chat_id, settings)

    # Publish SSE event
    from api.routes.events import EventBus

    await EventBus.publish(chat_id, "settings_change", {"settings": settings})

    return {"status": "ok"}


@router.get("/{chat_id}/logs")
async def group_logs(chat_id: int, limit: int = 50, user: dict = Depends(get_current_user)):
    logs = await get_recent_logs(chat_id)
    return logs[:limit] if isinstance(logs, list) else logs


@router.post("/{chat_id}/copy-settings")
async def copy_settings_to_groups(
    chat_id: int,
    body: dict,
    user: dict = Depends(get_current_user)
):
    """Copy settings from source group to target groups."""
    target_chat_ids = body.get("target_chat_ids", [])
    modules = body.get("modules", [])
    if not target_chat_ids:
        raise HTTPException(status_code=400, detail="No target groups specified")

    source = await get_group(chat_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source group not found")

    source_settings = source.get("settings") or {}
    results = []
    for target_id in target_chat_ids:
        try:
            target = await get_group(int(target_id))
            if not target:
                results.append({"chat_id": target_id, "ok": False, "error": "Group not found"})
                continue
            target_settings = target.get("settings") or {}
            if not modules or "automod" in modules:
                automod_keys = ["antiflood", "antispam", "lock_link", "captcha_enabled", "warn_max", "warn_action"]
                for k in automod_keys:
                    if k in source_settings:
                        target_settings[k] = source_settings[k]
            if not modules or "welcome" in modules:
                for k in ["welcome_enabled", "goodbye_enabled"]:
                    if k in source_settings:
                        target_settings[k] = source_settings[k]
            if not modules or "modules" in modules:
                for k in ["xp_enabled", "games_enabled", "reports_enabled", "notes_enabled"]:
                    if k in source_settings:
                        target_settings[k] = source_settings[k]
            await update_group_settings(int(target_id), target_settings)
            results.append({"chat_id": target_id, "ok": True})
        except Exception as e:
            results.append({"chat_id": target_id, "ok": False, "error": str(e)})

    return {"ok": True, "results": results}


@router.post("/{chat_id}/actions/slowmode")
async def set_slowmode(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    seconds = max(0, min(3600, int(body.get("seconds", 0))))
    from bot.registry import get_all
    for bid, app_instance in get_all().items():
        try:
            await app_instance.bot.set_chat_slow_mode_delay(chat_id, seconds)
            break
        except Exception:
            continue
    return {"ok": True, "seconds": seconds}


@router.delete("/{chat_id}/settings/reset")
async def reset_settings(chat_id: int, user: dict = Depends(get_current_user)):
    await update_group_settings(chat_id, {})
    return {"ok": True}


@router.post("/{chat_id}/actions/leave")
async def leave_group(chat_id: int, user: dict = Depends(get_current_user)):
    from bot.registry import get_all
    for bid, app_instance in get_all().items():
        try:
            await app_instance.bot.leave_chat(chat_id)
            break
        except Exception:
            continue
    return {"ok": True}
