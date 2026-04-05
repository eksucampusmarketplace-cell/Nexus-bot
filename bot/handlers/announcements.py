"""
bot/handlers/announcements.py

Announcement Channel integration handler.
Detects and processes forwarded channel posts from linked announcement channels.
"""

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

log = logging.getLogger("announcements")


async def handle_announcement_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires on every group message. Detects if the message is from the linked channel.
    Channel posts forwarded into supergroup have sender_chat set.
    """
    message = update.effective_message
    chat = update.effective_chat
    
    if not message or not chat:
        return
    
    # Channel posts forwarded into supergroup have sender_chat set
    if not message.sender_chat:
        return
    
    # Only process in groups
    if chat.type not in ["group", "supergroup"]:
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    if not db:
        return
    
    try:
        async with db.acquire() as conn:
            cfg = await conn.fetchrow(
                """SELECT announcement_channel_id, announcement_auto_pin,
                          announcement_notifications, announcement_auto_delete_mins,
                          announcement_restrict_replies
                   FROM groups WHERE chat_id = $1""",
                chat.id
            )
        
        if not cfg or cfg["announcement_channel_id"] != message.sender_chat.id:
            return  # not from the configured linked channel
        
        # Auto-pin if enabled
        if cfg["announcement_auto_pin"]:
            try:
                await context.bot.pin_chat_message(chat.id, message.message_id)
                log.debug(f"[ANNOUNCEMENTS] Auto-pinned message {message.message_id} in {chat.id}")
            except Exception as e:
                log.warning(f"[ANNOUNCEMENTS] Failed to auto-pin message: {e}")
        
        # Notify admins if enabled
        if cfg["announcement_notifications"]:
            await _notify_admins(context.bot, chat, message)
        
        # Schedule deletion if enabled
        if cfg["announcement_auto_delete_mins"] and cfg["announcement_auto_delete_mins"] > 0:
            delay_seconds = cfg["announcement_auto_delete_mins"] * 60
            asyncio.create_task(
                _schedule_delete(context.bot, chat.id, message.message_id, delay_seconds)
            )
        
        # Restrict replies if enabled
        if cfg["announcement_restrict_replies"]:
            asyncio.create_task(
                _restrict_replies_temporarily(context.bot, chat.id, message.message_id)
            )
            
    except Exception as e:
        log.error(f"[ANNOUNCEMENTS] Error handling announcement post: {e}")


async def _notify_admins(bot, chat, message):
    """Send notification to admins about new announcement."""
    try:
        # Get chat info for the message
        channel_title = message.sender_chat.title if message.sender_chat else "Channel"
        
        # Build notification text
        text = (
            f"📢 <b>New Announcement</b>\n\n"
            f"Channel: {channel_title}\n"
            f"Group: {chat.title}\n"
        )
        
        if message.text:
            preview = message.text[:200] + "..." if len(message.text) > 200 else message.text
            text += f"\nPreview: {preview}"
        
        # Try to get admin list and notify them
        try:
            admins = await bot.get_chat_administrators(chat.id)
            for admin in admins:
                if not admin.user.is_bot:
                    try:
                        await bot.send_message(
                            admin.user.id,
                            text,
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass  # User may have blocked the bot
        except Exception as e:
            log.warning(f"[ANNOUNCEMENTS] Failed to get admins for notification: {e}")
            
    except Exception as e:
        log.error(f"[ANNOUNCEMENTS] Failed to notify admins: {e}")


async def _schedule_delete(bot, chat_id: int, message_id: int, delay_seconds: int):
    """Schedule message deletion after delay."""
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_message(chat_id, message_id)
        log.debug(f"[ANNOUNCEMENTS] Auto-deleted message {message_id} in {chat_id}")
    except Exception as e:
        log.warning(f"[ANNOUNCEMENTS] Failed to auto-delete message: {e}")


async def _restrict_replies_temporarily(bot, chat_id: int, message_id: int):
    """
    Temporarily restrict replies to announcement posts.
    This is a simplified implementation - full implementation would require
    tracking permissions and restoring them properly.
    """
    try:
        # For now, we just log this feature
        # A full implementation would:
        # 1. Save current permissions
        # 2. Set can_send_messages=False for non-admins
        # 3. Restore permissions after 5 minutes
        log.debug(f"[ANNOUNCEMENTS] Reply restriction requested for message {message_id}")
    except Exception as e:
        log.error(f"[ANNOUNCEMENTS] Failed to restrict replies: {e}")


# Handler registration
announcement_handlers = [
    MessageHandler(
        filters.ALL & filters.ChatType.GROUPS,
        handle_announcement_post
    ),
]
