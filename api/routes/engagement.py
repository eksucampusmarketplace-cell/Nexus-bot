"""
api/routes/engagement.py

Engagement system API endpoints for XP, reputation, badges, newsletter, and networks.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from db.client import db

log = logging.getLogger("api.engagement")

router = APIRouter()


def _pool():
    return db.pool


# ── Request models ────────────────────────────────────────────────────────────


class GiveXPRequest(BaseModel):
    user_id: int
    amount: int
    reason: Optional[str] = "admin_grant"


class XPSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    xp_per_message: Optional[int] = None
    xp_per_daily: Optional[int] = None
    xp_per_game_win: Optional[int] = None
    message_cooldown_s: Optional[int] = None
    level_up_announce: Optional[bool] = None
    level_up_message: Optional[str] = None
    xp_admin_grant: Optional[int] = None


class DoubleXPRequest(BaseModel):
    hours: int = 2


class LevelConfigRequest(BaseModel):
    title: Optional[str] = None
    xp_required: Optional[int] = None
    unlock_description: Optional[str] = None


class GiveRepRequest(BaseModel):
    user_id: int
    amount: int = 1
    reason: Optional[str] = None


class GrantBadgeRequest(BaseModel):
    user_id: int
    badge_id: int


class NewsletterSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    send_day: Optional[int] = None
    send_hour_utc: Optional[int] = None
    include_top_members: Optional[bool] = None
    include_top_messages: Optional[bool] = None
    include_new_members: Optional[bool] = None
    include_leaderboard: Optional[bool] = None
    include_milestones: Optional[bool] = None
    custom_intro: Optional[str] = None


class CreateNetworkRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class JoinNetworkRequest(BaseModel):
    invite_code: str
    chat_id: int


class BroadcastRequest(BaseModel):
    message: str
    from_chat_id: int


# ── XP & Levels ───────────────────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/xp/leaderboard")
async def get_xp_leaderboard(
    chat_id: int,
    limit: int = 10,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_xp_leaderboard
    bot_id = user.get("bot_id", 0)
    try:
        board = await get_xp_leaderboard(_pool(), chat_id, bot_id, limit, offset)
        return {"leaderboard": board}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/groups/{chat_id}/xp/member/{user_id}")
async def get_xp_member(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_member_xp, get_member_badges
    from bot.engagement.xp import get_member_rank, xp_to_next_level
    bot_id = user.get("bot_id", 0)
    try:
        xp_data = await get_member_xp(_pool(), chat_id, user_id, bot_id)
        rank_data = await get_member_rank(_pool(), chat_id, user_id, bot_id)
        badges = await get_member_badges(_pool(), chat_id, user_id, bot_id)
        return {**xp_data, **rank_data, "badges": badges}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/groups/{chat_id}/xp/settings")
async def get_xp_settings_endpoint(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_xp_settings
    bot_id = user.get("bot_id", 0)
    try:
        return await get_xp_settings(_pool(), chat_id, bot_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/api/groups/{chat_id}/xp/settings")
async def update_xp_settings_endpoint(
    chat_id: int,
    body: XPSettingsRequest,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import upsert_xp_settings
    bot_id = user.get("bot_id", 0)
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if updates:
            result = await upsert_xp_settings(_pool(), chat_id, bot_id, **updates)
            return result
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/groups/{chat_id}/xp/give")
async def give_xp_endpoint(
    chat_id: int,
    body: GiveXPRequest,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.xp import award_xp
    bot_id = user.get("bot_id", 0)
    try:
        result = await award_xp(
            _pool(), None, None,
            chat_id, body.user_id, bot_id,
            body.amount, body.reason, given_by=user.get("user_id"),
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/groups/{chat_id}/xp/remove")
async def remove_xp_endpoint(
    chat_id: int,
    body: GiveXPRequest,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.xp import deduct_xp
    bot_id = user.get("bot_id", 0)
    try:
        result = await deduct_xp(
            _pool(), None,
            chat_id, body.user_id, bot_id,
            body.amount, body.reason or "admin_remove", given_by=user.get("user_id"),
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/groups/{chat_id}/xp/double")
async def start_double_xp_endpoint(
    chat_id: int,
    body: DoubleXPRequest,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.xp import start_double_xp
    bot_id = user.get("bot_id", 0)
    try:
        await start_double_xp(_pool(), chat_id, bot_id, body.hours)
        return {"ok": True, "hours": body.hours}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/groups/{chat_id}/xp/levels")
async def get_levels_endpoint(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_level_config
    from bot.engagement.xp import xp_for_level
    bot_id = user.get("bot_id", 0)
    try:
        custom = await get_level_config(_pool(), chat_id, bot_id)
        defaults = [
            {"level": 1, "xp_required": 0, "title": "Member"},
            {"level": 2, "xp_required": xp_for_level(2), "title": "Regular"},
            {"level": 5, "xp_required": xp_for_level(5), "title": "Trusted"},
            {"level": 10, "xp_required": xp_for_level(10), "title": "Veteran"},
            {"level": 20, "xp_required": xp_for_level(20), "title": "Legend"},
            {"level": 50, "xp_required": xp_for_level(50), "title": "Elite"},
        ]
        return {"levels": custom or defaults}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/api/groups/{chat_id}/xp/levels/{level}")
async def update_level_config_endpoint(
    chat_id: int,
    level: int,
    body: LevelConfigRequest,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import upsert_level_config
    bot_id = user.get("bot_id", 0)
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        await upsert_level_config(_pool(), chat_id, bot_id, level, **updates)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Reputation ────────────────────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/rep/leaderboard")
async def get_rep_leaderboard_endpoint(
    chat_id: int,
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_rep_leaderboard
    bot_id = user.get("bot_id", 0)
    try:
        return {"leaderboard": await get_rep_leaderboard(_pool(), chat_id, bot_id, limit)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/groups/{chat_id}/rep/member/{user_id}")
async def get_rep_member_endpoint(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.reputation import get_reputation
    bot_id = user.get("bot_id", 0)
    try:
        return await get_reputation(_pool(), chat_id, user_id, bot_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/groups/{chat_id}/rep/give")
async def give_rep_endpoint(
    chat_id: int,
    body: GiveRepRequest,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.reputation import give_rep
    bot_id = user.get("bot_id", 0)
    try:
        success, msg = await give_rep(
            _pool(), chat_id, user.get("user_id", 0), body.user_id, bot_id,
            amount=body.amount, reason=body.reason, is_admin=True,
        )
        return {"ok": success, "message": msg}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Badges ────────────────────────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/badges")
async def get_badges_endpoint(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_all_badges
    bot_id = user.get("bot_id", 0)
    try:
        badges = await get_all_badges(_pool(), bot_id, chat_id)
        return {"badges": badges}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/groups/{chat_id}/badges/member/{user_id}")
async def get_member_badges_endpoint(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_member_badges
    bot_id = user.get("bot_id", 0)
    try:
        return {"badges": await get_member_badges(_pool(), chat_id, user_id, bot_id)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/groups/{chat_id}/badges/grant")
async def grant_badge_endpoint(
    chat_id: int,
    body: GrantBadgeRequest,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.badges import grant_badge_manually
    bot_id = user.get("bot_id", 0)
    try:
        result = await grant_badge_manually(
            _pool(), chat_id, body.user_id, bot_id,
            body.badge_id, granted_by=user.get("user_id", 0),
        )
        return {"ok": result}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Newsletter ────────────────────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/newsletter/settings")
async def get_newsletter_settings(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_newsletter_config
    bot_id = user.get("bot_id", 0)
    try:
        return await get_newsletter_config(_pool(), chat_id, bot_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/api/groups/{chat_id}/newsletter/settings")
async def update_newsletter_settings(
    chat_id: int,
    body: NewsletterSettingsRequest,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import upsert_newsletter_config
    bot_id = user.get("bot_id", 0)
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if updates:
            await upsert_newsletter_config(_pool(), chat_id, bot_id, **updates)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/groups/{chat_id}/newsletter/history")
async def get_newsletter_history_endpoint(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_newsletter_history
    bot_id = user.get("bot_id", 0)
    try:
        history = await get_newsletter_history(_pool(), chat_id, bot_id)
        return {"history": history}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/groups/{chat_id}/newsletter/send-now")
async def send_newsletter_now(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.newsletter import send_newsletter
    from bot.registry import get_all as registry_get_all
    bot_id = user.get("bot_id", 0)
    try:
        apps = registry_get_all()
        bot = None
        for app in apps.values():
            info = app.bot_data.get("cached_bot_info", {})
            if info.get("id") == bot_id:
                bot = app.bot
                break
        if not bot and apps:
            bot = list(apps.values())[0].bot
        if bot:
            await send_newsletter(bot, _pool(), chat_id, bot_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/groups/{chat_id}/newsletter/preview")
async def preview_newsletter(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    from datetime import date, timedelta
    from bot.engagement.newsletter import generate_newsletter
    bot_id = user.get("bot_id", 0)
    try:
        today = date.today()
        week_start = today - timedelta(days=7)
        week_end = today - timedelta(days=1)
        text = await generate_newsletter(_pool(), chat_id, bot_id, week_start, week_end)
        return {"preview": text}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Networks ──────────────────────────────────────────────────────────────────


@router.get("/api/networks")
async def list_networks(user: dict = Depends(get_current_user)):
    from db.ops.engagement import get_chat_networks
    chat_id = user.get("chat_id") or user.get("active_chat_id")
    if not chat_id:
        return {"networks": []}
    try:
        return {"networks": await get_chat_networks(_pool(), chat_id)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/networks")
async def create_network_endpoint(
    body: CreateNetworkRequest,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.network import create_network
    bot_id = user.get("bot_id", 0)
    user_id = user.get("user_id", 0)
    try:
        result = await create_network(_pool(), body.name, body.description or "", user_id, bot_id)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/networks/{network_id}")
async def get_network_details(
    network_id: int,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_network_groups, get_network_leaderboard
    try:
        groups = await get_network_groups(_pool(), network_id)
        leaderboard = await get_network_leaderboard(_pool(), network_id, limit=10)
        return {"groups": groups, "leaderboard": leaderboard}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/networks/join")
async def join_network_endpoint(
    body: JoinNetworkRequest,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.network import join_network
    bot_id = user.get("bot_id", 0)
    try:
        success, msg = await join_network(_pool(), body.invite_code, body.chat_id, bot_id)
        return {"ok": success, "message": msg}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/api/networks/{network_id}/members/{chat_id}")
async def leave_network_endpoint(
    network_id: int,
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.network import leave_network
    try:
        result = await leave_network(_pool(), network_id, chat_id)
        return {"ok": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/networks/{network_id}/leaderboard")
async def get_network_leaderboard_endpoint(
    network_id: int,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    from db.ops.engagement import get_network_leaderboard
    try:
        return {"leaderboard": await get_network_leaderboard(_pool(), network_id, limit)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/networks/{network_id}/broadcast")
async def broadcast_to_network_endpoint(
    network_id: int,
    body: BroadcastRequest,
    user: dict = Depends(get_current_user),
):
    from bot.engagement.network import broadcast_to_network
    from bot.registry import get_all as registry_get_all
    user_id = user.get("user_id", 0)
    bot_id = user.get("bot_id", 0)
    try:
        apps = registry_get_all()
        bot = None
        for app in apps.values():
            info = app.bot_data.get("cached_bot_info", {})
            if info.get("id") == bot_id:
                bot = app.bot
                break
        if not bot and apps:
            bot = list(apps.values())[0].bot
        if not bot:
            raise HTTPException(503, "Bot not available")
        delivered = await broadcast_to_network(
            _pool(), bot, network_id, body.from_chat_id, user_id, body.message
        )
        if delivered == -1:
            raise HTTPException(429, "Rate limited — max 1 broadcast per hour")
        return {"ok": True, "delivered": delivered}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
