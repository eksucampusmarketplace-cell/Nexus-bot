"""
api/routes/engagement.py

API endpoints for the engagement system:
- XP & Levels
- Reputation
- Badges
- Newsletter
- Network
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from api.auth import require_auth
from db.client import db

router = APIRouter()


async def get_pool():
    """Get database pool."""
    if not db.pool:
        await db.connect()
    return db.pool


# ── XP & Levels ──────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/xp/leaderboard")
async def get_xp_leaderboard(
    chat_id: int, limit: int = 10, offset: int = 0, user=Depends(require_auth)
):
    """Get paginated XP leaderboard for a group."""
    pool = await get_pool()
    from db.ops.engagement import get_xp_leaderboard as get_lb

    leaderboard = await get_lb(pool, chat_id, user["bot_id"], limit, offset)
    return {"leaderboard": leaderboard}


@router.get("/api/groups/{chat_id}/xp/member/{user_id}")
async def get_member_xp_profile(chat_id: int, user_id: int, user=Depends(require_auth)):
    """Full XP profile for a member."""
    pool = await get_pool()
    from db.ops.engagement import get_member_xp
    from bot.engagement.xp import xp_to_next_level, calculate_level

    xp_data = await get_member_xp(pool, chat_id, user_id, user["bot_id"])
    xp_needed, next_level_xp = xp_to_next_level(xp_data["xp"])

    return {
        "user_id": user_id,
        "xp": xp_data["xp"],
        "level": xp_data["level"],
        "xp_to_next": xp_needed,
        "total_messages": xp_data["total_messages"],
        "streak_days": xp_data["streak_days"],
    }


@router.get("/api/groups/{chat_id}/xp/settings")
async def get_xp_settings_endpoint(chat_id: int, user=Depends(require_auth)):
    """Get XP settings for a group."""
    pool = await get_pool()
    from db.ops.engagement import get_xp_settings

    settings = await get_xp_settings(pool, chat_id, user["bot_id"])
    return settings


@router.put("/api/groups/{chat_id}/xp/settings")
async def update_xp_settings(chat_id: int, settings: dict, user=Depends(require_auth)):
    """Update XP settings for a group."""
    pool = await get_pool()
    from db.ops.engagement import upsert_xp_settings

    updated = await upsert_xp_settings(pool, chat_id, user["bot_id"], **settings)
    return updated


@router.post("/api/groups/{chat_id}/xp/give")
async def admin_give_xp(chat_id: int, data: dict, user=Depends(require_auth)):
    """Admin gives XP to a member."""
    pool = await get_pool()
    from bot.engagement.xp import XPEngine

    engine = XPEngine()
    result = await engine.award_xp(
        pool,
        None,
        None,
        chat_id,
        data["user_id"],
        user["bot_id"],
        data["amount"],
        data.get("reason", "Admin grant"),
        user["user_id"],
    )

    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Failed"))

    return result


@router.post("/api/groups/{chat_id}/xp/remove")
async def admin_remove_xp(chat_id: int, data: dict, user=Depends(require_auth)):
    """Admin removes XP from a member."""
    pool = await get_pool()
    from bot.engagement.xp import XPEngine

    engine = XPEngine()
    result = await engine.deduct_xp(
        pool,
        None,
        chat_id,
        data["user_id"],
        user["bot_id"],
        data["amount"],
        data.get("reason", "Admin penalty"),
        user["user_id"],
    )

    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Failed"))

    return result


@router.post("/api/groups/{chat_id}/xp/double")
async def start_double_xp(chat_id: int, data: dict, user=Depends(require_auth)):
    """Start double XP event."""
    pool = await get_pool()
    from bot.engagement.xp import XPEngine

    engine = XPEngine()
    success = await engine.start_double_xp(pool, chat_id, user["bot_id"], data.get("hours", 2))

    if not success:
        raise HTTPException(400, "Failed to start double XP")

    return {"ok": True, "hours": data.get("hours", 2)}


@router.get("/api/groups/{chat_id}/xp/levels")
async def get_levels_config(chat_id: int, user=Depends(require_auth)):
    """Get level configuration for a group."""
    pool = await get_pool()
    from db.ops.engagement import get_level_config

    config = await get_level_config(pool, chat_id, user["bot_id"])
    return {"levels": config}


@router.put("/api/groups/{chat_id}/xp/levels/{level}")
async def update_level_config(chat_id: int, level: int, data: dict, user=Depends(require_auth)):
    """Configure a level."""
    pool = await get_pool()
    from db.ops.engagement import upsert_level_config

    config = await upsert_level_config(pool, chat_id, user["bot_id"], level, **data)
    return {"ok": True, "config": config}


# ── Reputation ───────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/rep/leaderboard")
async def get_rep_leaderboard_endpoint(chat_id: int, limit: int = 10, user=Depends(require_auth)):
    """Get reputation leaderboard."""
    pool = await get_pool()
    from db.ops.engagement import get_rep_leaderboard

    leaderboard = await get_rep_leaderboard(pool, chat_id, user["bot_id"], limit)
    return {"leaderboard": leaderboard}


@router.get("/api/groups/{chat_id}/rep/member/{user_id}")
async def get_member_rep(chat_id: int, user_id: int, user=Depends(require_auth)):
    """Get reputation for a member."""
    pool = await get_pool()
    from db.ops.engagement import get_member_rep

    rep = await get_member_rep(pool, chat_id, user_id, user["bot_id"])
    return rep


@router.post("/api/groups/{chat_id}/rep/give")
async def admin_give_rep(chat_id: int, data: dict, user=Depends(require_auth)):
    """Admin gives/removes rep."""
    pool = await get_pool()
    from bot.engagement.reputation import give_rep

    success, message = await give_rep(
        pool,
        chat_id,
        user["user_id"],
        data["user_id"],
        user["bot_id"],
        data.get("amount", 1),
        data.get("reason"),
        is_admin=True,
    )

    if not success:
        raise HTTPException(400, message)

    return {"ok": True, "message": message}


# ── Badges ───────────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/badges")
async def get_group_badges(chat_id: int, user=Depends(require_auth)):
    """All badges and which members have them."""
    pool = await get_pool()
    from db.ops.engagement import get_all_badges

    badges = await get_all_badges(pool, user["bot_id"], chat_id)
    return {"badges": badges}


@router.get("/api/groups/{chat_id}/badges/member/{user_id}")
async def get_member_badges_endpoint(chat_id: int, user_id: int, user=Depends(require_auth)):
    """Get badges for a member."""
    pool = await get_pool()
    from db.ops.engagement import get_member_badges

    badges = await get_member_badges(pool, chat_id, user_id, user["bot_id"])
    return {"badges": badges}


@router.post("/api/groups/{chat_id}/badges/grant")
async def admin_grant_badge(chat_id: int, data: dict, user=Depends(require_auth)):
    """Admin grants a badge."""
    pool = await get_pool()
    from db.ops.engagement import award_badge

    await award_badge(
        pool, chat_id, data["user_id"], user["bot_id"], data["badge_id"], user["user_id"]
    )

    return {"ok": True}


# ── Newsletter ───────────────────────────────────────────────


@router.get("/api/groups/{chat_id}/newsletter/settings")
async def get_newsletter_settings(chat_id: int, user=Depends(require_auth)):
    """Get newsletter settings."""
    pool = await get_pool()
    from db.ops.engagement import get_newsletter_config

    config = await get_newsletter_config(pool, chat_id, user["bot_id"])
    return config or {"enabled": True, "send_day": 0, "send_hour_utc": 9}


@router.put("/api/groups/{chat_id}/newsletter/settings")
async def update_newsletter_settings(chat_id: int, data: dict, user=Depends(require_auth)):
    """Update newsletter settings."""
    pool = await get_pool()
    from db.ops.engagement import upsert_newsletter_config

    updated = await upsert_newsletter_config(pool, chat_id, user["bot_id"], **data)
    return updated


@router.get("/api/groups/{chat_id}/newsletter/history")
async def get_newsletter_history_endpoint(
    chat_id: int, limit: int = 10, user=Depends(require_auth)
):
    """Get newsletter history."""
    pool = await get_pool()
    from db.ops.engagement import get_newsletter_history

    history = await get_newsletter_history(pool, chat_id, user["bot_id"], limit)
    return {"history": history}


@router.post("/api/groups/{chat_id}/newsletter/send-now")
async def send_newsletter_now(chat_id: int, user=Depends(require_auth)):
    """Manually trigger newsletter."""
    # This would need bot instance - simplified for now
    return {"ok": True, "message": "Newsletter scheduled"}


@router.get("/api/groups/{chat_id}/newsletter/preview")
async def preview_newsletter(chat_id: int, user=Depends(require_auth)):
    """Preview this week's newsletter without sending."""
    pool = await get_pool()
    from bot.engagement.newsletter import generate_newsletter
    from datetime import date, timedelta

    today = date.today()
    week_end = today - timedelta(days=today.weekday() + 1)
    week_start = week_end - timedelta(days=6)

    preview = await generate_newsletter(pool, chat_id, user["bot_id"], week_start, week_end)

    return {"preview": preview}


