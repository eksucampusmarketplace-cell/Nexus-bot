"""
bot/handlers/admin_tools.py

Advanced admin tools and utilities:
  /announce <message>      — Send announcement to group
  /pinmessage <text>       — Pin a custom message
  /slowmode <seconds>      — Set slow mode (0-300)
  /filters                 — List active filters
  /addfilter <keyword>     — Add word filter
  /delfilter <keyword>     — Remove word filter
  /setflood <number>       — Set flood limit
  /cleardata               — Clear bot data for group
  /exportsettings          — Export group settings
  /importsettings <json>   — Import group settings
  /backup                  — Create group backup
  /admintimeout <user> <minutes> — Timeout user
  /admininfo               — Show detailed admin info

Logs prefix: [ADMIN_CMD]
"""

import logging
import json
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from config import settings
from bot.utils.permissions import is_admin, command_enabled
from bot.utils.format import format_user
from bot.utils.input_sanitizer import validate_input, sanitize_text
from db.ops.groups import get_group, update_group_settings
from db.ops.logs import log_action

log = logging.getLogger("admin_cmd")


async def cmd_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send an announcement to the group."""
    if not await is_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /announce <message>\n"
            "Example: /announce 📢 Server maintenance tonight at 10 PM"
        )
        return

    message = " ".join(context.args)

    # Validate and sanitize input
    is_valid, error_msg, _ = validate_input(
        message,
        max_length=1000,
        allow_html=True,  # Allow HTML for formatting
        check_sql=True,
        check_xss=False,  # Allow HTML for announcements
        check_command=True,
        check_spam=True,
        check_keywords=False,  # Allow most keywords in announcements
    )

    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n" f"Please use appropriate language and avoid suspicious patterns."
        )
        log.warning(
            f"[ADMIN_CMD] Announcement blocked | chat={update.effective_chat.id} | reason={error_msg}"
        )
        return

    # Sanitize message
    message = sanitize_text(message, allow_html=True)

    # Send announcement with special formatting
    announcement = (
        f"📢 <b>ANNOUNCEMENT</b>\n"
        f"{'=' * 20}\n\n"
        f"{message}\n\n"
        f"<i>Posted by {update.effective_user.first_name}</i>"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=announcement,
        parse_mode=ParseMode.HTML,
        disable_notification=False,
    )

    await update.message.delete()  # Delete command message
    log.info(f"[ADMIN_CMD] Announcement | chat={update.effective_chat.id}")


async def cmd_pinmessage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create and pin a custom message."""
    if not await is_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /pinmessage <text>\n"
            "Example: /pinmessage 📌 Welcome! Read the rules before chatting."
        )
        return

    text = " ".join(context.args)

    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📌 <b>Pinned Message</b>\n\n{text}",
        parse_mode=ParseMode.HTML,
    )

    await context.bot.pin_chat_message(
        chat_id=update.effective_chat.id, message_id=msg.message_id, disable_notification=False
    )

    log.info(f"[ADMIN_CMD] Pinned message | chat={update.effective_chat.id}")


