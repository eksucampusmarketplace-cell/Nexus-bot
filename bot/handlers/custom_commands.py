"""
bot/handlers/custom_commands.py

Runtime engine for the Custom Commands Builder.
Intercepts messages, matches triggers, evaluates conditions, and executes action chains.
"""

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timezone

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from db.client import db
from db.ops.custom_commands import (check_rate_limit, get_actions,
                                    get_all_enabled_commands_with_triggers,
                                    get_variables, increment_execution,
                                    set_variable)

logger = logging.getLogger(__name__)

# ── Built-in Variables ────────────────────────────────────────────────────────

BUILTIN_VARS = {
    "user.name",
    "user.first_name",
    "user.last_name",
    "user.username",
    "user.id",
    "user.mention",
    "target.name",
    "target.first_name",
    "target.last_name",
    "target.username",
    "target.id",
    "target.mention",
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
    "args",
    "arg1",
    "arg2",
    "arg3",
}

# Max actions per command execution (abuse prevention)
MAX_ACTIONS_PER_EXEC = 10
# Max reply text length
MAX_TEXT_LENGTH = 4096
# Max variable substitutions per text
MAX_SUBSTITUTIONS = 50


async def _resolve_variable(
    var_name: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    command_id: int,
) -> str:
    """Resolve a variable name to its value."""
    user = update.effective_user
    chat = update.effective_chat
    target = (
        update.message.reply_to_message.from_user
        if update.message and update.message.reply_to_message
        else None
    )

    # Built-in variables
    if var_name == "user.name":
        return user.full_name if user else "Unknown"
    if var_name == "user.first_name":
        return user.first_name if user else "Unknown"
    if var_name == "user.last_name":
        return (user.last_name or "") if user else ""
    if var_name == "user.username":
        return (
            f"@{user.username}"
            if user and user.username
            else user.full_name if user else ""
        )
    if var_name == "user.id":
        return str(user.id) if user else "0"
    if var_name == "user.mention":
        if user:
            return f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
        return "Unknown"

    if var_name == "target.name":
        return target.full_name if target else ""
    if var_name == "target.first_name":
        return target.first_name if target else ""
    if var_name == "target.last_name":
        return (target.last_name or "") if target else ""
    if var_name == "target.username":
        return f"@{target.username}" if target and target.username else ""
    if var_name == "target.id":
        return str(target.id) if target else ""
    if var_name == "target.mention":
        if target:
            return f'<a href="tg://user?id={target.id}">{target.full_name}</a>'
        return ""

    if var_name == "group.name":
        return chat.title if chat else "Unknown"
    if var_name == "group.id":
        return str(chat.id) if chat else "0"
    if var_name == "group.member_count":
        try:
            count = await context.bot.get_chat_member_count(chat_id)
            return str(count)
        except Exception:
            return "?"
    if var_name == "bot.name":
        return context.bot.first_name or "Bot"
    if var_name == "bot.username":
        return f"@{context.bot.username}" if context.bot.username else "Bot"
    if var_name == "time":
        return datetime.now(timezone.utc).strftime("%H:%M UTC")
    if var_name == "date":
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if var_name == "datetime":
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if var_name == "random":
        return str(random.randint(1, 100))
    if var_name == "newline":
        return "\n"

    # Command arguments
    if var_name.startswith("arg") or var_name == "args":
        text = update.message.text or update.message.caption or ""
        parts = text.split()
        if len(parts) > 1:
            if var_name == "args":
                return " ".join(parts[1:])
            try:
                idx = int(var_name[3:])
                if 0 < idx < len(parts):
                    return parts[idx]
            except (ValueError, IndexError):
                pass
        return ""

    # Custom variables from DB
    try:
        variables = await get_variables(db.pool, chat_id, command_id)
        for v in variables:
            if v["var_name"] == var_name:
                return v["var_value"] or ""
    except Exception:
        pass

    return f"{{{var_name}}}"