# ── Network ──────────────────────────────────────────────────


@router.get("/api/networks")
async def get_user_networks(user=Depends(require_auth)):
    """Networks the user owns or their groups belong to."""
    # Simplified - would need to look up user's groups
    return {"networks": []}


@router.post("/api/networks")
async def create_network_endpoint(data: dict, user=Depends(require_auth)):
    """Create a new network."""
    pool = await get_pool()
    from bot.engagement.network import create_network

    result = await create_network(
        pool, data["name"], data.get("description", ""), user["user_id"], user["bot_id"]
    )

    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Failed"))

    return result


@router.get("/api/networks/{network_id}")
async def get_network_details(network_id: int, user=Depends(require_auth)):
    """Network details + member groups."""
    pool = await get_pool()
    from bot.engagement.network import get_network_details

    details = await get_network_details(pool, network_id)
    if not details:
        raise HTTPException(404, "Network not found")

    return details


@router.post("/api/networks/join")
async def join_network_endpoint(data: dict, user=Depends(require_auth)):
    """Join a network via invite code."""
    pool = await get_pool()
    from bot.engagement.network import join_network

    success, message = await join_network(
        pool, data["invite_code"], data["chat_id"], user["bot_id"]
    )

    if not success:
        raise HTTPException(400, message)

    return {"ok": True, "message": message}


@router.delete("/api/networks/{network_id}/members/{chat_id}")
async def leave_network_endpoint(network_id: int, chat_id: int, user=Depends(require_auth)):
    """Leave or remove group from network."""
    pool = await get_pool()
    from bot.engagement.network import leave_network

    success = await leave_network(pool, network_id, chat_id)
    if not success:
        raise HTTPException(400, "Failed to leave network")

    return {"ok": True}


@router.get("/api/networks/{network_id}/leaderboard")
async def get_network_leaderboard_endpoint(
    network_id: int, limit: int = 20, user=Depends(require_auth)
):
    """Get unified network leaderboard."""
    pool = await get_pool()
    from bot.engagement.network import get_network_leaderboard

    leaderboard = await get_network_leaderboard(pool, network_id, limit)
    return {"leaderboard": leaderboard}


@router.post("/api/networks/{network_id}/broadcast")
async def broadcast_to_network_endpoint(network_id: int, data: dict, user=Depends(require_auth)):
    """Broadcast to all groups in network."""
    # This would need bot instance - simplified
    return {"ok": True, "delivered": 0}
