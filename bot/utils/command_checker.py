"""
bot/utils/command_checker.py

Utility to check if a command is disabled for a group.
Used by command handlers to verify commands are enabled before executing.
"""

import json
import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from db.client import db

logger = logging.getLogger(__name__)


async def is_command_enabled(chat_id: int, command: str) -> bool:
    """
    Check if a command is enabled for a given chat/group.
    
    Args:
        chat_id: The group chat ID
        command: The command name (without / prefix, e.g., 'warn', 'ban', 'mute')
    
    Returns:
        True if command is enabled (or not explicitly disabled), False if disabled
    """
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT disabled_commands FROM groups WHERE chat_id = $1",
                chat_id
            )
            
            if not row or not row["disabled_commands"]:
                # No disabled commands = all enabled
                return True
            
            # Parse the disabled_commands JSON
            disabled = row["disabled_commands"]
            if isinstance(disabled, str):
                try:
                    disabled = json.loads(disabled)
                except json.JSONDecodeError:
                    return True
            
            if not isinstance(disabled, dict):
                return True
            
            # Command is disabled if explicitly set to False
            return disabled.get(command, True) is not False
    
    except Exception as e:
        logger.debug(f"[CommandChecker] Error checking command state: {e}")
        # On error, allow command to run (fail-open for safety)
        return True


async def get_disabled_commands(chat_id: int) -> dict:
    """Get all disabled commands for a group."""
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT disabled_commands FROM groups WHERE chat_id = $1",
                chat_id
            )
            
            if not row or not row["disabled_commands"]:
                return {}
            
            disabled = row["disabled_commands"]
            if isinstance(disabled, str):
                try:
                    disabled = json.loads(disabled)
                except json.JSONDecodeError:
                    return {}
            
            return disabled if isinstance(disabled, dict) else {}
    except Exception as e:
        logger.debug(f"[CommandChecker] Error getting disabled commands: {e}")
        return {}


def check_command_enabled(command_name: str):
    """
    Decorator to check if a command is enabled before executing.
    
    Usage:
        @check_command_enabled('warn')
        async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not update.effective_chat:
                return
            
            chat_id = update.effective_chat.id
            chat_type = update.effective_chat.type
            
            # Only check for groups/supergroups
            if chat_type not in ['group', 'supergroup']:
                return await func(update, context)
            
            # Check if command is enabled
            if not await is_command_enabled(chat_id, command_name):
                try:
                    await update.message.reply_text(
                        "⛔ This command is currently disabled for this group."
                    )
                except Exception:
                    pass
                return
            
            # Command is enabled, proceed
            return await func(update, context)
        
        return wrapper
    return decorator
