"""
Auto-delete messages handler
Automatically deletes bot messages after a set time
"""

import logging
import asyncio
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

import db.ops.groups as db_groups

logger = logging.getLogger(__name__)


async def cmd_autodelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Set auto-delete timeout for bot messages
    Usage: /autodelete <seconds> or /autodelete off
    """
    chat_id = update.effective_chat.id
    user = update.effective_user
    pool = context.bot_data.get("db_pool")

    if not pool:
        await update.message.reply_text("⚠️ Database not available.")
        return

    # Check admin rights
    try:
        member = await update.effective_chat.get_member(user.id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("⛔ Only admins can use this command.")
            return
    except Exception as e:
        logger.error(f"[AUTODELETE] Error checking admin: {e}")
        return

    if not context.args:
        # Show current setting
        settings = await db_groups.get_group_settings(pool, chat_id)
        current = settings.get("auto_delete_seconds", 0) if settings else 0

        if current > 0:
            await update.message.reply_text(
                f"⏱️ Auto-delete is enabled.\n"
                f"Bot messages are deleted after {current} seconds.\n\n"
                f"To change: /autodelete <seconds>\n"
                f"To disable: /autodelete off"
            )
        else:
            await update.message.reply_text(
                "⏱️ Auto-delete is currently disabled.\n\n"
                "To enable: /autodelete <seconds>\n"
                "Example: /autodelete 30"
            )
        return

    arg = context.args[0].lower()

    if arg == "off" or arg == "0":
        await db_groups.set_group_setting(pool, chat_id, auto_delete_seconds=0)
        await update.message.reply_text("✅ Auto-delete disabled.")
        logger.info(f"[AUTODELETE] Disabled for chat {chat_id}")
        return

    try:
        seconds = int(arg)
        if seconds < 5:
            await update.message.reply_text("❌ Minimum auto-delete time is 5 seconds.")
            return
        if seconds > 3600:
            await update.message.reply_text("❌ Maximum auto-delete time is 1 hour (3600 seconds).")
            return

        await db_groups.set_group_setting(pool, chat_id, auto_delete_seconds=seconds)

        msg = await update.message.reply_text(
            f"✅ Auto-delete enabled!\n"
            f"Bot messages will be deleted after {seconds} seconds.\n\n"
            f"Note: Some important messages (like warnings) won't be deleted."
        )

        # Auto-delete this message too after delay
        if seconds <= 60:
            asyncio.create_task(delete_after(msg, seconds))

        logger.info(f"[AUTODELETE] Set to {seconds}s for chat {chat_id}")

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid format.\n"
            "Usage: /autodelete <seconds> or /autodelete off\n"
            "Example: /autodelete 30"
        )


async def delete_after(message, seconds: int):
    """Delete a message after specified seconds"""
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass


async def should_auto_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> Optional[int]:
    """
    Check if auto-delete is enabled for a chat
    Returns seconds if enabled, None otherwise
    """
    pool = context.bot_data.get("db_pool")
    if not pool:
        return None

    try:
        settings = await db_groups.get_group_settings(pool, chat_id)
        if settings:
            seconds = settings.get("auto_delete_seconds", 0)
            return seconds if seconds > 0 else None
    except Exception as e:
        logger.error(f"[AUTODELETE] Error checking settings: {e}")

    return None


async def auto_delete_message(
    message, context: ContextTypes.DEFAULT_TYPE, exclude_important: bool = False
):
    """
    Schedule a message for auto-deletion if enabled
    Call this after sending bot messages
    """
    if not message or not message.chat:
        return

    # Don't delete important messages if excluded
    if exclude_important:
        # Check if message contains important info
        if message.text and any(
            kw in message.text.lower() for kw in ["warning", "banned", "muted", "important"]
        ):
            return

    seconds = await should_auto_delete(context, message.chat.id)
    if seconds:
        asyncio.create_task(delete_after(message, seconds))


# Command handler
autodelete_command = CommandHandler("autodelete", cmd_autodelete)

# Export
__all__ = ["autodelete_command", "auto_delete_message", "should_auto_delete"]
