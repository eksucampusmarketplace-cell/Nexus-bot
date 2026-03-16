"""
db/ops/federation.py

Federation/TrustNet database operations.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

logger = logging.getLogger(__name__)


async def create_federation(pool, owner_id: int, name: str, invite_code: str) -> Optional[str]:
    """Create a new federation. Returns federation ID."""
    try:
        async with pool.acquire() as conn:
            fed_id = await conn.fetchval(
                """INSERT INTO federations (owner_id, name, invite_code)
                   VALUES ($1, $2, $3) RETURNING id""",
                owner_id, name, invite_code
            )
            return str(fed_id)
    except Exception as e:
        logger.error(f"Failed to create federation: {e}")
        return None


async def get_federation_by_code(pool, invite_code: str) -> Optional[Dict]:
    """Get federation by invite code."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM federations WHERE invite_code = $1",
                invite_code.upper()
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get federation: {e}")
        return None


async def join_federation(pool, federation_id: str, chat_id: int, joined_by: int) -> bool:
    """Add a group to a federation."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO federation_members (federation_id, chat_id, joined_by)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (federation_id, chat_id) DO NOTHING""",
                federation_id, chat_id, joined_by
            )
            return True
    except Exception as e:
        logger.error(f"Failed to join federation: {e}")
        return False


async def leave_federation(pool, federation_id: str, chat_id: int) -> bool:
    """Remove a group from a federation."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM federation_members WHERE federation_id = $1 AND chat_id = $2",
                federation_id, chat_id
            )
            return result != "DELETE 0"
    except Exception as e:
        logger.error(f"Failed to leave federation: {e}")
        return False


async def get_group_federations(pool, chat_id: int) -> List[Dict]:
    """Get all federations a group is a member of."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT f.id, f.name, f.owner_id, f.invite_code, fm.joined_at,
                          (SELECT COUNT(*) FROM federation_members WHERE federation_id = f.id) as group_count
                   FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1""",
                chat_id
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to get group federations: {e}")
        return []


async def get_user_federations(pool, user_id: int) -> List[Dict]:
    """Get all federations owned by a user."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT f.id, f.name, f.invite_code, f.created_at,
                          (SELECT COUNT(*) FROM federation_members WHERE federation_id = f.id) as group_count,
                          (SELECT COUNT(*) FROM federation_bans WHERE federation_id = f.id) as ban_count
                   FROM federations f
                   WHERE f.owner_id = $1
                   ORDER BY f.created_at DESC""",
                user_id
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to get user federations: {e}")
        return []


async def add_fed_ban(pool, federation_id: str, user_id: int, reason: str, banned_by: int, silent: bool = False) -> bool:
    """Add a user to federation ban list."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO federation_bans (federation_id, user_id, reason, banned_by, silent)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (federation_id, user_id) DO UPDATE 
                   SET reason = EXCLUDED.reason, banned_by = EXCLUDED.banned_by, 
                       banned_at = NOW(), silent = EXCLUDED.silent""",
                federation_id, user_id, reason, banned_by, silent
            )
            
            # Log action
            await conn.execute(
                """INSERT INTO federation_ban_actions (federation_id, user_id, action, performed_by, reason)
                   VALUES ($1, $2, $3, $4, $5)""",
                federation_id, user_id, "ban", banned_by, reason
            )
            return True
    except Exception as e:
        logger.error(f"Failed to add fed ban: {e}")
        return False


async def remove_fed_ban(pool, federation_id: str, user_id: int, removed_by: int) -> bool:
    """Remove a user from federation ban list."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM federation_bans WHERE federation_id = $1 AND user_id = $2",
                federation_id, user_id
            )
            
            if result != "DELETE 0":
                await conn.execute(
                    """INSERT INTO federation_ban_actions (federation_id, user_id, action, performed_by)
                       VALUES ($1, $2, $3, $4)""",
                    federation_id, user_id, "unban", removed_by
                )
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to remove fed ban: {e}")
        return False


async def is_fed_banned(pool, federation_id: str, user_id: int) -> Optional[Dict]:
    """Check if a user is banned in a federation."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT fb.*, f.name as federation_name
                   FROM federation_bans fb
                   JOIN federations f ON f.id = fb.federation_id
                   WHERE fb.federation_id = $1 AND fb.user_id = $2""",
                federation_id, user_id
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to check fed ban: {e}")
        return None


async def get_fed_bans(pool, federation_id: str, limit: int = 100) -> List[Dict]:
    """Get list of banned users in a federation."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT fb.*, f.name as federation_name
                   FROM federation_bans fb
                   JOIN federations f ON f.id = fb.federation_id
                   WHERE fb.federation_id = $1
                   ORDER BY fb.banned_at DESC
                   LIMIT $2""",
                federation_id, limit
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to get fed bans: {e}")
        return []


async def get_federation_groups(pool, federation_id: str) -> List[int]:
    """Get all chat IDs in a federation."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT chat_id FROM federation_members WHERE federation_id = $1",
                federation_id
            )
            return [r["chat_id"] for r in rows]
    except Exception as e:
        logger.error(f"Failed to get federation groups: {e}")
        return []


async def promote_fed_admin(pool, federation_id: str, user_id: int, promoted_by: int) -> bool:
    """Promote a user to federation admin."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO federation_admins (federation_id, user_id, promoted_by)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (federation_id, user_id) DO NOTHING""",
                federation_id, user_id, promoted_by
            )
            return True
    except Exception as e:
        logger.error(f"Failed to promote fed admin: {e}")
        return False


