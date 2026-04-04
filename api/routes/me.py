"""
GET /api/me
Auth: required (initData)
Returns complete user context across all Nexus-managed groups.

Logic:
1. Extract user_id from validated initData
2. Query all groups where this user_id appears in our DB
3. For each group: check their Telegram status via bot.get_chat_member()
4. Return structured role data
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from config import settings
from db.client import db

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_user_telegram_status(bot, chat_id: int, user_id: int) -> str:
    """Check if user is admin/owner/member in a Telegram group."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        status = member.status
        if status == "creator":
            return "owner"
        elif status == "administrator":
            return "admin"
        elif status in ["member", "restricted"]:
            return "member"
        else:
            return "none"
    except Exception as e:
        logger.warning(
            f"[ME] Failed to get chat member status | chat_id={chat_id} user_id={user_id}: {e}"
        )
        return "unknown"


@router.get("")
async def get_user_context(user: dict = Depends(get_current_user)):
    """
    Get complete user context across all Nexus-managed groups.
    Determines role: owner, admin, mod, member, or stranger.
    """
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user data")

    logger.info(f"[ME] Getting user context | user_id={user_id}")

    # Get bot instance for checking Telegram status
    from bot.registry import get_all

    bots = get_all()
    if not bots:
        logger.error("[ME] No bots registered")
        raise HTTPException(status_code=503, detail="Bot service unavailable")

    # Use the bot that validated the user
    validated_bot_token = user.get("validated_bot_token")
    bot_app = None

    if validated_bot_token:
        for bid, app in bots.items():
            if app.bot.token == validated_bot_token:
                bot_app = app
                break

    # Fallback to primary bot if no match found (shouldn't happen with correct auth)
    if not bot_app:
        for bid, app in bots.items():
            if app.bot_data.get("is_primary"):
                bot_app = app
                break
        if not bot_app:
            for bid, app in bots.items():
                bot_app = app
                break

    if not bot_app:
        raise HTTPException(status_code=503, detail="Bot service unavailable")

    from bot.utils.crypto import hash_token

    token_hash = hash_token(bot_app.bot.token)

    async with db.pool.acquire() as conn:
        # Bug E fix: Union fallback query - handle groups via bot_token_hash OR clone_bot_groups
        all_groups = await conn.fetch(
            """
            SELECT g.chat_id, g.title, g.member_count, g.settings,
                   g.photo_big, g.photo_small
            FROM groups g
            WHERE g.bot_token_hash = $1
            UNION
            SELECT g.chat_id, g.title, g.member_count, g.settings,
                   g.photo_big, g.photo_small
            FROM groups g
            JOIN clone_bot_groups cbg ON g.chat_id = cbg.chat_id
            JOIN bots b ON b.bot_id = cbg.bot_id
            WHERE b.token_hash = $1
            ORDER BY title
        """,
            token_hash,
        )

        if not all_groups:
            logger.warning(
                f"[ME] No groups found for bot token_hash="
                f"{token_hash[:8]}... — check hash consistency"
            )
            all_groups = []

    import asyncio

    admin_groups = []
    mod_groups = []
    member_groups = []

    async def _process_group(group_row):
        chat_id = group_row["chat_id"]
        title = group_row["title"]
        member_count = group_row["member_count"]
        photo_big = group_row.get("photo_big")
        group_settings = group_row["settings"] or {}
        if isinstance(group_settings, str):
            try:
                group_settings = json.loads(group_settings)
            except Exception:
                group_settings = {}

        status = await get_user_telegram_status(bot_app.bot, chat_id, user_id)
        return chat_id, title, member_count, photo_big, group_settings, status

    results = await asyncio.gather(
        *[_process_group(row) for row in all_groups], return_exceptions=True
    )

    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"[ME] Error processing group: {result}")
            continue
        chat_id, title, member_count, photo_big, group_settings, status = result

        # Main dashboard: only show groups where user is actually a Telegram member/admin
        if status in ["owner", "admin"]:
            boost_settings = group_settings.get("member_boost", {})
            channel_settings = group_settings.get("channel_gate", {})

            admin_groups.append(
                {
                    "chat_id": chat_id,
                    "title": title,
                    "username": None,
                    "member_count": member_count or 0,
                    "photo_big": photo_big,
                    "is_owner": status == "owner",
                    "boost_enabled": boost_settings.get("force_add_enabled", False),
                    "channel_gate_enabled": channel_settings.get("force_channel_enabled", False),
                }
            )
        elif status == "member":
            boost_record = await get_member_boost_stats(chat_id, user_id)
            channel_record = await get_member_channel_status(chat_id, user_id)
            trust_score = await get_member_trust_score(chat_id, user_id)
            warn_count = await get_member_warn_count(chat_id, user_id)
            warn_limit = await get_warn_limit(chat_id)

            member_groups.append(
                {
                    "chat_id": chat_id,
                    "title": title,
                    "member_count": member_count or 0,
                    "boost_status": boost_record,
                    "channel_status": channel_record,
                    "trust_score": trust_score,
                    "warn_status": {"count": warn_count, "limit": warn_limit},
                }
            )

    # Determine highest role
    if admin_groups:
        # Check if any are owner
        is_owner = any(g.get("is_owner") for g in admin_groups)
        role = "owner" if is_owner else "admin"
    elif mod_groups:
        role = "mod"
    elif member_groups:
        role = "member"
    else:
        role = "stranger"

    # Check if user is the owner (for owner panel gating)
    is_sudo = user_id == settings.OWNER_ID

    # Check bot ownership from auth layer (if user came through clone bot auth)
    is_clone_owner = user.get("is_clone_owner", False)
    is_overlord = user.get("is_overlord", False) or is_sudo

    # Build user object
    user_obj = {
        "id": user_id,
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "username": user.get("username", ""),
        "photo_url": user.get("photo_url"),
        "language_code": user.get("language_code"),
    }

    # Get bot info for the UI
    try:
        bot_me = await bot_app.bot.get_me()
        bot_info = {"username": bot_me.username, "first_name": bot_me.first_name, "id": bot_me.id}
    except Exception as e:
        logger.warning(f"[ME] Failed to get bot info: {e}")
        bot_info = {"username": "NexusBot", "first_name": "Nexus", "id": 0}

    all_managed_groups = admin_groups + mod_groups

    response = {
        "user": user_obj,
        "user_id": user_id,
        "role": role,
        "is_sudo": is_sudo,
        "is_overlord": is_overlord,
        "is_clone_owner": is_clone_owner,
        "is_bot_owner": is_sudo or is_clone_owner,  # Convenience flag for UI
        "groups": all_managed_groups,
        "admin_groups": admin_groups,
        "mod_groups": mod_groups,
        "member_groups": member_groups,
        "bot_info": bot_info,
        "support_group": (
            settings.SUPPORT_GROUP_URL if hasattr(settings, "SUPPORT_GROUP_URL") else None
        ),
    }

    logger.info(
        f"[ME] User context ready | user_id={user_id} role={role} is_sudo={is_sudo} "
        f"is_clone_owner={is_clone_owner} is_overlord={is_overlord} "
        f"bot_id={bot_info.get('id')} bot_username={bot_info.get('username')} "
        f"admin={len(admin_groups)} member={len(member_groups)}"
    )

    return response


