"""
api/routes/custom_commands.py

REST API for the Custom Commands Builder.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from db.client import db
from db.ops.custom_commands import (add_action, add_trigger, create_command,
                                    delete_action, delete_command,
                                    delete_trigger, get_actions, get_command,
                                    get_triggers, get_variables, list_commands,
                                    set_variable, update_action,
                                    update_command)

router = APIRouter(
    prefix="/api/groups/{chat_id}/custom-commands",
    tags=["custom_commands"],
)
logger = logging.getLogger(__name__)


# ── Command CRUD ─────────────────────────────────────────────────────────────


@router.get("")
async def list_custom_commands(chat_id: int, user: dict = Depends(get_current_user)):
    """List all custom commands for a group."""
    try:
        commands = await list_commands(db.pool, chat_id)
        # Enrich with triggers and actions count
        for cmd in commands:
            triggers = await get_triggers(db.pool, cmd["id"])
            actions = await get_actions(db.pool, cmd["id"])
            cmd["triggers"] = triggers
            cmd["actions"] = actions
            cmd["trigger_count"] = len(triggers)
            cmd["action_count"] = len(actions)
        return {"ok": True, "commands": commands}
    except Exception as e:
        logger.error(f"[CustomCmds API] list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_custom_command(
    chat_id: int, body: dict, user: dict = Depends(get_current_user)
):
    """Create a new custom command."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name is required")

    try:
        cmd = await create_command(
            db.pool,
            chat_id=chat_id,
            name=name,
            description=body.get("description", ""),
            created_by=user.get("user_id", 0),
            cooldown_secs=body.get("cooldown_secs", 0),
            priority=body.get("priority", 0),
        )

        # Add triggers if provided
        triggers = body.get("triggers", [])
        for t in triggers:
            await add_trigger(
                db.pool,
                command_id=cmd["id"],
                trigger_type=t.get("trigger_type", "command"),
                trigger_value=t.get("trigger_value", name),
                case_sensitive=t.get("case_sensitive", False),
            )

        # Add actions if provided
        actions = body.get("actions", [])
        for i, a in enumerate(actions):
            await add_action(
                db.pool,
                command_id=cmd["id"],
                action_type=a.get("action_type", "reply"),
                action_config=a.get("action_config", {}),
                sort_order=a.get("sort_order", i),
                condition=a.get("condition"),
                delay_secs=a.get("delay_secs", 0),
            )

        return {"ok": True, "command": cmd}
    except Exception as e:
        logger.error(f"[CustomCmds API] create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{command_id}")
async def get_custom_command(
    chat_id: int, command_id: int, user: dict = Depends(get_current_user)
):
    """Get a specific custom command with its triggers and actions."""
    try:
        cmd = await get_command(db.pool, command_id)
        if not cmd or cmd.get("chat_id") != chat_id:
            raise HTTPException(404, "Command not found")

        cmd["triggers"] = await get_triggers(db.pool, command_id)
        cmd["actions"] = await get_actions(db.pool, command_id)
        cmd["variables"] = await get_variables(db.pool, chat_id, command_id)

        return {"ok": True, "command": cmd}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomCmds API] get error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{command_id}")
async def update_custom_command(
    chat_id: int, command_id: int, body: dict, user: dict = Depends(get_current_user)
):
    """Update a custom command."""
    try:
        cmd = await get_command(db.pool, command_id)
        if not cmd or cmd.get("chat_id") != chat_id:
            raise HTTPException(404, "Command not found")

        updated = await update_command(db.pool, command_id, **body)
        return {"ok": True, "command": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomCmds API] update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{command_id}")
