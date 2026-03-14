import json
import logging
from datetime import datetime, timezone
from typing import Optional
from db.client import db

logger = logging.getLogger(__name__)


# ==================== Member Boost Records ====================


async def get_boost_record(group_id: int, user_id: int) -> Optional[dict]:
    """Get a user's boost record for a group."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM member_boost_records WHERE group_id = $1 AND user_id = $2",
            group_id,
            user_id,
        )
        return dict(row) if row else None


async def create_boost_record(
    group_id: int,
    user_id: int,
    username: str = None,
    first_name: str = None,
    invite_link: str = None,
    invite_link_name: str = None,
    required_count: int = 0,
    join_source: str = "unknown",
) -> dict:
    """Create a new boost record for a user joining a group."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO member_boost_records 
            (group_id, user_id, username, first_name, invite_link, invite_link_name, required_count, join_source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (group_id, user_id) DO UPDATE 
            SET username = EXCLUDED.username, first_name = EXCLUDED.first_name
            RETURNING *
        """,
            group_id,
            user_id,
            username,
            first_name,
            invite_link,
            invite_link_name,
            required_count,
            join_source,
        )
        return dict(row)


async def update_invite_count(group_id: int, user_id: int, delta: int = 1) -> Optional[dict]:
    """Increment the invite count for a user. Returns updated record."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE member_boost_records 
            SET invited_count = invited_count + $3, updated_at = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
            delta,
        )
        return dict(row) if row else None


async def update_manual_credits(group_id: int, user_id: int, credits: int) -> Optional[dict]:
    """Add manual credits to a user's boost record."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE member_boost_records 
            SET manual_credits = manual_credits + $3, updated_at = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
            credits,
        )
        return dict(row) if row else None


async def set_unlocked(group_id: int, user_id: int) -> Optional[dict]:
    """Mark a user's boost as complete/unlocked."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE member_boost_records 
            SET is_unlocked = TRUE, is_restricted = FALSE, unlocked_at = NOW(), updated_at = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
        )
        return dict(row) if row else None


async def set_restricted(group_id: int, user_id: int, restricted: bool = True) -> Optional[dict]:
    """Set restricted status for a boost record."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE member_boost_records 
            SET is_restricted = $3, updated_at = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
            restricted,
        )
        return dict(row) if row else None


async def set_exempted(
    group_id: int, user_id: int, exempted: bool, exempted_by: int = None, reason: str = None
) -> Optional[dict]:
    """Set exemption status for a user."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE member_boost_records 
            SET is_exempted = $3, exempted_by = $4, exemption_reason = $5, updated_at = NOW(),
                is_restricted = FALSE
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
            exempted,
            exempted_by,
            reason,
        )
        return dict(row) if row else None


async def reset_boost_record(group_id: int, user_id: int) -> bool:
    """Reset a user's boost record to zero."""
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE member_boost_records 
            SET invited_count = 0, manual_credits = 0, is_unlocked = FALSE, 
                is_restricted = FALSE, invite_link = NULL, invite_link_name = NULL,
                updated_at = NOW()
            WHERE group_id = $1 AND user_id = $2
        """,
            group_id,
            user_id,
        )
        return "UPDATE 1" in result


async def delete_boost_record(group_id: int, user_id: int) -> bool:
    """Delete a user's boost record."""
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM member_boost_records WHERE group_id = $1 AND user_id = $2",
            group_id,
            user_id,
        )
        return "DELETE 1" in result


async def get_all_boost_records(group_id: int) -> list:
    """Get all boost records for a group."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM member_boost_records WHERE group_id = $1 ORDER BY created_at DESC",
            group_id,
        )
        return [dict(row) for row in rows]


async def get_restricted_members(group_id: int) -> list:
    """Get all restricted members (still need to complete boost)."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM member_boost_records 
               WHERE group_id = $1 AND is_restricted = TRUE AND is_unlocked = FALSE 
               ORDER BY created_at DESC""",
            group_id,
        )
        return [dict(row) for row in rows]


async def get_exempted_users(group_id: int) -> list:
    """Get all exempted users in a group."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM member_boost_records WHERE group_id = $1 AND is_exempted = TRUE",
            group_id,
        )
        return [dict(row) for row in rows]