async def get_member_boost_stats(group_id: int, user_id: int) -> dict:
    """Get boost stats for a specific member in a group."""
    from db.ops.booster import get_boost_config, get_boost_record

    config = await get_boost_config(group_id)
    record = await get_boost_record(group_id, user_id)

    if not record and not config.get("force_add_enabled"):
        return {"enabled": False}

    required = config.get("force_add_required", 5)
    current = record["invited_count"] + record["manual_credits"] if record else 0

    return {
        "enabled": config.get("force_add_enabled", False),
        "required": required,
        "current": current,
        "is_unlocked": record.get("is_unlocked", True) if record else True,
        "is_restricted": record.get("is_restricted", False) if record else False,
        "invite_link": record.get("invite_link") if record else None,
        "progress_style": config.get("force_add_progress_style", "blocks"),
    }


async def get_member_channel_status(group_id: int, user_id: int) -> dict:
    """Get channel verification status for a member."""
    from db.ops.booster import get_channel_gate_config, get_channel_record

    config = await get_channel_gate_config(group_id)
    record = await get_channel_record(group_id, user_id)

    if not config.get("force_channel_enabled"):
        return {"enabled": False}

    return {
        "enabled": True,
        "channel_username": config.get("force_channel_username"),
        "channel_id": config.get("force_channel_id"),
        "is_verified": record["is_verified"] if record else False,
        "is_restricted": record["is_restricted"] if record else False,
        "channel_invite": (
            f"t.me/{config.get('force_channel_username')}"
            if config.get("force_channel_username")
            else None
        ),
    }


