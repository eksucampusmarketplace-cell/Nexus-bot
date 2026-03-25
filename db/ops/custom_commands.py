"""
db/ops/custom_commands.py

Database operations for the Custom Commands Builder.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── Command CRUD ─────────────────────────────────────────────────────────────


async def create_command(
    pool,
    chat_id: int,
    name: str,
    description: str = "",
    created_by: int = 0,
    cooldown_secs: int = 0,
    priority: int = 0,
) -> dict:
    """Create a new custom command and return it."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO custom_commands
                (chat_id, name, description, created_by, cooldown_secs, priority)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (chat_id, name) DO UPDATE
                SET description = EXCLUDED.description,
                    cooldown_secs = EXCLUDED.cooldown_secs,
                    priority = EXCLUDED.priority,
                    updated_at = NOW()
            RETURNING *
            """,
            chat_id,
            name.lower().strip(),
            description,
            created_by,
            cooldown_secs,
            priority,
        )
    return dict(row) if row else {}


async def get_command(pool, command_id: int) -> dict:
    """Get a single command by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM custom_commands WHERE id = $1", command_id
        )
    return dict(row) if row else {}


async def get_command_by_name(pool, chat_id: int, name: str) -> dict:
    """Get a command by chat_id and name."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM custom_commands WHERE chat_id = $1 AND name = $2",
            chat_id,
            name.lower().strip(),
        )
    return dict(row) if row else {}


async def list_commands(pool, chat_id: int, enabled_only: bool = False) -> list:
    """List all custom commands for a group."""
    query = "SELECT * FROM custom_commands WHERE chat_id = $1"
    if enabled_only:
        query += " AND enabled = TRUE"
    query += " ORDER BY priority DESC, name ASC"
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, chat_id)
    return [dict(r) for r in rows]


async def update_command(pool, command_id: int, **kwargs) -> dict:
    """Update a custom command's fields."""
    allowed = {"name", "description", "enabled", "cooldown_secs", "priority"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return await get_command(pool, command_id)

    set_parts = [f"{k} = ${i + 2}" for i, k in enumerate(updates.keys())]
    set_parts.append("updated_at = NOW()")
    query = (
        f"UPDATE custom_commands SET {', '.join(set_parts)} WHERE id = $1 RETURNING *"
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, command_id, *updates.values())
    return dict(row) if row else {}


async def delete_command(pool, command_id: int) -> bool:
    """Delete a custom command and all related triggers/actions."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM custom_commands WHERE id = $1", command_id
        )
    return result == "DELETE 1"


async def increment_execution(pool, command_id: int) -> None:
    """Increment execution count and update last_executed."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE custom_commands
            SET execution_count = execution_count + 1,
                last_executed = NOW()
            WHERE id = $1
            """,
            command_id,
        )


# ── Triggers ─────────────────────────────────────────────────────────────────


async def add_trigger(
    pool,
    command_id: int,
    trigger_type: str,
    trigger_value: str = "",
    case_sensitive: bool = False,
) -> dict:
    """Add a trigger to a command."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO command_triggers (command_id, trigger_type, trigger_value, case_sensitive)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            command_id,
            trigger_type,
            trigger_value,
            case_sensitive,
        )
    return dict(row) if row else {}


async def get_triggers(pool, command_id: int) -> list:
    """Get all triggers for a command."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM command_triggers WHERE command_id = $1 ORDER BY id",
            command_id,
        )
    return [dict(r) for r in rows]


async def delete_trigger(pool, trigger_id: int) -> bool:
    """Delete a trigger."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM command_triggers WHERE id = $1", trigger_id
        )
    return result == "DELETE 1"


# ── Actions ──────────────────────────────────────────────────────────────────


async def add_action(
    pool,
    command_id: int,
    action_type: str,
    action_config: Optional[dict] = None,
    sort_order: int = 0,
    condition: Optional[dict] = None,
    delay_secs: int = 0,
) -> dict:
    """Add an action to a command."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO command_actions
                (command_id, action_type, action_config, sort_order, condition, delay_secs)
            VALUES ($1, $2, $3::jsonb, $4, $5::jsonb, $6)
            RETURNING *
            """,
            command_id,
            action_type,
            json.dumps(action_config or {}),
            sort_order,
            json.dumps(condition) if condition else None,
            delay_secs,
        )
    return dict(row) if row else {}