async def get_boost_stats(group_id: int) -> dict:
    """Get boost statistics for a group."""
    async with db.pool.acquire() as conn:
        locked = await conn.fetchval(
            "SELECT COUNT(*) FROM member_boost_records WHERE group_id = $1 AND is_restricted = TRUE AND is_unlocked = FALSE",
            group_id,
        )
        unlocked = await conn.fetchval(
            "SELECT COUNT(*) FROM member_boost_records WHERE group_id = $1 AND is_unlocked = TRUE",
            group_id,
        )
        exempted = await conn.fetchval(
            "SELECT COUNT(*) FROM member_boost_records WHERE group_id = $1 AND is_exempted = TRUE",
            group_id,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM member_boost_records WHERE group_id = $1", group_id
        )

        top_inviters = await conn.fetch(
            """
            SELECT user_id, username, first_name, (invited_count + manual_credits) as total_invites
            FROM member_boost_records 
            WHERE group_id = $1 
            ORDER BY total_invites DESC 
            LIMIT 10
        """,
            group_id,
        )

        return {
            "locked_count": locked or 0,
            "unlocked_count": unlocked or 0,
            "exempted_count": exempted or 0,
            "total_records": total or 0,
            "top_inviters": [dict(row) for row in top_inviters],
        }


async def grant_access(group_id: int, user_id: int) -> Optional[dict]:
    """Manually grant full access without requiring invites."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE member_boost_records 
            SET is_unlocked = TRUE, is_restricted = FALSE, unlocked_at = NOW(), updated_at = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
        )
        return dict(row) if row else None


async def revoke_access(group_id: int, user_id: int) -> Optional[dict]:
    """Revoke manually granted access."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE member_boost_records 
            SET is_unlocked = FALSE, updated_at = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
        )
        return dict(row) if row else None


# ==================== Invite Events ====================


async def record_invite_event(
    group_id: int,
    inviter_user_id: int,
    invited_user_id: int,
    invited_username: str = None,
    invited_first_name: str = None,
    invite_link: str = None,
    source: str = "link",
) -> dict:
    """Record an invite event."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO member_invite_events 
            (group_id, inviter_user_id, invited_user_id, invited_username, invited_first_name, invite_link, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (group_id, invited_user_id) DO NOTHING
            RETURNING *
        """,
            group_id,
            inviter_user_id,
            invited_user_id,
            invited_username,
            invited_first_name,
            invite_link,
            source,
        )
        return dict(row) if row else None


async def get_invited_by(group_id: int, invited_user_id: int) -> Optional[dict]:
    """Get who invited a specific user."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM member_invite_events WHERE group_id = $1 AND invited_user_id = $2",
            group_id,
            invited_user_id,
        )
        return dict(row) if row else None


async def get_user_invites(group_id: int, inviter_user_id: int) -> list:
    """Get all users a person has invited."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM member_invite_events WHERE group_id = $1 AND inviter_user_id = $2 ORDER BY joined_at DESC",
            group_id,
            inviter_user_id,
        )
        return [dict(row) for row in rows]


