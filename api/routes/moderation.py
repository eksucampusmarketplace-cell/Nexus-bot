import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db.ops.moderation as mod_db
from api.auth import get_current_user
from bot.handlers.moderation.utils import publish_event
from db.client import db

log = logging.getLogger("[MOD_API]")

router = APIRouter(prefix="/api/groups/{chat_id}", tags=["moderation"])


async def verify_admin(chat_id: int, user: dict):
    pass


# ── Request Models ────────────────────────────────────────────────────────────

class BanRequest(BaseModel):
    user_id: int
    reason: str = "No reason provided"
    duration: Optional[str] = None


class MuteRequest(BaseModel):
    user_id: int
    reason: str = "No reason provided"
    duration: Optional[str] = None


class WarnRequest(BaseModel):
    user_id: int
    reason: str = "No reason provided"


class KickRequest(BaseModel):
    user_id: int
    reason: str = "No reason provided"


class WarnSettingsRequest(BaseModel):
    max_warns: int = 3
    warn_action: str = "mute"
    warn_duration: str = "1h"
    reset_on_kick: bool = True


class FilterRequest(BaseModel):
    keyword: str
    response: str


class BlacklistRequest(BaseModel):
    word: str
    action: str = "delete"


class BlacklistModeRequest(BaseModel):
    mode: str


class RulesRequest(BaseModel):
    rules_text: str


class PromoteRequest(BaseModel):
    title: Optional[str] = None


class TitleRequest(BaseModel):
    title: str


class LocksRequest(BaseModel):
    media: Optional[bool] = None
    stickers: Optional[bool] = None
    gifs: Optional[bool] = None
    links: Optional[bool] = None
    forwards: Optional[bool] = None
    polls: Optional[bool] = None
    games: Optional[bool] = None
    voice: Optional[bool] = None
    video_notes: Optional[bool] = None
    contacts: Optional[bool] = None


# ── Bans ──────────────────────────────────────────────────────────────────────