async def delete_custom_command(
    chat_id: int, command_id: int, user: dict = Depends(get_current_user)
):
    """Delete a custom command."""
    try:
        cmd = await get_command(db.pool, command_id)
        if not cmd or cmd.get("chat_id") != chat_id:
            raise HTTPException(404, "Command not found")

        deleted = await delete_command(db.pool, command_id)
        return {"ok": True, "deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomCmds API] delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Triggers ─────────────────────────────────────────────────────────────────


@router.post("/{command_id}/triggers")
async def add_command_trigger(
    chat_id: int, command_id: int, body: dict, user: dict = Depends(get_current_user)
):
    """Add a trigger to a command."""
    try:
        trigger = await add_trigger(
            db.pool,
            command_id=command_id,
            trigger_type=body.get("trigger_type", "command"),
            trigger_value=body.get("trigger_value", ""),
            case_sensitive=body.get("case_sensitive", False),
        )
        return {"ok": True, "trigger": trigger}
    except Exception as e:
        logger.error(f"[CustomCmds API] add_trigger error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{command_id}/triggers/{trigger_id}")
async def remove_command_trigger(
    chat_id: int,
    command_id: int,
    trigger_id: int,
    user: dict = Depends(get_current_user),
):
    """Remove a trigger from a command."""
    try:
        deleted = await delete_trigger(db.pool, trigger_id)
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        logger.error(f"[CustomCmds API] delete_trigger error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Actions ──────────────────────────────────────────────────────────────────


@router.post("/{command_id}/actions")
async def add_command_action(
    chat_id: int, command_id: int, body: dict, user: dict = Depends(get_current_user)
):
    """Add an action to a command."""
    try:
        action = await add_action(
            db.pool,
            command_id=command_id,
            action_type=body.get("action_type", "reply"),
            action_config=body.get("action_config", {}),
            sort_order=body.get("sort_order", 0),
            condition=body.get("condition"),
            delay_secs=body.get("delay_secs", 0),
        )
        return {"ok": True, "action": action}
    except Exception as e:
        logger.error(f"[CustomCmds API] add_action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{command_id}/actions/{action_id}")
async def update_command_action(
    chat_id: int,
    command_id: int,
    action_id: int,
    body: dict,
    user: dict = Depends(get_current_user),
):
    """Update an action."""
    try:
        updated = await update_action(db.pool, action_id, **body)
        return {"ok": True, "action": updated}
    except Exception as e:
        logger.error(f"[CustomCmds API] update_action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{command_id}/actions/{action_id}")
async def remove_command_action(
    chat_id: int,
    command_id: int,
    action_id: int,
    user: dict = Depends(get_current_user),
):
    """Remove an action from a command."""
    try:
        deleted = await delete_action(db.pool, action_id)
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        logger.error(f"[CustomCmds API] delete_action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Variables ────────────────────────────────────────────────────────────────


@router.get("/{command_id}/variables")
async def list_command_variables(
    chat_id: int, command_id: int, user: dict = Depends(get_current_user)
):
    """List variables for a command."""
    try:
        variables = await get_variables(db.pool, chat_id, command_id)
        return {"ok": True, "variables": variables}
    except Exception as e:
        logger.error(f"[CustomCmds API] list_variables error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{command_id}/variables")
async def set_command_variable(
    chat_id: int, command_id: int, body: dict, user: dict = Depends(get_current_user)
):
    """Set a variable for a command."""
    var_name = body.get("var_name", "").strip()
    if not var_name:
        raise HTTPException(400, "var_name is required")

    try:
        variable = await set_variable(
            db.pool,
            chat_id=chat_id,
            var_name=var_name,
            var_value=body.get("var_value", ""),
            var_type=body.get("var_type", "string"),
            command_id=command_id,
        )
        return {"ok": True, "variable": variable}
    except Exception as e:
        logger.error(f"[CustomCmds API] set_variable error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Test / Preview ───────────────────────────────────────────────────────────


@router.post("/{command_id}/test")
async def test_custom_command(
    chat_id: int, command_id: int, body: dict, user: dict = Depends(get_current_user)
):
    """Preview what a custom command would do (dry run)."""
    try:
        cmd = await get_command(db.pool, command_id)
        if not cmd or cmd.get("chat_id") != chat_id:
            raise HTTPException(404, "Command not found")

        triggers = await get_triggers(db.pool, command_id)
        actions = await get_actions(db.pool, command_id)

        # Build preview
        preview = {
            "command": cmd["name"],
            "enabled": cmd["enabled"],
            "triggers": [
                {"type": t["trigger_type"], "value": t["trigger_value"]}
                for t in triggers
            ],
            "actions": [
                {
                    "type": a["action_type"],
                    "config": a["action_config"],
                    "condition": a["condition"],
                    "order": a["sort_order"],
                }
                for a in actions
            ],
            "variables_available": [
                "user.name",
                "user.username",
                "user.id",
                "user.mention",
                "group.name",
                "group.id",
                "group.member_count",
                "bot.name",
                "bot.username",
                "time",
                "date",
                "datetime",
                "random",
                "newline",
            ],
        }

        return {"ok": True, "preview": preview}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CustomCmds API] test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