async def get_actions(pool, command_id: int) -> list:
    """Get all actions for a command, ordered by sort_order."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM command_actions WHERE command_id = $1 ORDER BY sort_order, id",
            command_id,
        )
    return [dict(r) for r in rows]


async def update_action(pool, action_id: int, **kwargs) -> dict:
    """Update an action's fields."""
    allowed = {"action_type", "action_config", "sort_order", "condition", "delay_secs"}
    updates = {}
    for k, v in kwargs.items():
        if k not in allowed:
            continue
        if k in ("action_config", "condition"):
            updates[k] = json.dumps(v) if v is not None else None
        else:
            updates[k] = v

    if not updates:
        return {}

    set_parts = [f"{k} = ${i + 2}" for i, k in enumerate(updates.keys())]
    query = (
        f"UPDATE command_actions SET {', '.join(set_parts)} WHERE id = $1 RETURNING *"
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, action_id, *updates.values())
    return dict(row) if row else {}


async def delete_action(pool, action_id: int) -> bool:
    """Delete an action."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM command_actions WHERE id = $1", action_id
        )
    return result == "DELETE 1"


# ── Variables ────────────────────────────────────────────────────────────────


async def set_variable(
    pool,
    chat_id: int,
    var_name: str,
    var_value: str,
    var_type: str = "string",
    command_id: Optional[int] = None,
) -> dict:
    """Set a variable (group-level if command_id is None)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO command_variables (chat_id, command_id, var_name, var_value, var_type)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (chat_id, command_id, var_name)
            DO UPDATE SET var_value = EXCLUDED.var_value,
                         var_type = EXCLUDED.var_type,
                         updated_at = NOW()
            RETURNING *
            """,
            chat_id,
            command_id,
            var_name,
            var_value,
            var_type,
        )
    return dict(row) if row else {}


async def get_variables(pool, chat_id: int, command_id: Optional[int] = None) -> list:
    """Get variables for a group or specific command."""
    if command_id is not None:
        query = (
            "SELECT * FROM command_variables "
            "WHERE chat_id = $1 AND (command_id = $2 OR command_id IS NULL) "
            "ORDER BY var_name"
        )
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, chat_id, command_id)
    else:
        query = (
            "SELECT * FROM command_variables WHERE chat_id = $1 AND command_id IS NULL "
            "ORDER BY var_name"
        )
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, chat_id)
    return [dict(r) for r in rows]


async def delete_variable(pool, variable_id: int) -> bool:
    """Delete a variable."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM command_variables WHERE id = $1", variable_id
        )
    return result == "DELETE 1"


# ── Rate Limiting ────────────────────────────────────────────────────────────


async def check_rate_limit(
    pool, chat_id: int, user_id: int, command_id: int, cooldown_secs: int
) -> bool:
    """Check if user is rate-limited. Returns True if allowed, False if rate-limited."""
    if cooldown_secs <= 0:
        return True

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT last_used FROM command_rate_limits
            WHERE chat_id = $1 AND user_id = $2 AND command_id = $3
            """,
            chat_id,
            user_id,
            command_id,
        )

        if row:
            elapsed = (datetime.now(timezone.utc) - row["last_used"]).total_seconds()
            if elapsed < cooldown_secs:
                return False

        await conn.execute(
            """
            INSERT INTO command_rate_limits (chat_id, user_id, command_id, last_used, use_count)
            VALUES ($1, $2, $3, NOW(), 1)
            ON CONFLICT (chat_id, user_id, command_id)
            DO UPDATE SET last_used = NOW(), use_count = command_rate_limits.use_count + 1
            """,
            chat_id,
            user_id,
            command_id,
        )
    return True


# ── Bulk Fetch (for runtime engine) ─────────────────────────────────────────


async def get_all_enabled_commands_with_triggers(pool, chat_id: int) -> list:
    """Fetch all enabled commands with their triggers for runtime matching."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.*, t.id AS trigger_id, t.trigger_type, t.trigger_value, t.case_sensitive
            FROM custom_commands c
            JOIN command_triggers t ON t.command_id = c.id
            WHERE c.chat_id = $1 AND c.enabled = TRUE
            ORDER BY c.priority DESC, c.name
            """,
            chat_id,
        )

    # Group by command
    commands: dict = {}
    for row in rows:
        row_dict = dict(row)
        cmd_id = row_dict["id"]
        if cmd_id not in commands:
            commands[cmd_id] = {
                "id": cmd_id,
                "chat_id": row_dict["chat_id"],
                "name": row_dict["name"],
                "description": row_dict["description"],
                "cooldown_secs": row_dict["cooldown_secs"],
                "priority": row_dict["priority"],
                "triggers": [],
            }
        commands[cmd_id]["triggers"].append(
            {
                "id": row_dict["trigger_id"],
                "type": row_dict["trigger_type"],
                "value": row_dict["trigger_value"],
                "case_sensitive": row_dict["case_sensitive"],
            }
        )

    return list(commands.values())