async def get_recent_invite_events(group_id: int, limit: int = 50) -> list:
    """Get recent invite events."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM member_invite_events WHERE group_id = $1 ORDER BY joined_at DESC LIMIT $2",
            group_id,
            limit,
        )
        return [dict(row) for row in rows]


# ==================== Manual Add Credits ====================


async def create_credit_request(
    group_id: int,
    claimant_user_id: int,
    claimant_username: str = None,
    claimed_count: int = 1,
    claimed_user_ids: list = None,
) -> dict:
    """Create a pending credit request."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO manual_add_credits 
            (group_id, claimant_user_id, claimant_username, claimed_count, claimed_user_ids)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """,
            group_id,
            claimant_user_id,
            claimant_username,
            claimed_count,
            json.dumps(claimed_user_ids) if claimed_user_ids else json.dumps([]),
        )
        return dict(row)


async def get_pending_credit_requests(group_id: int) -> list:
    """Get all pending credit requests."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM manual_add_credits WHERE group_id = $1 AND status = 'pending' ORDER BY created_at DESC",
            group_id,
        )
        return [dict(row) for row in rows]


async def get_credit_request(group_id: int, request_id: int) -> Optional[dict]:
    """Get a specific credit request."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM manual_add_credits WHERE group_id = $1 AND id = $2", group_id, request_id
        )
        return dict(row) if row else None


async def approve_credit_request(
    group_id: int, request_id: int, amount: int, reviewed_by: int, note: str = None
) -> Optional[dict]:
    """Approve a credit request."""
    async with db.pool.acquire() as conn:
        # Get the request first
        request = await conn.fetchrow(
            "SELECT * FROM manual_add_credits WHERE group_id = $1 AND id = $2", group_id, request_id
        )
        if not request:
            return None

        # Update the request status
        await conn.execute(
            """
            UPDATE manual_add_credits 
            SET status = 'approved', approved_count = $3, reviewed_by = $4, 
                review_note = $5, reviewed_at = NOW()
            WHERE group_id = $1 AND id = $2
        """,
            group_id,
            request_id,
            amount,
            reviewed_by,
            note,
        )

        # Add credits to the claimant's boost record
        await conn.execute(
            """
            INSERT INTO member_boost_records (group_id, user_id, username, manual_credits)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (group_id, user_id) DO UPDATE 
            SET manual_credits = member_boost_records.manual_credits + $4,
                updated_at = NOW()
        """,
            group_id,
            request["claimant_user_id"],
            request["claimant_username"],
            amount,
        )

        row = await conn.fetchrow(
            "SELECT * FROM manual_add_credits WHERE group_id = $1 AND id = $2", group_id, request_id
        )
        return dict(row) if row else None


async def deny_credit_request(
    group_id: int, request_id: int, reviewed_by: int, reason: str = None
) -> Optional[dict]:
    """Deny a credit request."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE manual_add_credits 
            SET status = 'denied', reviewed_by = $3, review_note = $4, reviewed_at = NOW()
            WHERE group_id = $1 AND id = $2
        """,
            group_id,
            request_id,
            reviewed_by,
            reason,
        )

        row = await conn.fetchrow(
            "SELECT * FROM manual_add_credits WHERE group_id = $1 AND id = $2", group_id, request_id
        )
        return dict(row) if row else None


# ==================== Manual Adds Detected ====================


async def record_manual_add(
    group_id: int,
    added_user_id: int,
    added_username: str = None,
    added_first_name: str = None,
    added_by_user_id: int = None,
) -> dict:
    """Record a detected manual add (no invite link)."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO manual_adds_detected 
            (group_id, added_user_id, added_username, added_first_name, added_by_user_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """,
            group_id,
            added_user_id,
            added_username,
            added_first_name,
            added_by_user_id,
        )
        return dict(row)


async def get_unassigned_adds(group_id: int, hours: int = 24) -> list:
    """Get manual adds that haven't been credited yet."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM manual_adds_detected
            WHERE group_id = $1 AND credited_to IS NULL
            AND detected_at > NOW() - ($2 || ' hours')::INTERVAL
            ORDER BY detected_at DESC
        """,
            group_id,
            hours,
        )
        return [dict(row) for row in rows]


async def get_recent_manual_adds(group_id: int, hours: int = 2) -> list:
    """Get recent manual adds for correlation with credit claims."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM manual_adds_detected
            WHERE group_id = $1 AND detected_at > NOW() - ($2 || ' hours')::INTERVAL
            ORDER BY detected_at DESC
        """,
            group_id,
            hours,
        )
        return [dict(row) for row in rows]


async def assign_manual_add_credit(
    group_id: int, added_user_id: int, credited_to_user_id: int
) -> bool:
    """Assign credit for a manual add to a specific user."""
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE manual_adds_detected 
            SET credited_to = $3
            WHERE group_id = $1 AND added_user_id = $2 AND credited_to IS NULL
        """,
            group_id,
            added_user_id,
            credited_to_user_id,
        )

        if "UPDATE 1" in result:
            # Also update the inviter's count
            await conn.execute(
                """
                UPDATE member_boost_records 
                SET invited_count = invited_count + 1, updated_at = NOW()
                WHERE group_id = $1 AND user_id = $2
            """,
                group_id,
                credited_to_user_id,
            )

            # Record the invite event
            await conn.execute(
                """
                INSERT INTO member_invite_events 
                (group_id, inviter_user_id, invited_user_id, source)
                VALUES ($1, $2, $3, 'manual_credit')
                ON CONFLICT (group_id, invited_user_id) DO NOTHING
            """,
                group_id,
                credited_to_user_id,
                added_user_id,
            )

            return True
        return False