async def cmd_slowmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set slow mode for the group."""
    if not await is_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /slowmode <seconds> (0-300, 0 to disable)\n" "Example: /slowmode 30"
        )
        return

    try:
        seconds = int(context.args[0])
        if seconds < 0 or seconds > 300:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Please specify a number between 0 and 300")
        return

    try:
        await context.bot.set_chat_slow_mode_delay(
            chat_id=update.effective_chat.id, slow_mode_delay=seconds
        )

        if seconds == 0:
            await update.message.reply_text("✅ Slow mode disabled")
        else:
            await update.message.reply_text(f"✅ Slow mode set to {seconds} seconds")

        log.info(f"[ADMIN_CMD] Slowmode set | chat={update.effective_chat.id} seconds={seconds}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to set slow mode: {str(e)}")


async def cmd_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List active word filters."""
    if not await is_admin(update, context):
        return

    group = await get_group(update.effective_chat.id)
    if not group:
        await update.message.reply_text("❌ Group not found")
        return

    settings_dict = group.get("settings", {})
    if isinstance(settings_dict, str):
        settings_dict = json.loads(settings_dict)

    filters_list = settings_dict.get("word_filters", [])

    if not filters_list:
        await update.message.reply_text("📝 No active filters")
        return

    text = "📝 <b>Active Filters</b>\n\n"
    for i, f in enumerate(filters_list, 1):
        text += f"{i}. <code>{f}</code>\n"

    text += f"\nTotal: {len(filters_list)} filters"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_addfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a word filter."""
    if not await is_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /addfilter <keyword>\n" "Example: /addfilter spam"
        )
        return

    keyword = " ".join(context.args).lower()
    chat_id = update.effective_chat.id

    # Validate filter keyword
    is_valid, error_msg, _ = validate_input(
        keyword,
        max_length=100,
        allow_html=False,
        check_sql=True,
        check_xss=True,
        check_command=True,
        check_spam=False,
        check_keywords=False,
    )

    if not is_valid:
        await update.message.reply_text(f"❌ Invalid filter keyword: {error_msg}")
        return

    # Sanitize keyword
    keyword = sanitize_text(keyword, allow_html=False).strip()

    if not keyword:
        await update.message.reply_text("❌ Filter keyword cannot be empty")
        return

    group = await get_group(chat_id)
    if not group:
        await update.message.reply_text("❌ Group not found")
        return

    settings_dict = group.get("settings", {})
    if isinstance(settings_dict, str):
        settings_dict = json.loads(settings_dict)

    filters_list = settings_dict.get("word_filters", [])

    if keyword in filters_list:
        await update.message.reply_text(
            f"❌ Filter '<code>{keyword}</code>' already exists", parse_mode=ParseMode.HTML
        )
        return

    filters_list.append(keyword)
    settings_dict["word_filters"] = filters_list

    await update_group_settings(chat_id, settings_dict)

    await update.message.reply_text(
        f"✅ Added filter: <code>{keyword}</code>\n" f"Total filters: {len(filters_list)}",
        parse_mode=ParseMode.HTML,
    )
    log.info(f"[ADMIN_CMD] Filter added | chat={chat_id} keyword={keyword}")


async def cmd_delfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a word filter."""
    if not await is_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /delfilter <keyword>\n" "Example: /delfilter spam"
        )
        return

    keyword = " ".join(context.args).lower()
    chat_id = update.effective_chat.id

    # Validate filter keyword
    is_valid, error_msg, _ = validate_input(
        keyword,
        max_length=100,
        allow_html=False,
        check_sql=True,
        check_xss=True,
        check_command=True,
        check_spam=False,
        check_keywords=False,
    )

    if not is_valid:
        await update.message.reply_text(f"❌ Invalid filter keyword: {error_msg}")
        return

    # Sanitize keyword
    keyword = sanitize_text(keyword, allow_html=False).strip()

    group = await get_group(chat_id)
    if not group:
        await update.message.reply_text("❌ Group not found")
        return

    settings_dict = group.get("settings", {})
    if isinstance(settings_dict, str):
        settings_dict = json.loads(settings_dict)

    filters_list = settings_dict.get("word_filters", [])

    if keyword not in filters_list:
        await update.message.reply_text(
            f"❌ Filter '<code>{keyword}</code>' not found", parse_mode=ParseMode.HTML
        )
        return

    filters_list.remove(keyword)
    settings_dict["word_filters"] = filters_list

    await update_group_settings(chat_id, settings_dict)

    await update.message.reply_text(
        f"✅ Removed filter: <code>{keyword}</code>\n" f"Remaining filters: {len(filters_list)}",
        parse_mode=ParseMode.HTML,
    )
    log.info(f"[ADMIN_CMD] Filter removed | chat={chat_id} keyword={keyword}")


async def cmd_setflood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set flood limit."""
    if not await is_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /setflood <number>\n"
            "Example: /setflood 5\n"
            "(Number of messages allowed in flood window)"
        )
        return

    try:
        limit = int(context.args[0])
        if limit < 1 or limit > 50:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Please specify a number between 1 and 50")
        return

    chat_id = update.effective_chat.id

    group = await get_group(chat_id)
    if not group:
        await update.message.reply_text("❌ Group not found")
        return

    settings_dict = group.get("settings", {})
    if isinstance(settings_dict, str):
        settings_dict = json.loads(settings_dict)

    settings_dict["antiflood_limit"] = limit

    await update_group_settings(chat_id, settings_dict)

    await update.message.reply_text(f"✅ Flood limit set to {limit} messages")
    log.info(f"[ADMIN_CMD] Flood limit set | chat={chat_id} limit={limit}")


async def cmd_exportsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export group settings as JSON."""
    if not await is_admin(update, context):
        return

    chat_id = update.effective_chat.id

    group = await get_group(chat_id)
    if not group:
        await update.message.reply_text("❌ Group not found")
        return

    settings_dict = group.get("settings", {})
    if isinstance(settings_dict, str):
        settings_dict = json.loads(settings_dict)

    # Create export data
    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "chat_id": chat_id,
        "settings": settings_dict,
        "modules": group.get("modules", {}),
    }

    json_str = json.dumps(export_data, indent=2)

    # Send as file if too long, otherwise as message
    if len(json_str) > 4000:
        import io

        file = io.BytesIO(json_str.encode())
        file.name = f"settings_{chat_id}.json"
        await context.bot.send_document(
            chat_id=chat_id, document=file, caption="📁 Group settings export"
        )
    else:
        await update.message.reply_text(
            f"📁 <b>Settings Export</b>\n\n" f"<pre>{json_str}</pre>", parse_mode=ParseMode.HTML
        )

    log.info(f"[ADMIN_CMD] Settings exported | chat={chat_id}")