async def _substitute_variables(
    text: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    command_id: int,
) -> str:
    """Replace {variable} placeholders in text."""
    if not text:
        return text

    pattern = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")
    matches = pattern.findall(text)

    if not matches:
        return text

    count = 0
    for var_name in matches:
        if count >= MAX_SUBSTITUTIONS:
            break
        value = await _resolve_variable(var_name, update, context, chat_id, command_id)
        text = text.replace(f"{{{var_name}}}", value, 1)
        count += 1

    return text[:MAX_TEXT_LENGTH]


async def _evaluate_condition(
    condition: dict,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    command_id: int,
) -> bool:
    """Evaluate a condition dict. Returns True if condition passes."""
    if not condition:
        return True

    cond_type = condition.get("type", "")

    if cond_type == "role_check":
        # Check if user has a specific role
        role = condition.get("role", "member")
        user = update.effective_user
        if not user:
            return False
        try:
            member = await context.bot.get_chat_member(chat_id, user.id)
            if role == "admin":
                return member.status in ("creator", "administrator")
            if role == "creator":
                return member.status == "creator"
            return True  # 'member' always passes
        except Exception:
            return False

    if cond_type == "variable_check":
        var_name = condition.get("var", "")
        op = condition.get("op", "==")
        expected = condition.get("value", "")
        actual = await _resolve_variable(var_name, update, context, chat_id, command_id)

        try:
            if op == "==":
                return str(actual) == str(expected)
            if op == "!=":
                return str(actual) != str(expected)
            if op == ">":
                return float(actual) > float(expected)
            if op == ">=":
                return float(actual) >= float(expected)
            if op == "<":
                return float(actual) < float(expected)
            if op == "<=":
                return float(actual) <= float(expected)
            if op == "contains":
                return str(expected) in str(actual)
        except (ValueError, TypeError):
            return False

    if cond_type == "reply_check":
        return update.message.reply_to_message is not None

    return True