# ==================== Force Channel Records ====================


async def get_channel_record(group_id: int, user_id: int) -> Optional[dict]:
    """Get a user's channel verification record."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM force_channel_records WHERE group_id = $1 AND user_id = $2",
            group_id,
            user_id,
        )
        return dict(row) if row else None


async def create_channel_record(
    group_id: int, user_id: int, username: str = None, channel_id: int = None
) -> dict:
    """Create a channel verification record for a user."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO force_channel_records 
            (group_id, user_id, username, channel_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (group_id, user_id) DO UPDATE 
            SET username = EXCLUDED.username, channel_id = COALESCE(EXCLUDED.channel_id, force_channel_records.channel_id)
            RETURNING *
        """,
            group_id,
            user_id,
            username,
            channel_id,
        )
        return dict(row)


async def set_channel_verified(group_id: int, user_id: int) -> Optional[dict]:
    """Mark a user as verified channel member."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE force_channel_records 
            SET is_verified = TRUE, is_restricted = FALSE, verified_at = NOW(), last_checked = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
        )
        return dict(row) if row else None


async def set_channel_restricted(
    group_id: int, user_id: int, restricted: bool = True
) -> Optional[dict]:
    """Set restricted status for channel verification."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE force_channel_records 
            SET is_restricted = $3, last_checked = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
            restricted,
        )
        return dict(row) if row else None


async def increment_check_count(group_id: int, user_id: int) -> Optional[dict]:
    """Increment the check count for a user."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE force_channel_records 
            SET check_count = check_count + 1, last_checked = NOW()
            WHERE group_id = $1 AND user_id = $2
            RETURNING *
        """,
            group_id,
            user_id,
        )
        return dict(row) if row else None


async def get_unverified_channel_users(group_id: int) -> list:
    """Get all users who haven't verified channel membership."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM force_channel_records WHERE group_id = $1 AND is_verified = FALSE ORDER BY last_checked DESC",
            group_id,
        )
        return [dict(row) for row in rows]


async def get_channel_stats(group_id: int) -> dict:
    """Get channel gate statistics."""
    async with db.pool.acquire() as conn:
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM force_channel_records WHERE group_id = $1 AND is_verified = FALSE",
            group_id,
        )
        verified = await conn.fetchval(
            "SELECT COUNT(*) FROM force_channel_records WHERE group_id = $1 AND is_verified = TRUE",
            group_id,
        )

        avg_time = await conn.fetchval(
            """
            SELECT AVG(EXTRACT(EPOCH FROM (verified_at - last_checked)))
            FROM force_channel_records 
            WHERE group_id = $1 AND verified_at IS NOT NULL
        """,
            group_id,
        )

        return {
            "pending_count": pending or 0,
            "verified_count": verified or 0,
            "avg_verify_seconds": int(avg_time) if avg_time else 0,
        }


