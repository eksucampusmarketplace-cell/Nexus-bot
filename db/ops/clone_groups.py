"""
db/ops/clone_groups.py

All DB operations for clone bot group membership and access control.
"""

import logging
from asyncpg import Connection

log = logging.getLogger("db.clone_groups")


async def get_active_group_count(db: Connection, bot_id: int) -> int:
    """Returns how many active groups this clone is currently in."""
    row = await db.fetchrow(
        "SELECT COUNT(*) as c FROM clone_bot_groups "
        "WHERE bot_id=$1 AND is_active=TRUE",
        bot_id
    )
    return row["c"] if row else 0


async def get_clone_config(db: Connection, bot_id: int) -> dict | None:
    """
    Returns clone config fields needed for group access decisions.
    Returns: {group_limit, group_access_policy, bot_add_notifications, owner_id}
    """
    row = await db.fetchrow(
        "SELECT group_limit, group_access_policy, bot_add_notifications, owner_user_id as owner_id "
        "FROM bots WHERE bot_id=$1",
        bot_id
    )
    return dict(row) if row else None


async def register_group(
    db: Connection,
    bot_id: int,
    chat_id: int,
    chat_title: str,
    added_by: int,
    added_by_name: str,
    is_owner_group: bool,
    access_status: str = "active"
) -> None:
    """
    Upsert a group record for this clone bot.
    If the group was previously left (is_active=False), reactivate it.
    Logs: [CLONE_GROUPS] Registered | bot={bot_id} chat={chat_id} status={access_status}
    """
    await db.execute(
        """
        INSERT INTO clone_bot_groups
            (bot_id, chat_id, chat_title, added_by, added_by_name,
             is_owner_group, is_active, access_status)
        VALUES ($1,$2,$3,$4,$5,$6,TRUE,$7)
        ON CONFLICT (bot_id, chat_id) DO UPDATE SET
            chat_title=EXCLUDED.chat_title,
            added_by=EXCLUDED.added_by,
            added_by_name=EXCLUDED.added_by_name,
            is_owner_group=EXCLUDED.is_owner_group,
            is_active=TRUE,
            access_status=EXCLUDED.access_status,
            left_at=NULL
        """,
        bot_id, chat_id, chat_title, added_by,
        added_by_name, is_owner_group, access_status
    )
    log.info(f"[CLONE_GROUPS] Registered | bot={bot_id} chat={chat_id} status={access_status}")


async def mark_group_left(db: Connection, bot_id: int, chat_id: int) -> None:
    """Mark a group as left (bot was removed or left itself)."""
    from datetime import datetime, timezone
    await db.execute(
        """
        UPDATE clone_bot_groups
        SET is_active=FALSE, left_at=$3, access_status='left'
        WHERE bot_id=$1 AND chat_id=$2
        """,
        bot_id, chat_id, datetime.now(timezone.utc)
    )
    log.info(f"[CLONE_GROUPS] Left | bot={bot_id} chat={chat_id}")


async def get_group_entry(db: Connection, bot_id: int, chat_id: int) -> dict | None:
    """Get a single group record for this clone."""
    row = await db.fetchrow(
        "SELECT * FROM clone_bot_groups WHERE bot_id=$1 AND chat_id=$2",
        bot_id, chat_id
    )
    return dict(row) if row else None


async def list_active_groups(db: Connection, bot_id: int) -> list[dict]:
    """List all active groups for a clone bot. Used in /myclones and Mini App."""
    rows = await db.fetch(
        "SELECT * FROM clone_bot_groups WHERE bot_id=$1 AND is_active=TRUE ORDER BY added_at DESC",
        bot_id
    )
    return [dict(r) for r in rows]


async def update_access_status(
    db: Connection, bot_id: int, chat_id: int, status: str
) -> None:
    """Update access_status for a group entry. Used for approval flow."""
    await db.execute(
        "UPDATE clone_bot_groups SET access_status=$3 WHERE bot_id=$1 AND chat_id=$2",
        bot_id, chat_id, status
    )