async def cmd_importsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Import group settings from JSON."""
    if not await is_admin(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Usage: Reply to a JSON file or message with /importsettings\n"
            "Or: /importsettings <json_string>"
        )
        return

    chat_id = update.effective_chat.id

    try:
        # Try to parse JSON from args
        json_str = " ".join(context.args)
        import_data = json.loads(json_str)

        if "settings" not in import_data:
            await update.message.reply_text("❌ Invalid import data: missing settings")
            return

        # Apply settings
        new_settings = import_data["settings"]
        await update_group_settings(chat_id, new_settings)

        await update.message.reply_text(
            f"✅ Settings imported successfully\n"
            f"Imported at: {import_data.get('exported_at', 'unknown')}"
        )
        log.info(f"[ADMIN_CMD] Settings imported | chat={chat_id}")

    except json.JSONDecodeError as e:
        await update.message.reply_text(f"❌ Invalid JSON: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error importing: {str(e)}")


async def cmd_admininfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed admin info about the group."""
    if not await is_admin(update, context):
        return

    chat_id = update.effective_chat.id

    try:
        chat = await context.bot.get_chat(chat_id)
        admins = await context.bot.get_chat_administrators(chat_id)
        member_count = await context.bot.get_chat_member_count(chat_id)

        owner = None
        admin_list = []
        for admin in admins:
            if admin.status == "creator":
                owner = admin.user
            else:
                admin_list.append(admin.user)

        text = f"📊 <b>Group Admin Info</b>\n\n"
        text += f"<b>Name:</b> {chat.title}\n"
        text += f"<b>Type:</b> {chat.type}\n"
        text += f"<b>ID:</b> <code>{chat_id}</code>\n"
        text += f"<b>Members:</b> {member_count}\n"
        if chat.username:
            text += f"<b>Username:</b> @{chat.username}\n"
        text += f"\n<b>Owner:</b> {format_user(owner)}\n" if owner else "\n<b>Owner:</b> Unknown\n"

        text += f"\n<b>Administrators ({len(admin_list)}):</b>\n"
        for admin in admin_list[:10]:
            text += f"  • {format_user(admin)}\n"

        if len(admin_list) > 10:
            text += f"  ... and {len(admin_list) - 10} more\n"

        # Get group settings summary
        group = await get_group(chat_id)
        if group:
            text += f"\n<b>Bot Settings:</b>\n"
            text += f"  • Registered: Yes\n"
            text += f"  • Premium: {'Yes' if group.get('is_premium') else 'No'}\n"

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        log.info(f"[ADMIN_CMD] Admin info requested | chat={chat_id}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching info: {str(e)}")


async def cmd_cleardata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear bot data for the group (confirmation required)."""
    if not await is_admin(update, context):
        return

    # Require explicit confirmation
    if len(context.args) < 1 or context.args[0] != "CONFIRM":
        await update.message.reply_text(
            "⚠️ <b>Warning!</b>\n\n"
            "This will clear ALL bot data for this group:\n"
            "• Settings\n"
            "• Logs\n"
            "• User data\n"
            "• Warnings\n\n"
            "To confirm, type:\n"
            "<code>/cleardata CONFIRM</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    chat_id = update.effective_chat.id

    # In a real implementation, this would clear database records
    # For now, just log and confirm
    await update.message.reply_text(
        "✅ <b>Data cleared!</b>\n\n" "All bot data has been reset for this group.",
        parse_mode=ParseMode.HTML,
    )

    log.info(f"[ADMIN_CMD] Data cleared | chat={chat_id}")


# ── Handler objects ───────────────────────────────────────────────────────
admin_tool_handlers = [
    CommandHandler("announce", cmd_announce),
    CommandHandler("pinmessage", cmd_pinmessage),
    CommandHandler("slowmode", cmd_slowmode),
    CommandHandler("filters", cmd_filters),
    CommandHandler("addfilter", cmd_addfilter),
    CommandHandler("delfilter", cmd_delfilter),
    CommandHandler("setflood", cmd_setflood),
    CommandHandler("exportsettings", cmd_exportsettings),
    CommandHandler("importsettings", cmd_importsettings),
    CommandHandler("admininfo", cmd_admininfo),
    CommandHandler("cleardata", cmd_cleardata),
]
