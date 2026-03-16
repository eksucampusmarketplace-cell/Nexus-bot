"""
bot/handlers/night_mode.py

Night Mode System - Scheduled group access control v21
Restricts group at night, restores permissions in morning.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import pytz
from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes, CommandHandler

from bot.utils.permissions import is_admin
from bot.utils.localization import get_locale, get_trust_level

log = logging.getLogger("night_mode")


def parse_time(time_str: str) -> Optional[tuple]:
    """Parse time string (HH:MM) into (hour, minute)."""
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if 0 <= hour < 24 and 0 <= minute < 60:
            return (hour, minute)
    except (ValueError, IndexError):
        pass
    return None


def format_time(hour: int, minute: int) -> str:
    """Format time as HH:MM."""
    return f"{hour:02d}:{minute:02d}"


async def cmd_nightmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /nightmode - Manage night mode settings
    
    Usage:
      /nightmode 23:00 07:00 - Set schedule
      /nightmode tz Asia/Dubai - Set timezone
      /nightmode on - Enable
      /nightmode off - Disable
      /nightmode status - Show current status
    """
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Use this command in a group.")
        return
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    # Get current settings
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT settings FROM groups WHERE chat_id = $1",
            chat.id
        )
        
        settings = row["settings"] or {} if row else {}
        if isinstance(settings, str):
            settings = json.loads(settings)
        
        night_mode = settings.get("night_mode", {})
    
    if not context.args:
        # Show status
        enabled = night_mode.get("enabled", False)
        start = night_mode.get("start_time", "23:00")
        end = night_mode.get("end_time", "07:00")
        tz = night_mode.get("timezone", "UTC")
        
        status = "✅ Enabled" if enabled else "❌ Disabled"
        
        await update.message.reply_text(
            f"🌙 <b>Night Mode Settings</b>\n\n"
            f"Status: {status}\n"
            f"Schedule: {start} → {end}\n"
            f"Timezone: {tz}\n\n"
            f"<b>Commands:</b>\n"
            f"<code>/nightmode 23:00 07:00</code> - Set times\n"
            f"<code>/nightmode tz Asia/Dubai</code> - Set timezone\n"
            f"<code>/nightmode on</code> - Enable\n"
            f"<code>/nightmode off</code> - Disable\n"
            f"<code>/nightmode status</code> - Show this",
            parse_mode="HTML"
        )
        return
    
    subcommand = context.args[0].lower()
    
    if subcommand in ["on", "enable", "true"]:
        night_mode["enabled"] = True
        await _save_night_mode(db, chat.id, settings, night_mode)
        await update.message.reply_text(
            "🌙 <b>Night Mode Enabled</b>\n\n"
            f"Schedule: {night_mode.get('start_time', '23:00')} → {night_mode.get('end_time', '07:00')}\n"
            "The group will be restricted at night.",
            parse_mode="HTML"
        )
        log.info(f"[NIGHT] Enabled | chat={chat.id}")
        
    elif subcommand in ["off", "disable", "false"]:
        night_mode["enabled"] = False
        await _save_night_mode(db, chat.id, settings, night_mode)
        await update.message.reply_text(
            "☀️ <b>Night Mode Disabled</b>\n\n"
            "Night restrictions are now off.",
            parse_mode="HTML"
        )
        log.info(f"[NIGHT] Disabled | chat={chat.id}")
        
    elif subcommand == "status":
        enabled = night_mode.get("enabled", False)
        start = night_mode.get("start_time", "23:00")
        end = night_mode.get("end_time", "07:00")
        tz = night_mode.get("timezone", "UTC")
        
        # Check current state
        is_restricted = await _is_currently_restricted(night_mode)
        state = "🌙 RESTRICTED" if is_restricted else "☀️ Normal"
        
        await update.message.reply_text(
            f"🌙 <b>Night Mode Status</b>\n\n"
            f"Enabled: {'✅ Yes' if enabled else '❌ No'}\n"
            f"Schedule: {start} → {end}\n"
            f"Timezone: {tz}\n"
            f"Current State: {state}",
            parse_mode="HTML"
        )
        
    elif subcommand == "tz" or subcommand == "timezone":
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Please provide a timezone.\n"
                "Examples: UTC, Asia/Dubai, America/New_York, Europe/London"
            )
            return
        
        tz_name = context.args[1]
        
        # Validate timezone
        try:
            pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            await update.message.reply_text(
                f"❌ Unknown timezone: {tz_name}\n"
                f"Use IANA timezone names like: UTC, Asia/Dubai, Europe/London"
            )
            return
        
        night_mode["timezone"] = tz_name
        await _save_night_mode(db, chat.id, settings, night_mode)
        await update.message.reply_text(
            f"✅ <b>Timezone Updated</b>\n\n"
            f"Timezone: {tz_name}",
            parse_mode="HTML"
        )
        log.info(f"[NIGHT] Timezone | chat={chat.id} tz={tz_name}")
        
    elif subcommand == "message":
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Please provide a custom message.\n"
                "Use {end_time} placeholder for the morning time."
            )
            return
        
        custom_msg = " ".join(context.args[1:])
        night_mode["custom_message"] = custom_msg
        await _save_night_mode(db, chat.id, settings, night_mode)
        await update.message.reply_text(
            f"✅ <b>Custom Message Updated</b>\n\n"
            f"Message: {custom_msg}",
            parse_mode="HTML"
        )
        
    else:
        # Try to parse as time settings
        if len(context.args) >= 2:
            start_time = parse_time(context.args[0])
            end_time = parse_time(context.args[1])
            
            if not start_time or not end_time:
                await update.message.reply_text(
                    "❌ Invalid time format. Use HH:MM (e.g., 23:00 07:00)"
                )
                return
            
            night_mode["start_time"] = format_time(*start_time)
            night_mode["end_time"] = format_time(*end_time)
            await _save_night_mode(db, chat.id, settings, night_mode)
            
            await update.message.reply_text(
                f"✅ <b>Night Mode Schedule Updated</b>\n\n"
                f"Start: {night_mode['start_time']}\n"
                f"End: {night_mode['end_time']}\n\n"
                f"Use <code>/nightmode on</code> to enable.",
                parse_mode="HTML"
            )
            log.info(f"[NIGHT] Schedule | chat={chat.id} {night_mode['start_time']}-{night_mode['end_time']}")
        else:
            await update.message.reply_text(
                "❌ Invalid command.\n\n"
                "Usage:\n"
                "<code>/nightmode 23:00 07:00</code>\n"
                "<code>/nightmode tz Asia/Dubai</code>\n"
                "<code>/nightmode on/off</code>"
            )