@router.get("/bans")
async def list_bans(
    chat_id: int,
    page: int = 1,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        bans = await mod_db.get_all_bans(chat_id, page=page)
        return {"ok": True, "data": [dict(b) for b in bans]}
    except Exception as e:
        log.error(f"[MOD_API] get_bans error: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/bans")
async def ban_user_api(
    chat_id: int,
    req: BanRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        from datetime import datetime
        from bot.handlers.moderation.utils import parse_time

        unban_at = None
        if req.duration:
            delta = parse_time(req.duration)
            if delta:
                unban_at = datetime.utcnow() + delta

        await mod_db.ban_user(
            chat_id, req.user_id, user.get("id", 0), req.reason, unban_at
        )
        await mod_db.add_mod_log(
            chat_id, "ban", req.user_id, str(req.user_id),
            user.get("id", 0), user.get("first_name", "Admin"), req.reason, req.duration
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "ban",
                "target_id": req.user_id,
                "reason": req.reason,
                "duration": req.duration or "permanent",
                "admin_id": user.get("id", 0),
                "admin_name": user.get("first_name", "Admin"),
            },
        )
        return {"ok": True}
    except Exception as e:
        log.error(f"[MOD_API] ban_user error: {e}")
        return {"ok": False, "error": str(e)}


@router.delete("/bans/{user_id}")
async def unban_user_api(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.unban_user(chat_id, user_id)
        await mod_db.add_mod_log(
            chat_id, "unban", user_id, str(user_id),
            user.get("id", 0), user.get("first_name", "Admin"), "Unbanned via miniapp"
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "unban",
                "target_id": user_id,
                "admin_id": user.get("id", 0),
                "admin_name": user.get("first_name", "Admin"),
            },
        )
        return {"ok": True}
    except Exception as e:
        log.error(f"[MOD_API] unban_user error: {e}")
        return {"ok": False, "error": str(e)}


# ── Mutes ─────────────────────────────────────────────────────────────────────

@router.get("/mutes")
async def list_mutes(
    chat_id: int,
    page: int = 1,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        mutes = await mod_db.get_all_mutes(chat_id, page=page)
        return {"ok": True, "data": [dict(m) for m in mutes]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/mutes")
async def mute_user_api(
    chat_id: int,
    req: MuteRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        from datetime import datetime
        from bot.handlers.moderation.utils import parse_time

        unmute_at = None
        if req.duration:
            delta = parse_time(req.duration)
            if delta:
                unmute_at = datetime.utcnow() + delta

        await mod_db.mute_user(
            chat_id, req.user_id, user.get("id", 0), req.reason, unmute_at
        )
        await mod_db.add_mod_log(
            chat_id, "mute", req.user_id, str(req.user_id),
            user.get("id", 0), user.get("first_name", "Admin"), req.reason, req.duration
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "mute",
                "target_id": req.user_id,
                "reason": req.reason,
                "duration": req.duration or "permanent",
                "admin_id": user.get("id", 0),
                "admin_name": user.get("first_name", "Admin"),
            },
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/mutes/{user_id}")
async def unmute_user_api(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.unmute_user(chat_id, user_id)
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "unmute",
                "target_id": user_id,
                "admin_id": user.get("id", 0),
                "admin_name": user.get("first_name", "Admin"),
            },
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Warnings ──────────────────────────────────────────────────────────────────

@router.get("/warnings")
async def list_warnings(
    chat_id: int,
    page: int = 1,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        warns = await mod_db.get_all_warnings(chat_id, page=page)
        return {"ok": True, "data": [dict(w) for w in warns]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/warnings/{user_id}")
async def get_user_warnings_api(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        warns = await mod_db.get_user_warnings(chat_id, user_id)
        settings = await mod_db.get_warn_settings(chat_id)
        return {
            "ok": True,
            "data": [dict(w) for w in warns],
            "count": len(warns),
            "max_warns": settings.get("max_warns", 3),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/warnings")
async def warn_user_api(
    chat_id: int,
    req: WarnRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.add_warning(chat_id, req.user_id, user.get("id", 0), req.reason)
        warn_count = await mod_db.get_active_warn_count(chat_id, req.user_id)
        settings = await mod_db.get_warn_settings(chat_id)
        await mod_db.add_mod_log(
            chat_id, "warn", req.user_id, str(req.user_id),
            user.get("id", 0), user.get("first_name", "Admin"), req.reason
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "warn",
                "target_id": req.user_id,
                "reason": req.reason,
                "warn_count": warn_count,
                "max_warns": settings.get("max_warns", 3),
                "admin_id": user.get("id", 0),
                "admin_name": user.get("first_name", "Admin"),
            },
        )
        return {"ok": True, "warn_count": warn_count}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/warnings/{warning_id}")
async def remove_warning_api(
    chat_id: int,
    warning_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.remove_warning(warning_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/warnings/{user_id}/all")
async def reset_all_warnings_api(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.reset_warnings(chat_id, user_id)
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "resetwarns",
                "target_id": user_id,
                "admin_id": user.get("id", 0),
                "admin_name": user.get("first_name", "Admin"),
            },
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Warn Settings ─────────────────────────────────────────────────────────────

@router.get("/warn-settings")
async def get_warn_settings_api(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        settings = await mod_db.get_warn_settings(chat_id)
        return {"ok": True, "data": settings}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/warn-settings")
async def update_warn_settings_api(
    chat_id: int,
    req: WarnSettingsRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.set_warn_settings(
            chat_id, req.max_warns, req.warn_action, req.warn_duration, req.reset_on_kick
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Mod Log ───────────────────────────────────────────────────────────────────

@router.get("/mod-log")
async def get_mod_log_api(
    chat_id: int,
    page: int = 1,
    limit: int = 20,
    action_type: Optional[str] = None,
    admin_id: Optional[int] = None,
    target_id: Optional[int] = None,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        logs = await mod_db.get_mod_log(
            chat_id, page=page, limit=limit,
            action_type=action_type, admin_id=admin_id, target_id=target_id
        )
        return {"ok": True, "data": [dict(l) for l in logs]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Locks ─────────────────────────────────────────────────────────────────────

@router.get("/locks")
async def get_locks_api(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        locks = await mod_db.get_locks(chat_id)
        return {"ok": True, "data": locks}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/locks")
async def update_locks_api(
    chat_id: int,
    req: LocksRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            return {"ok": True}

        await mod_db.set_locks(chat_id, **updates)

        for k, v in updates.items():
            await publish_event(chat_id, "lock_change", {"lock_type": k, "enabled": v})

        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Filters ───────────────────────────────────────────────────────────────────

@router.get("/filters")
async def list_filters_api(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        filters = await mod_db.get_filters(chat_id)
        return {"ok": True, "data": [dict(f) for f in filters]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/filters")
async def add_filter_api(
    chat_id: int,
    req: FilterRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.add_filter(chat_id, req.keyword, req.response, user.get("id", 0))
        await publish_event(
            chat_id,
            "filter_change",
            {"change": "added", "keyword": req.keyword},
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/filters/{filter_id}")
async def remove_filter_api(
    chat_id: int,
    filter_id: str,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await db.execute(
            "DELETE FROM filters WHERE id = $1 AND chat_id = $2", int(filter_id), chat_id
        )
        await publish_event(
            chat_id,
            "filter_change",
            {"change": "removed", "filter_id": filter_id},
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Blacklist ─────────────────────────────────────────────────────────────────

@router.get("/blacklist")
async def list_blacklist_api(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        words = await mod_db.get_blacklist(chat_id)
        return {"ok": True, "data": [dict(w) for w in words]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/blacklist")
async def add_blacklist_api(
    chat_id: int,
    req: BlacklistRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.add_blacklist(chat_id, req.word, req.action, user.get("id", 0))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/blacklist/{word}")
async def remove_blacklist_api(
    chat_id: int,
    word: str,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.remove_blacklist(chat_id, word)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/blacklist/mode")
async def set_blacklist_mode_api(
    chat_id: int,
    req: BlacklistModeRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        valid = ["delete", "warn", "mute", "kick", "ban"]
        if req.mode not in valid:
            return {"ok": False, "error": f"Invalid mode. Valid: {', '.join(valid)}"}
        await mod_db.set_blacklist_mode(chat_id, req.mode)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Rules ─────────────────────────────────────────────────────────────────────

@router.get("/rules")
async def get_rules_api(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    try:
        rules = await mod_db.get_rules(chat_id)
        return {"ok": True, "data": {"rules_text": rules or ""}}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/rules")
async def set_rules_api(
    chat_id: int,
    req: RulesRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.set_rules(chat_id, req.rules_text, user.get("id", 0))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Admins ────────────────────────────────────────────────────────────────────

@router.get("/admins")
async def list_admins_api(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        titles = await mod_db.get_all_admin_titles(chat_id)
        return {"ok": True, "data": titles}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/admins/{user_id}/title")
async def set_admin_title_api(
    chat_id: int,
    user_id: int,
    req: TitleRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.set_admin_title(chat_id, user_id, req.title[:16], user.get("id", 0))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Quick Actions ─────────────────────────────────────────────────────────────

@router.post("/actions/kick")
async def quick_kick_api(
    chat_id: int,
    req: KickRequest,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        await mod_db.add_mod_log(
            chat_id, "kick", req.user_id, str(req.user_id),
            user.get("id", 0), user.get("first_name", "Admin"), req.reason
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "kick",
                "target_id": req.user_id,
                "reason": req.reason,
                "admin_id": user.get("id", 0),
                "admin_name": user.get("first_name", "Admin"),
            },
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/actions/warn")
async def quick_warn_api(
    chat_id: int,
    req: WarnRequest,
    user: dict = Depends(get_current_user),
):
    return await warn_user_api(chat_id, req, user)


@router.post("/actions/mute")
async def quick_mute_api(
    chat_id: int,
    req: MuteRequest,
    user: dict = Depends(get_current_user),
):
    return await mute_user_api(chat_id, req, user)


@router.post("/actions/ban")
async def quick_ban_api(
    chat_id: int,
    req: BanRequest,
    user: dict = Depends(get_current_user),
):
    return await ban_user_api(chat_id, req, user)


# ── Member Profile ────────────────────────────────────────────────────────────

@router.get("/members/{user_id}/mod-summary")
async def get_member_mod_summary_api(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    await verify_admin(chat_id, user)
    try:
        summary = await mod_db.get_member_mod_summary(chat_id, user_id)
        return {"ok": True, "data": summary}
    except Exception as e:
        return {"ok": False, "error": str(e)}
