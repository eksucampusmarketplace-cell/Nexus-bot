"""
api/routes/engagement.py

REST API for XP, reputation, badges, newsletter, and network features.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import require_auth
from db.client import db

log = logging.getLogger("engagement.api")

router = APIRouter()


def _pool():
    return db.pool


# ── XP & Levels ──────────────────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/xp/leaderboard")
async def get_xp_leaderboard(
    chat_id: int,
    bot_id: int,
    limit: int = 20,
    offset: int = 0,
    auth=Depends(require_auth),
):
    from db.ops.engagement import get_xp_leaderboard
    pool = _pool()
    entries = await get_xp_leaderboard(pool, chat_id, bot_id, limit, offset)
    return {"leaderboard": entries}


@router.get("/api/groups/{chat_id}/xp/member/{user_id}")
async def get_xp_member(
    chat_id: int,
    user_id: int,
    bot_id: int,
    auth=Depends(require_auth),
):
    from db.ops.engagement import get_member_xp, get_member_rank
    from bot.engagement.xp import xp_to_next_level, xp_for_level
    pool = _pool()
    xp_data = await get_member_xp(pool, chat_id, user_id, bot_id)
    rank_data = await get_member_rank(pool, chat_id, user_id, bot_id)
    xp = xp_data.get("xp", 0)
    level = xp_data.get("level", 1)
    xp_needed, total_next = xp_to_next_level(xp)
    xp_for_cur = xp_for_level(level)
    level_range = total_next - xp_for_cur
    progress = int((xp - xp_for_cur) / max(1, level_range) * 100)
    return {
        **xp_data,
        **rank_data,
        "xp_to_next": xp_needed,
        "progress_pct": min(100, progress),
    }


@router.get("/api/groups/{chat_id}/xp/settings")
async def get_xp_settings_api(
    chat_id: int,
    bot_id: int,
    auth=Depends(require_auth),
):
    from db.ops.engagement import get_xp_settings
    pool = _pool()
    return await get_xp_settings(pool, chat_id, bot_id)


class XpSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    xp_per_message: Optional[int] = None
    message_cooldown_s: Optional[int] = None
    xp_per_daily: Optional[int] = None
    xp_per_game_win: Optional[int] = None
    xp_admin_grant: Optional[int] = None
    level_up_announce: Optional[bool] = None
    level_up_message: Optional[str] = None


@router.put("/api/groups/{chat_id}/xp/settings")
async def update_xp_settings_api(
    chat_id: int,
    bot_id: int,
    body: XpSettingsUpdate,
    auth=Depends(require_auth),
):
    from db.ops.engagement import upsert_xp_settings
    pool = _pool()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    result = await upsert_xp_settings(pool, chat_id, bot_id, **updates)
    return result


class GiveXpBody(BaseModel):
    user_id: int
    amount: int
    reason: str = "admin_grant"
    bot_id: int


@router.post("/api/groups/{chat_id}/xp/give")
async def give_xp_api(chat_id: int, body: GiveXpBody, auth=Depends(require_auth)):
    from bot.engagement.xp import award_xp
    from db.client import db as _db
    pool = _pool()
    result = await award_xp(
        pool, _db.redis, None,
        chat_id, body.user_id, body.bot_id,
        body.amount, body.reason
    )
    return result


class RemoveXpBody(BaseModel):
    user_id: int
    amount: int
    reason: str = "admin_remove"
    bot_id: int
    admin_id: int


@router.post("/api/groups/{chat_id}/xp/remove")
async def remove_xp_api(chat_id: int, body: RemoveXpBody, auth=Depends(require_auth)):
    from bot.engagement.xp import deduct_xp
    from db.client import db as _db
    pool = _pool()
    result = await deduct_xp(
        pool, _db.redis,
        chat_id, body.user_id, body.bot_id,
        body.amount, body.reason, body.admin_id
    )
    return result


class DoubleXpBody(BaseModel):
    hours: int = 2
    bot_id: int


@router.post("/api/groups/{chat_id}/xp/double")
async def double_xp_api(chat_id: int, body: DoubleXpBody, auth=Depends(require_auth)):
    from bot.engagement.xp import start_double_xp
    pool = _pool()
    await start_double_xp(pool, chat_id, body.bot_id, body.hours)
    return {"ok": True, "hours": body.hours}


@router.get("/api/groups/{chat_id}/xp/levels")
async def get_levels_api(chat_id: int, bot_id: int, auth=Depends(require_auth)):
    from db.ops.engagement import get_level_config
    pool = _pool()
    return {"levels": await get_level_config(pool, chat_id, bot_id)}


class LevelConfigBody(BaseModel):
    xp_required: Optional[int] = None
    title: Optional[str] = None
    unlock_description: Optional[str] = None
    bot_id: int


@router.put("/api/groups/{chat_id}/xp/levels/{level}")
async def update_level_config_api(
    chat_id: int, level: int, body: LevelConfigBody, auth=Depends(require_auth)
):
    from db.ops.engagement import upsert_level_config
    pool = _pool()
    updates = {
        k: v for k, v in body.model_dump().items()
        if k != "bot_id" and v is not None
    }
    await upsert_level_config(pool, chat_id, body.bot_id, level, **updates)
    return {"ok": True}


# ── Reputation ───────────────────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/rep/leaderboard")
async def get_rep_leaderboard_api(
    chat_id: int, bot_id: int, limit: int = 10, auth=Depends(require_auth)
):
    from db.ops.engagement import get_rep_leaderboard
    pool = _pool()
    return {"leaderboard": await get_rep_leaderboard(pool, chat_id, bot_id, limit)}


@router.get("/api/groups/{chat_id}/rep/member/{user_id}")
async def get_rep_member_api(
    chat_id: int, user_id: int, bot_id: int, auth=Depends(require_auth)
):
    from bot.engagement.reputation import get_reputation
    pool = _pool()
    return await get_reputation(pool, chat_id, user_id, bot_id)


class GiveRepBody(BaseModel):
    user_id: int
    amount: int = 1
    reason: Optional[str] = None
    bot_id: int
    admin_id: int


@router.post("/api/groups/{chat_id}/rep/give")
async def give_rep_api(chat_id: int, body: GiveRepBody, auth=Depends(require_auth)):
    from bot.engagement.reputation import give_rep
    pool = _pool()
    ok, msg = await give_rep(
        pool, chat_id, body.admin_id, body.user_id, body.bot_id,
        body.amount, body.reason, is_admin=True
    )
    return {"ok": ok, "message": msg}


# ── Badges ───────────────────────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/badges")
async def get_badges_api(chat_id: int, bot_id: int, auth=Depends(require_auth)):
    from db.ops.engagement import get_all_badges
    pool = _pool()
    return {"badges": await get_all_badges(pool, bot_id, chat_id)}


@router.get("/api/groups/{chat_id}/badges/member/{user_id}")
async def get_member_badges_api(
    chat_id: int, user_id: int, bot_id: int, auth=Depends(require_auth)
):
    from db.ops.engagement import get_member_badges
    pool = _pool()
    return {"badges": await get_member_badges(pool, chat_id, user_id, bot_id)}


class GrantBadgeBody(BaseModel):
    user_id: int
    badge_id: int
    bot_id: int
    admin_id: int


@router.post("/api/groups/{chat_id}/badges/grant")
async def grant_badge_api(chat_id: int, body: GrantBadgeBody, auth=Depends(require_auth)):
    from bot.engagement.badges import grant_badge_manually
    pool = _pool()
    ok = await grant_badge_manually(
        pool, chat_id, body.user_id, body.bot_id, body.badge_id, body.admin_id
    )
    return {"ok": ok}


# ── Newsletter ───────────────────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/newsletter/settings")
async def get_newsletter_settings_api(
    chat_id: int, bot_id: int, auth=Depends(require_auth)
):
    from db.ops.engagement import get_newsletter_config
    pool = _pool()
    return await get_newsletter_config(pool, chat_id, bot_id)


class NewsletterSettingsBody(BaseModel):
    bot_id: int
    enabled: Optional[bool] = None
    send_day: Optional[int] = None
    send_hour_utc: Optional[int] = None
    include_top_members: Optional[bool] = None
    include_top_messages: Optional[bool] = None
    include_new_members: Optional[bool] = None
    include_leaderboard: Optional[bool] = None
    include_milestones: Optional[bool] = None
    custom_intro: Optional[str] = None


@router.put("/api/groups/{chat_id}/newsletter/settings")
async def update_newsletter_settings_api(
    chat_id: int, body: NewsletterSettingsBody, auth=Depends(require_auth)
):
    from db.ops.engagement import upsert_newsletter_config
    pool = _pool()
    updates = {
        k: v for k, v in body.model_dump().items()
        if k != "bot_id" and v is not None
    }
    await upsert_newsletter_config(pool, chat_id, body.bot_id, **updates)
    return {"ok": True}


@router.get("/api/groups/{chat_id}/newsletter/history")
async def get_newsletter_history_api(
    chat_id: int, bot_id: int, limit: int = 10, auth=Depends(require_auth)
):
    from db.ops.engagement import get_newsletter_history
    pool = _pool()
    return {"history": await get_newsletter_history(pool, chat_id, bot_id, limit)}


@router.get("/api/groups/{chat_id}/newsletter/preview")
async def preview_newsletter_api(
    chat_id: int, bot_id: int, auth=Depends(require_auth)
):
    from bot.engagement.newsletter import generate_newsletter
    from datetime import date, timedelta
    pool = _pool()
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 1)
    week_end = today - timedelta(days=1)
    text = await generate_newsletter(pool, chat_id, bot_id, week_start, week_end)
    return {"preview": text}


class SendNewsletterBody(BaseModel):
    bot_id: int


@router.post("/api/groups/{chat_id}/newsletter/send-now")
async def send_newsletter_now_api(
    chat_id: int, body: SendNewsletterBody,
    request: Request, auth=Depends(require_auth)
):
    from bot.engagement.newsletter import send_newsletter
    from bot.registry import get_all as registry_get_all
    pool = _pool()

    bot = None
    for app_instance in registry_get_all().values():
        try:
            if app_instance.bot_data.get("cached_bot_info", {}).get("id") == body.bot_id:
                bot = app_instance.bot
                break
        except Exception:
            pass

    if not bot:
        raise HTTPException(404, "Bot not found")

    await send_newsletter(bot, pool, chat_id, body.bot_id)
    return {"ok": True}


# ── Network ──────────────────────────────────────────────────────────────────


@router.get("/api/networks")
async def get_networks_api(chat_id: int, auth=Depends(require_auth)):
    from db.ops.engagement import get_chat_networks
    pool = _pool()
    return {"networks": await get_chat_networks(pool, chat_id)}


class CreateNetworkBody(BaseModel):
    name: str
    description: Optional[str] = None
    owner_user_id: int
    owner_bot_id: int


@router.post("/api/networks")
async def create_network_api(body: CreateNetworkBody, auth=Depends(require_auth)):
    from bot.engagement.network import create_network
    pool = _pool()
    result = await create_network(
        pool, body.name, body.description,
        body.owner_user_id, body.owner_bot_id
    )
    return result


@router.get("/api/networks/{network_id}")
async def get_network_api(network_id: int, auth=Depends(require_auth)):
    from db.ops.engagement import get_network_groups
    pool = _pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM group_networks WHERE id=$1", network_id)
        if not row:
            raise HTTPException(404, "Network not found")
        groups = await get_network_groups(pool, network_id)
    return {**dict(row), "groups": groups}


class JoinNetworkBody(BaseModel):
    invite_code: str
    chat_id: int
    bot_id: int


@router.post("/api/networks/join")
async def join_network_api(body: JoinNetworkBody, auth=Depends(require_auth)):
    from bot.engagement.network import join_network
    pool = _pool()
    ok, msg = await join_network(pool, body.invite_code, body.chat_id, body.bot_id)
    return {"ok": ok, "message": msg}


@router.delete("/api/networks/{network_id}/members/{chat_id}")
async def leave_network_api(network_id: int, chat_id: int, auth=Depends(require_auth)):
    from bot.engagement.network import leave_network
    pool = _pool()
    ok = await leave_network(pool, network_id, chat_id)
    return {"ok": ok}


@router.get("/api/networks/{network_id}/leaderboard")
async def get_network_leaderboard_api(
    network_id: int, limit: int = 20, auth=Depends(require_auth)
):
    from bot.engagement.network import get_network_leaderboard
    pool = _pool()
    return {"leaderboard": await get_network_leaderboard(pool, network_id, limit)}


class BroadcastBody(BaseModel):
    message: str
    from_chat_id: int
    sent_by: int
    bot_id: int


@router.post("/api/networks/{network_id}/broadcast")
async def broadcast_network_api(
    network_id: int, body: BroadcastBody,
    request: Request, auth=Depends(require_auth)
):
    from bot.engagement.network import broadcast_to_network
    from bot.registry import get_all as registry_get_all
    pool = _pool()

    bot = None
    for app_instance in registry_get_all().values():
        try:
            if app_instance.bot_data.get("cached_bot_info", {}).get("id") == body.bot_id:
                bot = app_instance.bot
                break
        except Exception:
            pass

    if not bot:
        raise HTTPException(404, "Bot not found")

    delivered = await broadcast_to_network(
        pool, bot, network_id, body.from_chat_id, body.sent_by, body.message
    )

    if delivered == -1:
        raise HTTPException(429, "Rate limited: max 1 broadcast per hour")

    return {"ok": True, "delivered": delivered}