async def _save_night_mode(db, chat_id: int, settings: dict, night_mode: dict):
    """Save night mode settings to database."""
    settings["night_mode"] = night_mode
    
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE groups SET settings = $1 WHERE chat_id = $2",
            settings, chat_id
        )


async def _is_currently_restricted(night_mode: dict) -> bool:
    """Check if night mode should currently be active."""
    if not night_mode.get("enabled", False):
        return False
    
    tz_name = night_mode.get("timezone", "UTC")
    start_str = night_mode.get("start_time", "23:00")
    end_str = night_mode.get("end_time", "07:00")
    
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        
        start_parts = start_str.split(":")
        end_parts = end_str.split(":")
        
        start_hour = int(start_parts[0])
        start_min = int(start_parts[1]) if len(start_parts) > 1 else 0
        end_hour = int(end_parts[0])
        end_min = int(end_parts[1]) if len(end_parts) > 1 else 0
        
        start_time = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        end_time = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        # Handle overnight case (e.g., 23:00 to 07:00)
        if start_hour > end_hour or (start_hour == end_hour and start_min > end_min):
            # Night spans midnight
            if now >= start_time or now < end_time:
                return True
        else:
            # Daytime restriction (rare, but possible)
            if start_time <= now < end_time:
                return True
                
    except Exception as e:
        log.error(f"[NIGHT] Time check error: {e}")
    
    return False