async def get_member_trust_score(group_id: int, user_id: int) -> int:
    """Get trust score for a member."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT trust_score FROM users WHERE user_id = $1 AND chat_id = $2", user_id, group_id
        )
        return row["trust_score"] if row else 50


async def get_member_warn_count(group_id: int, user_id: int) -> int:
    """Get warning count for a member."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT warns FROM users WHERE user_id = $1 AND chat_id = $2", user_id, group_id
        )
        if row and row["warns"]:
            raw = row["warns"]
            if isinstance(raw, list):
                return len(raw)
            if isinstance(raw, str):
                try:
                    return len(json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    return 0
        return 0


@router.get("/usage")
async def get_usage(user: dict = Depends(get_current_user)):
    """Return usage stats for the current owner."""
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user data")

    async with db.pool.acquire() as conn:
        # Get total bots count (including primary)
        bots_count = (
            await conn.fetchval("SELECT COUNT(*) FROM bots WHERE owner_user_id=$1", user_id) or 0
        )

        # Get non-primary bots count (clones) - for the limit bar
        clone_count = (
            await conn.fetchval(
                "SELECT COUNT(*) FROM bots WHERE owner_user_id=$1 AND is_primary=FALSE", user_id
            )
            or 0
        )

        # Get groups count with correct JOIN on token_hash
        groups_count = (
            await conn.fetchval(
                """SELECT COUNT(DISTINCT g.chat_id)
               FROM groups g
               INNER JOIN bots b ON b.token_hash = g.bot_token_hash
               WHERE b.owner_user_id = $1""",
                user_id,
            )
            or 0
        )

        # Get plan limits from primary bot
        primary_bot = await conn.fetchrow(
            "SELECT group_limit FROM bots WHERE owner_user_id=$1 AND is_primary=TRUE", user_id
        )

    # Query for active subscription to get actual plan_name first
    plan_name = "Free"
    try:
        async with db.pool.acquire() as conn:
            subscription = await conn.fetchrow(
                """SELECT plan, plan_expires_at FROM billing_subscriptions
                   WHERE owner_id = $1
                     AND plan_expires_at > NOW()
                   ORDER BY created_at DESC LIMIT 1""",
                user_id,
            )
        if subscription:
            plan_name = subscription["plan"].title()
    except Exception as e:
        logger.warning(f"[ME] Could not fetch subscription info: {e}")

    # Determine limits based on plan
    group_limit = 10  # default for free
    if primary_bot:
        gl = primary_bot.get("group_limit") or 0
        # 0 = unlimited (primary bot on any plan)
        group_limit = gl if gl > 0 else 0

    # Clone bot limit: derive from plan config
    PLAN_BOT_LIMITS = {"free": 3, "starter": 5, "pro": 10, "enterprise": 50}
    plan_key = plan_name.lower() if plan_name else "free"
    bot_limit = PLAN_BOT_LIMITS.get(plan_key, 3)

    return {
        "bots_count": int(bots_count),
        "clone_count": int(clone_count),
        "groups_count": int(groups_count),
        "plan_limit_bots": bot_limit,
        "plan_limit_groups": group_limit,
        "plan_name": plan_name,
    }


async def get_warn_limit(group_id: int) -> int:
    """Get warning limit for a group."""
    from db.ops.groups import get_group

    group = await get_group(group_id)
    if group and group.get("settings"):
        return group["settings"].get("warnings", {}).get("threshold", 3)
    return 3
