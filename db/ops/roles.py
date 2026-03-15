"""
db/ops/roles.py

Custom Roles & Permissions operations.
Manages roles, user_roles, and permission checks.
"""

import json
from db.client import db
from typing import Optional, List, Dict

# Permission constants - aligned with miniapp key names
PERMISSIONS = {
    # Moderation (legacy and miniapp names)
    "warn_members",
    "mute_members",
    "kick_members",
    "ban_members",
    "unban_members",
    "purge_messages",
    "can_warn",      # miniapp name
    "can_mute",      # miniapp name
    "can_kick",      # miniapp name
    "can_ban",       # miniapp name
    # Content
    "pin_messages",
    "can_pin",       # miniapp name
    "post_channel",
    "schedule_posts",
    # Admin
    "manage_roles",
    "view_analytics",
    "export_data",
    "manage_webhooks",
    "manage_automod",
    "manage_games",
}


async def create_role(
    chat_id: int, name: str, color: str = "#64748b", permissions: Dict = None
) -> int:
    """Create a new role. Returns role ID."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO roles (chat_id, name, color, permissions)
               VALUES ($1, $2, $3, $4::jsonb)
               ON CONFLICT (chat_id, name) DO UPDATE
               SET color = EXCLUDED.color, permissions = EXCLUDED.permissions
               RETURNING id""",
            chat_id,
            name,
            color,
            json.dumps(permissions or {}),
        )
        return row["id"]


async def delete_role(chat_id: int, role_id: int) -> bool:
    """Delete a role."""
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM roles WHERE id = $1 AND chat_id = $2", role_id, chat_id
        )
        return "DELETE 1" in result


async def get_role(chat_id: int, role_id: int) -> Optional[dict]:
    """Get a single role by ID."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM roles WHERE id = $1 AND chat_id = $2", role_id, chat_id
        )
        if row:
            res = dict(row)
            res["permissions"] = json.loads(res["permissions"] or "{}")
            return res
        return None


async def get_roles(chat_id: int) -> List[dict]:
    """Get all roles for a group."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM roles WHERE chat_id = $1 ORDER BY name", chat_id)
        result = []
        for row in rows:
            res = dict(row)
            res["permissions"] = json.loads(res["permissions"] or "{}")
            result.append(res)
        return result


async def update_role_permissions(chat_id: int, role_id: int, permissions: Dict) -> bool:
    """Update role permissions."""
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE roles SET permissions = $1::jsonb
               WHERE id = $2 AND chat_id = $3""",
            json.dumps(permissions),
            role_id,
            chat_id,
        )
        return "UPDATE 1" in result


async def assign_role(
    user_id: int, chat_id: int, role_id: int, granted_by: int = None, expires_at=None
) -> bool:
    """Assign a role to a user."""
    async with db.pool.acquire() as conn:
        try:
            await conn.execute(
                """INSERT INTO user_roles (user_id, chat_id, role_id, granted_by, expires_at)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (user_id, chat_id, role_id) DO UPDATE
                   SET granted_by = EXCLUDED.granted_by,
                       expires_at = EXCLUDED.expires_at,
                       granted_at = CURRENT_TIMESTAMP""",
                user_id,
                chat_id,
                role_id,
                granted_by,
                expires_at,
            )
            return True
        except Exception:
            return False


async def remove_role(user_id: int, chat_id: int, role_id: int) -> bool:
    """Remove a role from a user."""
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM user_roles WHERE user_id = $1 AND chat_id = $2 AND role_id = $3",
            user_id,
            chat_id,
            role_id,
        )
        return "DELETE 1" in result


async def get_user_roles(user_id: int, chat_id: int) -> List[dict]:
    """Get all roles assigned to a user."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT r.* FROM user_roles ur
               JOIN roles r ON r.id = ur.role_id
               WHERE ur.user_id = $1 AND ur.chat_id = $2
                 AND (ur.expires_at IS NULL OR ur.expires_at > NOW())""",
            user_id,
            chat_id,
        )
        result = []
        for row in rows:
            res = dict(row)
            res["permissions"] = json.loads(res["permissions"] or "{}")
            result.append(res)
        return result


async def has_permission(user_id: int, chat_id: int, perm: str) -> bool:
    """
    Check if user has a specific permission through any of their roles.

    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        perm: Permission name from PERMISSIONS

    Returns:
        True if user has permission
    """
    if perm not in PERMISSIONS:
        return False

    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT r.permissions FROM user_roles ur
               JOIN roles r ON r.id = ur.role_id
               WHERE ur.user_id = $1 AND ur.chat_id = $2
                 AND (ur.expires_at IS NULL OR ur.expires_at > NOW())""",
            user_id,
            chat_id,
        )

        for row in rows:
            perms = json.loads(row["permissions"] or "{}")
            if perms.get(perm):
                return True
        return False


async def get_users_with_role(chat_id: int, role_id: int) -> List[dict]:
    """Get all users with a specific role."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ur.*, u.first_name, u.username FROM user_roles ur
               LEFT JOIN users u ON u.user_id = ur.user_id AND u.chat_id = ur.chat_id
               WHERE ur.chat_id = $1 AND ur.role_id = $2
                 AND (ur.expires_at IS NULL OR ur.expires_at > NOW())""",
            chat_id,
            role_id,
        )
        return [dict(row) for row in rows]


async def get_all_user_permissions(user_id: int, chat_id: int) -> Dict[str, bool]:
    """Get all permissions a user has (merged from all roles)."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT r.permissions FROM user_roles ur
               JOIN roles r ON r.id = ur.role_id
               WHERE ur.user_id = $1 AND ur.chat_id = $2
                 AND (ur.expires_at IS NULL OR ur.expires_at > NOW())""",
            user_id,
            chat_id,
        )

        merged = {}
        for row in rows:
            perms = json.loads(row["permissions"] or "{}")
            for key, value in perms.items():
                if value:  # If any role grants it, user has it
                    merged[key] = True
        return merged