async def _execute_action(
    action: dict,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    command_id: int,
) -> None:
    """Execute a single action."""
    action_type = action.get("action_type", "")
    config = action.get("action_config", {}) or {}
    delay = action.get("delay_secs", 0)

    if delay and delay > 0:
        await asyncio.sleep(min(delay, 30))  # Cap delay at 30 seconds

    if action_type == "reply":
        text = config.get("text", "")
        if not text:
            return
        text = await _substitute_variables(text, update, context, chat_id, command_id)
        parse_mode = config.get("parse_mode", "HTML")
        try:
            await update.message.reply_text(text, parse_mode=parse_mode)
        except Exception as e:
            logger.warning(f"[CUSTOM_CMD] reply action failed: {e}")

    elif action_type == "delete":
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"[CUSTOM_CMD] delete action failed: {e}")

    elif action_type == "react":
        emoji = config.get("emoji", "")
        if emoji:
            try:
                from telegram import ReactionTypeEmoji

                await update.message.set_reaction([ReactionTypeEmoji(emoji=emoji)])
            except Exception as e:
                logger.debug(f"[CUSTOM_CMD] react action failed: {e}")

    elif action_type == "warn":
        target = (
            update.message.reply_to_message.from_user
            if update.message.reply_to_message
            else None
        )
        if target:
            reason = config.get("reason", "Custom command auto-warn")
            reason = await _substitute_variables(
                reason, update, context, chat_id, command_id
            )
            try:
                from db.ops.users import add_warn

                await add_warn(target.id, chat_id, reason, update.effective_user.id)
                await update.message.reply_text(
                    f"Warned {target.full_name}: {reason}", parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] warn action failed: {e}")

    elif action_type == "mute":
        target = (
            update.message.reply_to_message.from_user
            if update.message.reply_to_message
            else None
        )
        if target:
            try:
                duration = int(config.get("duration", 0))
                until_date = None
                if duration > 0:
                    until_date = datetime.now(timezone.utc).timestamp() + duration
                await context.bot.restrict_chat_member(
                    chat_id,
                    target.id,
                    permissions={"can_send_messages": False},
                    until_date=until_date,
                )
                await update.message.reply_text(
                    f"Muted {target.full_name}"
                    + (f" for {duration}s" if duration > 0 else "")
                )
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] mute action failed: {e}")

    elif action_type == "unmute":
        target = (
            update.message.reply_to_message.from_user
            if update.message.reply_to_message
            else None
        )
        if target:
            try:
                await context.bot.restrict_chat_member(
                    chat_id,
                    target.id,
                    permissions={
                        "can_send_messages": True,
                        "can_send_media_messages": True,
                        "can_send_other_messages": True,
                        "can_add_web_page_previews": True,
                    },
                )
                await update.message.reply_text(f"Unmuted {target.full_name}")
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] unmute action failed: {e}")

    elif action_type == "kick":
        target = (
            update.message.reply_to_message.from_user
            if update.message.reply_to_message
            else None
        )
        if target:
            try:
                await context.bot.unban_chat_member(chat_id, target.id)
                await update.message.reply_text(f"Kicked {target.full_name}")
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] kick action failed: {e}")

    elif action_type == "ban":
        target = (
            update.message.reply_to_message.from_user
            if update.message.reply_to_message
            else None
        )
        if target:
            try:
                duration = int(config.get("duration", 0))
                until_date = None
                if duration > 0:
                    until_date = datetime.now(timezone.utc).timestamp() + duration
                await context.bot.ban_chat_member(
                    chat_id, target.id, until_date=until_date
                )
                await update.message.reply_text(
                    f"Banned {target.full_name}"
                    + (f" for {duration}s" if duration > 0 else "")
                )
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] ban action failed: {e}")

    elif action_type == "unban":
        target_id = config.get("user_id")
        if not target_id and update.message.reply_to_message:
            target_id = update.message.reply_to_message.from_user.id

        if target_id:
            try:
                await context.bot.unban_chat_member(chat_id, int(target_id))
                await update.message.reply_text(f"Unbanned user {target_id}")
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] unban action failed: {e}")

    elif action_type == "promote":
        target = (
            update.message.reply_to_message.from_user
            if update.message.reply_to_message
            else None
        )
        if target:
            try:
                await context.bot.promote_chat_member(
                    chat_id,
                    target.id,
                    can_manage_chat=True,
                    can_delete_messages=True,
                    can_restrict_members=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                )
                await update.message.reply_text(f"Promoted {target.full_name} to admin")
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] promote action failed: {e}")

    elif action_type == "demote":
        target = (
            update.message.reply_to_message.from_user
            if update.message.reply_to_message
            else None
        )
        if target:
            try:
                await context.bot.promote_chat_member(
                    chat_id,
                    target.id,
                    can_manage_chat=False,
                    can_delete_messages=False,
                    can_restrict_members=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                )
                await update.message.reply_text(f"Demoted {target.full_name}")
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] demote action failed: {e}")

    elif action_type == "send_photo":
        photo_url = config.get("photo_url", "")
        caption = config.get("caption", "")
        if photo_url:
            photo_url = await _substitute_variables(
                photo_url, update, context, chat_id, command_id
            )
            caption = await _substitute_variables(
                caption, update, context, chat_id, command_id
            )
            try:
                await context.bot.send_photo(chat_id, photo_url, caption=caption, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] send_photo action failed: {e}")

    elif action_type == "webhook":
        url = config.get("url", "")
        method = config.get("method", "POST")
        payload = config.get("payload", "{}")
        if url:
            url = await _substitute_variables(url, update, context, chat_id, command_id)
            try:
                payload_str = await _substitute_variables(
                    payload, update, context, chat_id, command_id
                )
                data = json.loads(payload_str)
                async with httpx.AsyncClient() as client:
                    if method.upper() == "POST":
                        await client.post(url, json=data, timeout=5.0)
                    elif method.upper() == "GET":
                        await client.get(url, params=data, timeout=5.0)
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] webhook action failed: {e}")

    elif action_type == "pin":
        try:
            if update.message.reply_to_message:
                await context.bot.pin_chat_message(
                    chat_id, update.message.reply_to_message.message_id
                )
        except Exception as e:
            logger.debug(f"[CUSTOM_CMD] pin action failed: {e}")

    elif action_type == "set_variable":
        var_name = config.get("var_name", "")
        var_value = config.get("var_value", "")
        if var_name:
            var_value = await _substitute_variables(
                var_value, update, context, chat_id, command_id
            )
            try:
                await set_variable(
                    db.pool,
                    chat_id,
                    var_name,
                    var_value,
                    config.get("var_type", "string"),
                    command_id,
                )
            except Exception as e:
                logger.warning(f"[CUSTOM_CMD] set_variable action failed: {e}")