async def demote_fed_admin(pool, federation_id: str, user_id: int) -> bool:
    """Demote a federation admin."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM federation_admins WHERE federation_id = $1 AND user_id = $2",
                federation_id, user_id
            )
            return result != "DELETE 0"
    except Exception as e:
        logger.error(f"Failed to demote fed admin: {e}")
        return False


async def get_fed_admins(pool, federation_id: str) -> List[Dict]:
    """Get list of federation admins."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT fa.*, f.owner_id
                   FROM federation_admins fa
                   JOIN federations f ON f.id = fa.federation_id
                   WHERE fa.federation_id = $1""",
                federation_id
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to get fed admins: {e}")
        return []


async def is_fed_admin(pool, federation_id: str, user_id: int) -> bool:
    """Check if a user is a federation admin or owner."""
    try:
        async with pool.acquire() as conn:
            # Check if owner
            owner = await conn.fetchval(
                "SELECT 1 FROM federations WHERE id = $1 AND owner_id = $2",
                federation_id, user_id
            )
            if owner:
                return True
            
            # Check if admin
            admin = await conn.fetchval(
                "SELECT 1 FROM federation_admins WHERE federation_id = $1 AND user_id = $2",
                federation_id, user_id
            )
            return bool(admin)
    except Exception as e:
        logger.error(f"Failed to check fed admin: {e}")
        return False


async def transfer_federation(pool, federation_id: str, new_owner_id: int) -> bool:
    """Transfer federation ownership."""
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE federations SET owner_id = $1 WHERE id = $2",
                new_owner_id, federation_id
            )
            return result != "UPDATE 0"
    except Exception as e:
        logger.error(f"Failed to transfer federation: {e}")
        return False


async def set_fed_log_channel(pool, federation_id: str, channel_id: int) -> bool:
    """Set log channel for a federation."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE federations SET log_channel_id = $1 WHERE id = $2",
                channel_id, federation_id
            )
            return True
    except Exception as e:
        logger.error(f"Failed to set log channel: {e}")
        return False


async def create_appeal(pool, federation_id: str, user_id: int, reason: str) -> bool:
    """Create a federation ban appeal."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO federation_appeals (federation_id, user_id, reason)
                   VALUES ($1, $2, $3)
                   ON CONFLICT DO NOTHING""",
                federation_id, user_id, reason
            )
            return True
    except Exception as e:
        logger.error(f"Failed to create appeal: {e}")
        return False


async def get_user_reputation(pool, user_id: int, federation_id: str = None) -> List[Dict]:
    """Get user reputation scores."""
    try:
        async with pool.acquire() as conn:
            if federation_id:
                row = await conn.fetchrow(
                    "SELECT * FROM federation_reputation WHERE user_id = $1 AND federation_id = $2",
                    user_id, federation_id
                )
                return [dict(row)] if row else []
            else:
                rows = await conn.fetch(
                    """SELECT fr.*, f.name as federation_name
                       FROM federation_reputation fr
                       JOIN federations f ON f.id = fr.federation_id
                       WHERE fr.user_id = $1""",
                    user_id
                )
                return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to get user reputation: {e}")
        return []


async def update_reputation(pool, user_id: int, federation_id: str, points_delta: int, reason: str = None) -> bool:
    """Update user reputation score."""
    try:
        async with pool.acquire() as conn:
            # Get current score
            current = await conn.fetchval(
                "SELECT score FROM federation_reputation WHERE user_id = $1 AND federation_id = $2",
                user_id, federation_id
            )
            
            if current is None:
                current = 50  # Default neutral score
            
            new_score = max(0, min(100, current + points_delta))
            
            await conn.execute(
                """INSERT INTO federation_reputation (user_id, federation_id, score)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (user_id, federation_id) DO UPDATE 
                   SET score = EXCLUDED.score, updated_at = NOW()""",
                user_id, federation_id, new_score
            )
            
            # Log event
            await conn.execute(
                """INSERT INTO federation_trust_events 
                   (federation_id, user_id, event_type, points_delta, reason)
                   VALUES ($1, $2, $3, $4, $5)""",
                federation_id, user_id, "reputation_change", points_delta, reason
            )
            return True
    except Exception as e:
        logger.error(f"Failed to update reputation: {e}")
        return False


async def check_federation_ban_on_join(pool, chat_id: int, user_id: int) -> Optional[Dict]:
    """Check if user should be banned when joining a group (fed ban check)."""
    try:
        async with pool.acquire() as conn:
            # Get federations this group is in
            fed_ids = await conn.fetch(
                "SELECT federation_id FROM federation_members WHERE chat_id = $1",
                chat_id
            )
            
            for fed in fed_ids:
                ban = await conn.fetchrow(
                    """SELECT fb.*, f.name as federation_name
                       FROM federation_bans fb
                       JOIN federations f ON f.id = fb.federation_id
                       WHERE fb.federation_id = $1 AND fb.user_id = $2""",
                    fed["federation_id"], user_id
                )
                if ban:
                    return dict(ban)
            
            return None
    except Exception as e:
        logger.error(f"Failed to check fed ban on join: {e}")
        return None