async def _apply_night_restriction(bot, chat_id: int, night_mode: dict):
    """Apply night mode restrictions to a group."""
    try:
        # Get current permissions to save
        chat = await bot.get_chat(chat_id)
        
        # Save original permissions
        perms = chat.permissions
        original_perms = {
            "can_send_messages": perms.can_send_messages if perms else True,
            "can_send_media_messages": perms.can_send_media_messages if perms else True,
            "can_send_polls": perms.can_send_polls if perms else True,
            "can_send_other_messages": perms.can_send_other_messages if perms else True,
            "can_add_web_page_previews": perms.can_add_web_page_previews if perms else True,
            "can_change_info": perms.can_change_info if perms else False,
            "can_invite_users": perms.can_invite_users if perms else True,
            "can_pin_messages": perms.can_pin_messages if perms else False,
        }
        
        # Store original permissions
        db = bot.bot_data.get("db_pool") or bot.bot_data.get("db")
        if db:
            async with db.acquire() as conn:
                settings_row = await conn.fetchrow(
                    "SELECT settings FROM groups WHERE chat_id = $1", chat_id
                )
                settings = settings_row["settings"] or {} if settings_row else {}
                if isinstance(settings, str):
                    settings = json.loads(settings)
                
                night_settings = settings.get("night_mode", {})
                night_settings["restored_permissions"] = original_perms
                settings["night_mode"] = night_settings
                
                await conn.execute(
                    "UPDATE groups SET settings = $1 WHERE chat_id = $2",
                    settings, chat_id
                )
        
        # Apply restricted permissions (admins can still chat)
        restricted_perms = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=True,  # Allow invites
            can_pin_messages=False,
        )
        
        await bot.set_chat_permissions(chat_id, restricted_perms)
        
        # Send notification
        end_time = night_mode.get("end_time", "07:00")
        custom_msg = night_mode.get("custom_message")
        
        if custom_msg:
            msg_text = custom_msg.replace("{end_time}", end_time)
        else:
            # Use localized messages
            locale = get_locale(night_mode.get("language", "en"))
            msg_text = locale.get("night_mode_on", end_time=end_time)
        
        await bot.send_message(chat_id, msg_text, parse_mode="HTML")
        
        # Log
        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO night_mode_log (chat_id, action, start_time, end_time, permissions_snapshot)
                   VALUES ($1, $2, $3, $4, $5)""",
                chat_id, "restricted", night_mode.get("start_time"), end_time, original_perms
            )
        
        log.info(f"[NIGHT] Restricted | chat={chat_id}")
        
    except Exception as e:
        log.error(f"[NIGHT] Restriction failed for {chat_id}: {e}")


async def _restore_day_permissions(bot, chat_id: int, night_mode: dict):
    """Restore normal permissions in the morning."""
    try:
        db = bot.bot_data.get("db_pool") or bot.bot_data.get("db")
        
        # Get saved permissions
        original_perms = night_mode.get("restored_permissions", {})
        
        if original_perms:
            perms = ChatPermissions(
                can_send_messages=original_perms.get("can_send_messages", True),
                can_send_media_messages=original_perms.get("can_send_media_messages", True),
                can_send_polls=original_perms.get("can_send_polls", True),
                can_send_other_messages=original_perms.get("can_send_other_messages", True),
                can_add_web_page_previews=original_perms.get("can_add_web_page_previews", True),
                can_change_info=original_perms.get("can_change_info", False),
                can_invite_users=original_perms.get("can_invite_users", True),
                can_pin_messages=original_perms.get("can_pin_messages", False),
            )
        else:
            # Default permissions
            perms = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
            )
        
        await bot.set_chat_permissions(chat_id, perms)
        
        # Send notification
        locale = get_locale(night_mode.get("language", "en"))
        msg_text = locale.get("night_mode_off")
        
        await bot.send_message(chat_id, msg_text, parse_mode="HTML")
        
        # Log
        if db:
            async with db.acquire() as conn:
                await conn.execute(
                    """INSERT INTO night_mode_log (chat_id, action, start_time, end_time, permissions_snapshot)
                       VALUES ($1, $2, $3, $4, $5)""",
                    chat_id, "restored", night_mode.get("start_time"), 
                    night_mode.get("end_time"), original_perms
                )
        
        log.info(f"[NIGHT] Restored | chat={chat_id}")
        
    except Exception as e:
        log.error(f"[NIGHT] Restore failed for {chat_id}: {e}")


async def night_mode_scheduler(context: ContextTypes.DEFAULT_TYPE):
    """Background task that runs every 60 seconds to check night mode status."""
    bot = context.bot
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    if not db:
        return
    
    try:
        async with db.acquire() as conn:
            # Get all groups with night mode enabled
            groups = await conn.fetch(
                """SELECT chat_id, settings FROM groups 
                   WHERE settings->'night_mode'->>'enabled' = 'true'"""
            )
        
        for group in groups:
            chat_id = group["chat_id"]
            settings = group["settings"] or {}
            if isinstance(settings, str):
                settings = json.loads(settings)
            
            night_mode = settings.get("night_mode", {})
            
            should_restrict = await _is_currently_restricted(night_mode)
            currently_restricted = night_mode.get("currently_restricted", False)
            
            if should_restrict and not currently_restricted:
                # Start night mode
                await _apply_night_restriction(bot, chat_id, night_mode)
                night_mode["currently_restricted"] = True
                await _save_night_mode(db, chat_id, settings, night_mode)
                
            elif not should_restrict and currently_restricted:
                # End night mode
                await _restore_day_permissions(bot, chat_id, night_mode)
                night_mode["currently_restricted"] = False
                await _save_night_mode(db, chat_id, settings, night_mode)
                
    except Exception as e:
        log.error(f"[NIGHT] Scheduler error: {e}")


async def start_night_mode_scheduler(application):
    """Start the night mode background scheduler."""
    from telegram.ext import Application
    
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(
            night_mode_scheduler,
            interval=60,  # Check every 60 seconds
            first=10,  # Start after 10 seconds
            name="night_mode_scheduler"
        )
        log.info("[NIGHT] Scheduler started")


# Handler registration
night_mode_handlers = [
    CommandHandler("nightmode", cmd_nightmode),
]