def _match_trigger(trigger: dict, message_text: str, is_command: bool) -> bool:
    """Check if a message matches a trigger."""
    trigger_type = trigger.get("type", "")
    trigger_value = trigger.get("value", "")
    case_sensitive = trigger.get("case_sensitive", False)

    if trigger_type == "command":
        if not is_command:
            return False
        cmd = message_text.split()[0].lower() if message_text else ""
        expected = f"/{trigger_value.lower().lstrip('/')}"
        return cmd == expected or cmd.startswith(f"{expected}@")

    if trigger_type == "keyword":
        text = message_text if case_sensitive else message_text.lower()
        keyword = trigger_value if case_sensitive else trigger_value.lower()
        return keyword in text

    if trigger_type == "regex":
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            return bool(re.search(trigger_value, message_text, flags))
        except re.error:
            return False

    if trigger_type == "message":
        return True  # Matches any message

    if trigger_type == "new_member":
        return message_text == "__new_member__"

    if trigger_type == "left_member":
        return message_text == "__left_member__"

    if trigger_type == "exact":
        if case_sensitive:
            return message_text.strip() == trigger_value.strip()
        return message_text.strip().lower() == trigger_value.strip().lower()

    return False


async def custom_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Main handler that intercepts messages and checks for custom command triggers.
    Should be registered at a low priority group so it runs after built-in commands.
    """
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    message_text = update.message.text or update.message.caption or ""

    if update.message.new_chat_members:
        message_text = "__new_member__"
    elif update.message.left_chat_member:
        message_text = "__left_member__"

    if not message_text and not update.message.new_chat_members and not update.message.left_chat_member:
        return

    is_command = message_text.startswith("/")

    try:
        commands = await get_all_enabled_commands_with_triggers(db.pool, chat_id)
    except Exception as e:
        logger.debug(f"[CUSTOM_CMD] Failed to load commands for chat {chat_id}: {e}")
        return

    for cmd in commands:
        # Check if any trigger matches
        matched = False
        for trigger in cmd.get("triggers", []):
            if _match_trigger(trigger, message_text, is_command):
                matched = True
                break

        if not matched:
            continue

        # Check rate limit
        cooldown = cmd.get("cooldown_secs", 0) or 0
        if cooldown > 0:
            allowed = await check_rate_limit(
                db.pool, chat_id, user_id, cmd["id"], cooldown
            )
            if not allowed:
                logger.debug(
                    f"[CUSTOM_CMD] Rate-limited: cmd={cmd['name']} user={user_id}"
                )
                continue

        # Execute actions
        try:
            actions = await get_actions(db.pool, cmd["id"])
            executed = 0
            for action in actions:
                if executed >= MAX_ACTIONS_PER_EXEC:
                    logger.warning(
                        f"[CUSTOM_CMD] Max actions reached for cmd={cmd['name']}"
                    )
                    break

                # Evaluate condition
                condition = action.get("condition")
                if condition and not await _evaluate_condition(
                    condition, update, context, chat_id, cmd["id"]
                ):
                    continue

                await _execute_action(action, update, context, chat_id, cmd["id"])
                executed += 1

            await increment_execution(db.pool, cmd["id"])
            logger.debug(
                f"[CUSTOM_CMD] Executed '{cmd['name']}' in chat {chat_id} "
                f"({executed} actions)"
            )
        except Exception as e:
            logger.error(f"[CUSTOM_CMD] Error executing '{cmd['name']}': {e}")

        # Only execute first matching command (highest priority)
        break
