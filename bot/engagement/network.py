"""
bot/engagement/network.py

Cross-group network system.

Log prefix: [NETWORK]
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("network")

BROADCAST_COOLDOWN_HOURS = 1


async def create_network(
    pool,
    name: str,
    description: Optional[str],
    owner_user_id: int,
    owner_bot_id: int
) -> dict:
    from db.ops.engagement import create_network as db_create
    result = await db_create(pool, name, description, owner_user_id, owner_bot_id)
    if result:
        log.info(f"[NETWORK] Created '{name}' | owner={owner_user_id} code={result.get('invite_code')}")
    return {"ok": bool(result), "network_id": result.get("id"), "invite_code": result.get("invite_code")}


async def join_network(
    pool,
    invite_code: str,
    chat_id: int,
    bot_id: int
) -> tuple[bool, str]:
    from db.ops.engagement import get_network_by_code, join_network as db_join, sync_network_xp, get_xp_leaderboard

    network = await get_network_by_code(pool, invite_code)
    if not network:
        return False, "❌ Invalid invite code."

    network_id = network["id"]
    ok = await db_join(pool, network_id, chat_id, bot_id)
    if not ok:
        return False, "❌ Failed to join network (already a member?)."

    leaderboard = await get_xp_leaderboard(pool, chat_id, bot_id, limit=1000)
    for entry in leaderboard:
        asyncio.create_task(
            sync_network_xp(pool, network_id, entry["user_id"], entry["xp"])
        )

    log.info(f"[NETWORK] Joined | network={network_id} chat={chat_id}")
    return True, f"✅ Joined network '{network['name']}'!"


async def leave_network(pool, network_id: int, chat_id: int) -> bool:
    from db.ops.engagement import leave_network as db_leave
    ok = await db_leave(pool, network_id, chat_id)
    if ok:
        log.info(f"[NETWORK] Left | network={network_id} chat={chat_id}")
    return ok


async def broadcast_to_network(
    pool,
    bot,
    network_id: int,
    from_chat_id: int,
    sent_by: int,
    message_text: str
) -> int:
    from db.ops.engagement import (
        get_last_broadcast_time, log_network_broadcast,
        get_network_groups, update_broadcast_delivered
    )

    last = await get_last_broadcast_time(pool, network_id)
    if last:
        since = datetime.now(timezone.utc) - last
        if since < timedelta(hours=BROADCAST_COOLDOWN_HOURS):
            remaining = BROADCAST_COOLDOWN_HOURS - since.total_seconds() / 3600
            log.warning(f"[NETWORK] Broadcast rate limited | network={network_id}")
            return -1

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM group_networks WHERE id=$1", network_id)
            network_name = row["name"] if row else "Network"
            from_name = f"Group {from_chat_id}"
    except Exception:
        network_name = "Network"
        from_name = f"Group {from_chat_id}"

    formatted = (
        f"📢 <b>Network Announcement</b>\n"
        f"From: {from_name}\n"
        f"─────────────────\n"
        f"{message_text}\n"
        f"─────────────────\n"
        f"Powered by Nexus Bot"
    )

    ann_id = await log_network_broadcast(pool, network_id, from_chat_id, sent_by, message_text)
    groups = await get_network_groups(pool, network_id)
    delivered = 0

    for group in groups:
        if group["chat_id"] == from_chat_id:
            continue
        try:
            await bot.send_message(group["chat_id"], formatted, parse_mode="HTML")
            delivered += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            log.warning(f"[NETWORK] Broadcast failed for chat={group['chat_id']}: {e}")

    await update_broadcast_delivered(pool, ann_id, delivered)
    log.info(f"[NETWORK] Broadcast sent | network={network_id} delivered={delivered}")
    return delivered


async def get_network_leaderboard(
    pool,
    network_id: int,
    limit: int = 20
) -> list[dict]:
    from db.ops.engagement import get_network_leaderboard as db_get
    return await db_get(pool, network_id, limit)


async def sync_xp_to_network(
    pool,
    network_id: int,
    chat_id: int,
    user_id: int,
    xp_delta: int
):
    from db.ops.engagement import sync_network_xp
    await sync_network_xp(pool, network_id, user_id, xp_delta)


async def get_member_networks(pool, chat_id: int) -> list[dict]:
    from db.ops.engagement import get_chat_networks
    return await get_chat_networks(pool, chat_id)