async def delete_channel_record(group_id: int, user_id: int) -> bool:
    """Delete a channel verification record."""
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM force_channel_records WHERE group_id = $1 AND user_id = $2",
            group_id,
            user_id,
        )
        return "DELETE 1" in result


async def delete_all_channel_records(group_id: int) -> bool:
    """Delete all channel records for a group."""
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM force_channel_records WHERE group_id = $1", group_id)
        return True


# ==================== Boost Config (stored in group settings) ====================


async def get_boost_config(group_id: int) -> dict:
    """Get boost configuration from group settings."""
    from db.ops.groups import get_group

    group = await get_group(group_id)
    if not group:
        return get_default_boost_config()

    settings = group.get("settings", {})
    boost_settings = settings.get("member_boost", {})

    default_config = get_default_boost_config()
    default_config.update(boost_settings)
    return default_config


async def save_boost_config(group_id: int, config: dict) -> bool:
    """Save boost configuration to group settings."""
    from db.ops.groups import get_group, upsert_group

    group = await get_group(group_id)
    settings = group.get("settings", {}) if group else {}
    settings["member_boost"] = config

    await upsert_group(
        group_id,
        group.get("title", "Unknown") if group else "Unknown",
        group.get("bot_token_hash", "") if group else "",
        settings,
    )
    return True


def get_default_boost_config() -> dict:
    """Get default boost configuration."""
    return {
        "force_add_enabled": False,
        "force_add_required": 5,
        "force_add_action": "mute",
        "force_add_message": (
            "👋 Welcome {first_name}!\n\n"
            "This group requires you to invite {required} member(s) "
            "before you can send messages.\n\n"
            "🔗 Your personal invite link:\n{link}\n\n"
            "📊 Progress: {bar} {current}/{required}\n\n"
            "Share your link and you'll unlock access automatically!"
        ),
        "force_add_unlock_message": "🎉 {first_name} has unlocked access after inviting {count} members!",
        "force_add_progress_style": "blocks",
        "manual_add_credit_enabled": True,
        "manual_add_auto_detect": True,
        "manual_add_witness_mode": False,
        "exempt_admins": True,
        "exempt_specific_users": [],
        "notify_group_on_unlock": False,
        "log_channel_id": None,
    }


async def get_channel_gate_config(group_id: int) -> dict:
    """Get channel gate configuration from group settings."""
    from db.ops.groups import get_group

    group = await get_group(group_id)
    if not group:
        return get_default_channel_gate_config()

    settings = group.get("settings", {})
    channel_settings = settings.get("channel_gate", {})

    default_config = get_default_channel_gate_config()
    default_config.update(channel_settings)
    return default_config


async def save_channel_gate_config(group_id: int, config: dict) -> bool:
    """Save channel gate configuration to group settings."""
    from db.ops.groups import get_group, upsert_group

    group = await get_group(group_id)
    settings = group.get("settings", {}) if group else {}
    settings["channel_gate"] = config

    await upsert_group(
        group_id,
        group.get("title", "Unknown") if group else "Unknown",
        group.get("bot_token_hash", "") if group else "",
        settings,
    )
    return True


def get_default_channel_gate_config() -> dict:
    """Get default channel gate configuration."""
    return {
        "force_channel_enabled": False,
        "force_channel_id": None,
        "force_channel_username": None,
        "force_channel_action": "restrict",
        "force_channel_message": (
            "📢 You must join our channel to participate here.\n\n"
            "After joining, tap ✅ I Joined to verify."
        ),
        "force_channel_kick_after": 0,
        "recheck_interval_secs": 30,
        "exempt_admins": True,
        "exempt_specific_users": [],
    }
