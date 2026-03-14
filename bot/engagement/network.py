"""
bot/engagement/network.py

Cross-group network system.
Groups join networks to share leaderboards and announcements.

Network owner:
- The bot owner who created the network
- Can add/remove groups from network
- Can broadcast to all groups in network
- Sees unified leaderboard across all groups

Network members:
- Any group using Nexus Bot
- Join via invite code
- Their members' XP contributes to network leaderboard
- Receive network announcements

Log prefix: [NETWORK]
"""

import logging
import secrets
import string
from datetime import datetime, timezone
from typing import List, Optional

log = logging.getLogger("network")

BROADCAST_RATE_LIMIT_HOURS = 1


def generate_invite_code(length: int = 8) -> str:
    """Generate a unique invite code."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def create_network(
    pool,
    name: str,
    description: str,
    owner_user_id: int,
    owner_bot_id: int
) -> dict:
    """
    Create a new network.
    Auto-generate unique invite_code (8 chars, uppercase).
    Add creator's first group automatically.
    Returns {ok, network_id, invite_code}
    """
    try:
        async with pool.acquire() as conn:
            # Generate unique invite code
            for _ in range(10):  # Try up to 10 times
                invite_code = generate_invite_code()

                # Check uniqueness
                existing = await conn.fetchrow(
                    "SELECT id FROM group_networks WHERE invite_code=$1",
                    invite_code
                )

                if not existing:
                    break
            else:
                return {"ok": False, "error": "Could not generate unique invite code"}

            # Create network
            row = await conn.fetchrow(
                """
                INSERT INTO group_networks
                    (name, description, owner_user_id, owner_bot_id, invite_code)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, invite_code
                """,
                name, description, owner_user_id, owner_bot_id, invite_code
            )

            log.info(
                f"[NETWORK] Created network '{name}' by user {owner_user_id}"
            )

            return {
                "ok": True,
                "network_id": row["id"],
                "invite_code": row["invite_code"]
            }

    except Exception as e:
        log.error(f"[NETWORK] Error creating network: {e}")
        return {"ok": False, "error": str(e)}


async def join_network(
    pool,
    invite_code: str,
    chat_id: int,
    bot_id: int
) -> tuple[bool, str]:
    """
    Join a network via invite code.
    Validates code exists and is valid.
    Adds to network_members table.
    Syncs existing member XP to network_xp.
    Returns (success, message)
    """
    try:
        async with pool.acquire() as conn:
            # Find network
            network = await conn.fetchrow(
                """
                SELECT * FROM group_networks
                WHERE invite_code=$1
                """,
                invite_code.upper()
            )

            if not network:
                return False, "Invalid invite code."

            # Check if already joined
            existing = await conn.fetchrow(
                """
                SELECT * FROM network_members
                WHERE network_id=$1 AND chat_id=$2
                """,
                network["id"], chat_id
            )

            if existing:
                return False, "Your group is already in this network."

            # Add to network
            await conn.execute(
                """
                INSERT INTO network_members
                    (network_id, chat_id, bot_id, role)
                VALUES ($1, $2, $3, 'member')
                """,
                network["id"], chat_id, bot_id
            )

            # Update member count
            await conn.execute(
                """
                UPDATE group_networks
                SET member_count = member_count + 1
                WHERE id=$1
                """,
                network["id"]
            )

            # Sync existing XP to network
            xp_rows = await conn.fetch(
                """
                SELECT user_id, xp FROM member_xp
                WHERE chat_id=$1 AND bot_id=$2
                """,
                chat_id, bot_id
            )

            for row in xp_rows:
                await conn.execute(
                    """
                    INSERT INTO network_xp
                        (network_id, user_id, total_xp, contributing_groups)
                    VALUES ($1, $2, $3, 1)
                    ON CONFLICT (network_id, user_id)
                    DO UPDATE SET
                        total_xp = network_xp.total_xp + $3,
                        contributing_groups = network_xp.contributing_groups + 1,
                        last_updated = NOW()
                    """,
                    network["id"], row["user_id"], row["xp"]
                )

            log.info(
                f"[NETWORK] Chat {chat_id} joined network '{network['name']}'"
            )

            return True, f"Successfully joined network '{network['name']}'!"

    except Exception as e:
        log.error(f"[NETWORK] Error joining network: {e}")
        return False, f"Error: {str(e)}"


async def leave_network(
    pool,
    network_id: int,
    chat_id: int
) -> bool:
    """Remove group from network."""
    try:
        async with pool.acquire() as conn:
            # Check if member
            existing = await conn.fetchrow(
                """
                SELECT * FROM network_members
                WHERE network_id=$1 AND chat_id=$2
                """,
                network_id, chat_id
            )

            if not existing:
                return False

            # Remove from network
            await conn.execute(
                """
                DELETE FROM network_members
                WHERE network_id=$1 AND chat_id=$2
                """,
                network_id, chat_id
            )

            # Update member count
            await conn.execute(
                """
                UPDATE group_networks
                SET member_count = member_count - 1
                WHERE id=$1
                """,
                network_id
            )

            log.info(f"[NETWORK] Chat {chat_id} left network {network_id}")
            return True

    except Exception as e:
        log.error(f"[NETWORK] Error leaving network: {e}")
        return False


async def broadcast_to_network(
    pool,
    bot,
    network_id: int,
    from_chat_id: int,
    sent_by: int,
    message_text: str
) -> int:
    """
    Send announcement to all groups in network.
    Format:
    📢 Network Announcement
    From: Group Name
    ─────────────────
    message text here
    ─────────────────
    Powered by Nexus Bot

    Returns count of groups delivered to.
    Rate limits: 1 broadcast per hour per network.
    """
    try:
        async with pool.acquire() as conn:
            # Check rate limit
            last_broadcast = await conn.fetchrow(
                """
                SELECT sent_at FROM network_announcements
                WHERE network_id=$1
                ORDER BY sent_at DESC
                LIMIT 1
                """,
                network_id
            )

            if last_broadcast:
                hours_since = (
                    datetime.now(timezone.utc) - last_broadcast["sent_at"]
                ).total_seconds() / 3600

                if hours_since < BROADCAST_RATE_LIMIT_HOURS:
                    return 0

            # Get network info
            network = await conn.fetchrow(
                "SELECT * FROM group_networks WHERE id=$1",
                network_id
            )

            if not network:
                return 0

            # Get all member groups
            members = await conn.fetch(
                """
                SELECT chat_id FROM network_members
                WHERE network_id=$1
                """,
                network_id
            )

            # Get sender group name
            try:
                chat = await bot.get_chat(from_chat_id)
                from_name = chat.title or "Unknown"
            except Exception:
                from_name = "Unknown"

            # Format message
            formatted_text = (
                f"📢 <b>Network Announcement</b>\n"
                f"From: {from_name}\n"
                f"─────────────────\n\n"
                f"{message_text}\n\n"
                f"─────────────────\n"
                f"Powered by Nexus Bot"
            )

            delivered = 0
            for member in members:
                try:
                    await bot.send_message(
                        chat_id=member["chat_id"],
                        text=formatted_text,
                        parse_mode="HTML"
                    )
                    delivered += 1
                except Exception as e:
                    log.warning(
                        f"[NETWORK] Failed to send to chat {member['chat_id']}: {e}"
                    )

            # Log broadcast
            await conn.execute(
                """
                INSERT INTO network_announcements
                    (network_id, from_chat_id, sent_by, message_text, delivered_to)
                VALUES ($1, $2, $3, $4, $5)
                """,
                network_id, from_chat_id, sent_by, message_text, delivered
            )

            log.info(
                f"[NETWORK] Broadcast sent to {delivered}/{len(members)} groups"
            )
            return delivered

    except Exception as e:
        log.error(f"[NETWORK] Error broadcasting: {e}")
        return 0


async def get_network_leaderboard(
    pool,
    network_id: int,
    limit: int = 20
) -> list[dict]:
    """
    Unified leaderboard across all groups in network.
    Sums XP from all groups for each user.
    Returns [{rank, user_id, total_xp, contributing_groups}]
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, total_xp, contributing_groups,
                       ROW_NUMBER() OVER (ORDER BY total_xp DESC) as rank
                FROM network_xp
                WHERE network_id=$1
                ORDER BY total_xp DESC
                LIMIT $2
                """,
                network_id, limit
            )

            return [
                {
                    "rank": row["rank"],
                    "user_id": row["user_id"],
                    "total_xp": row["total_xp"],
                    "contributing_groups": row["contributing_groups"]
                }
                for row in rows
            ]

    except Exception as e:
        log.error(f"[NETWORK] Error getting leaderboard: {e}")
        return []


async def sync_xp_to_network(
    pool,
    network_id: int,
    chat_id: int,
    user_id: int,
    xp_delta: int
):
    """
    Called after every XP award if group is in a network.
    Updates network_xp for this user.
    Fast — just an upsert.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO network_xp
                    (network_id, user_id, total_xp, contributing_groups, last_updated)
                VALUES ($1, $2, $3, 1, NOW())
                ON CONFLICT (network_id, user_id)
                DO UPDATE SET
                    total_xp = network_xp.total_xp + $3,
                    last_updated = NOW()
                """,
                network_id, user_id, xp_delta
            )

    except Exception as e:
        log.error(f"[NETWORK] Error syncing XP: {e}")


async def get_member_networks(pool, chat_id: int) -> list[dict]:
    """Get all networks a group belongs to."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT gn.id, gn.name, gn.description, gn.invite_code,
                       gn.is_public, gn.member_count, nm.role
                FROM network_members nm
                JOIN group_networks gn ON nm.network_id = gn.id
                WHERE nm.chat_id=$1
                """,
                chat_id
            )

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "invite_code": row["invite_code"],
                    "is_public": row["is_public"],
                    "member_count": row["member_count"],
                    "role": row["role"]
                }
                for row in rows
            ]

    except Exception as e:
        log.error(f"[NETWORK] Error getting member networks: {e}")
        return []


async def get_network_details(pool, network_id: int) -> Optional[dict]:
    """Get detailed info about a network."""
    try:
        async with pool.acquire() as conn:
            network = await conn.fetchrow(
                "SELECT * FROM group_networks WHERE id=$1",
                network_id
            )

            if not network:
                return None

            members = await conn.fetch(
                """
                SELECT chat_id, bot_id, role, joined_at
                FROM network_members
                WHERE network_id=$1
                """,
                network_id
            )

            return {
                "id": network["id"],
                "name": network["name"],
                "description": network["description"],
                "owner_user_id": network["owner_user_id"],
                "owner_bot_id": network["owner_bot_id"],
                "invite_code": network["invite_code"],
                "is_public": network["is_public"],
                "member_count": network["member_count"],
                "created_at": network["created_at"].isoformat() if network["created_at"] else None,
                "members": [
                    {
                        "chat_id": m["chat_id"],
                        "bot_id": m["bot_id"],
                        "role": m["role"],
                        "joined_at": m["joined_at"].isoformat() if m["joined_at"] else None
                    }
                    for m in members
                ]
            }

    except Exception as e:
        log.error(f"[NETWORK] Error getting network details: {e}")
        return None


async def is_network_owner(
    pool,
    network_id: int,
    user_id: int
) -> bool:
    """Check if user is the network owner."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT owner_user_id FROM group_networks
                WHERE id=$1
                """,
                network_id
            )

            return row and row["owner_user_id"] == user_id

    except Exception as e:
        log.error(f"[NETWORK] Error checking owner: {e}")
        return False
