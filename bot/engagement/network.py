"""
bot/engagement/network.py

Cross-group network system.
Groups join networks to share leaderboards and announcements.

Log prefix: [NETWORK]
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("network")

BROADCAST_COOLDOWN_HOURS = 1


async def create_network(
    pool,
    name: str,
    description: str,
    owner_user_id: int,
    owner_bot_id: int,
) -> dict:
    """
    Create a new network.
    Auto-generate unique invite_code (8 chars, uppercase).
    Returns {ok, network_id, invite_code}
    """
    try:
        from db.ops.engagement import create_network as db_create, join_network
        network = await db_create(pool, name, description, owner_user_id, owner_bot_id)
        log.info(f"[NETWORK] Created '{name}' | owner={owner_user_id} code={network['invite_code']}")
        return {"ok": True, "network_id": network["id"], "invite_code": network["invite_code"]}
    except Exception as e:
        log.error(f"[NETWORK] create_network error | err={e}")
        return {"ok": False, "reason": str(e)}


async def join_network(
    pool,
    invite_code: str,
    chat_id: int,
    bot_id: int,
) -> tuple[bool, str]:
    """Join a network via invite code."""
    try:
        from db.ops.engagement import (
            get_network_by_code, join_network as db_join,
            get_xp_leaderboard, sync_network_xp,
        )

        network = await get_network_by_code(pool, invite_code)
        if not network:
            return False, "❌ Invalid invite code."

        success = await db_join(pool, network["id"], chat_id, bot_id)
        if not success:
            return False, "❌ Already a member of this network."

        leaderboard = await get_xp_leaderboard(pool, chat_id, bot_id, limit=100)
        for entry in leaderboard:
            await sync_network_xp(pool, network["id"], entry["user_id"], entry["xp"])

        log.info(f"[NETWORK] Joined '{network['name']}' | chat={chat_id}")
        return True, f"✅ Joined network **{network['name']}**! Invite code: `{invite_code}`"
    except Exception as e:
        log.error(f"[NETWORK] join_network error | err={e}")
        return False, f"❌ Failed: {e}"


async def leave_network(
    pool,
    network_id: int,
    chat_id: int,
) -> bool:
    """Remove group from network."""
    from db.ops.engagement import leave_network as db_leave
    result = await db_leave(pool, network_id, chat_id)
    if result:
        log.info(f"[NETWORK] Left network={network_id} | chat={chat_id}")
    return result


async def broadcast_to_network(
    pool,
    bot,
    network_id: int,
    from_chat_id: int,
    sent_by: int,
    message_text: str,
) -> int:
    """
    Send announcement to all groups in network.
    Rate limits: 1 broadcast per hour per network.
    Returns count of groups delivered to.
    """
    try:
        import asyncio
        from db.ops.engagement import (
            get_last_broadcast_time, get_network_groups,
            log_network_broadcast, update_broadcast_delivered,
        )

        last_broadcast = await get_last_broadcast_time(pool, network_id)
        if last_broadcast:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=BROADCAST_COOLDOWN_HOURS)
            if last_broadcast.replace(tzinfo=timezone.utc) > cutoff:
                return -1

        announcement_id = await log_network_broadcast(
            pool, network_id, from_chat_id, sent_by, message_text
        )

        groups = await get_network_groups(pool, network_id)
        delivered = 0

        formatted = (
            f"📢 <b>Network Announcement</b>\n"
            f"─────────────────\n"
            f"{message_text}\n"
            f"─────────────────\n"
            f"<i>Powered by Nexus Bot</i>"
        )

        for group in groups:
            gid = group["chat_id"]
            try:
                await bot.send_message(gid, formatted, parse_mode="HTML")
                delivered += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                log.warning(f"[NETWORK] Broadcast failed | chat={gid} err={e}")

        await update_broadcast_delivered(pool, announcement_id, delivered)
        log.info(f"[NETWORK] Broadcast delivered to {delivered}/{len(groups)} groups")
        return delivered
    except Exception as e:
        log.error(f"[NETWORK] broadcast_to_network error | err={e}")
        return 0


async def get_network_leaderboard(
    pool,
    network_id: int,
    limit: int = 20,
) -> list[dict]:
    """Unified leaderboard across all groups in network."""
    from db.ops.engagement import get_network_leaderboard as db_get
    return await db_get(pool, network_id, limit)


async def sync_xp_to_network(
    pool,
    network_id: int,
    chat_id: int,
    user_id: int,
    xp_delta: int,
):
    """Called after every XP award if group is in a network."""
    from db.ops.engagement import sync_network_xp
    await sync_network_xp(pool, network_id, user_id, xp_delta)


async def get_member_networks(pool, chat_id: int) -> list[dict]:
    """Get all networks a group belongs to."""
    from db.ops.engagement import get_chat_networks
    return await get_chat_networks(pool, chat_id)
