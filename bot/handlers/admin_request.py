"""
bot/handlers/admin_request.py

@admins mention system - users can mention @admins to request admin help.

Features:
- Detects @admins or "@ admins" in messages
- Rate limiting per user
- Sends notifications to all admins
- Tracks request status (open, responding, closed)
- Admin commands to manage requests
- Statistics and analytics
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode, MessageEntityType

from bot.utils.permissions import is_admin
from bot.logging.log_channel import log_event
import db.ops.admin_requests as db_admin_req
import db.ops.groups as db_groups

log = logging.getLogger("admin_request")

# Patterns to detect admin requests
ADMIN_MENTION_PATTERNS = [
    "@admins",
    "@admin",  # Common typo
    "@moderators",
    "@mods",
    "@admin",
    "@mods",
    # Pattern for "@ admins" (with space)
    "@ admins",
    "@ moderator",
    "@ moderators",
]

# Max length for request message
_MAX_MESSAGE_LEN = 500


def contains_admin_mention(text: str) -> bool:
    """Check if text contains an admin mention pattern."""
    if not text:
        return False
    text_lower = text.lower()
    return any(pattern.lower() in text_lower for pattern in ADMIN_MENTION_PATTERNS)


def extract_mention_context(message: Message) -> str:
    """Extract relevant context around the admin mention."""
    text = message.text or message.caption or ""
    if not text:
        return "No text content"

    # If message is short (< 100 chars), return all of it
    if len(text) <= _MAX_MESSAGE_LEN:
        return text

    # Find the mention and extract context around it
    mention_pos = -1
    for pattern in ADMIN_MENTION_PATTERNS:
        pos = text.lower().find(pattern.lower())
        if pos != -1:
            mention_pos = pos
            break

    if mention_pos == -1:
        # No explicit mention found, return first 500 chars
        return text[:_MAX_MESSAGE_LEN]

    # Extract 250 chars before and after the mention
    start = max(0, mention_pos - 250)
    end = min(len(text), mention_pos + 250)
    context = text[start:end]

    if start > 0:
        context = "..." + context
    if end < len(text):
        context = context + "..."

    return context


async def handle_admin_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle messages containing @admins mentions.
    Creates an admin request and notifies admins.
    """
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    # Skip if not in a group
    if not chat or chat.type not in ["group", "supergroup"]:
        return

    # Skip if bot message
    if user.is_bot:
        return

    # Skip if this is a command message (e.g., /admins)
    if message and message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.BOT_COMMAND:
                return

    # Check if feature is enabled for this group
    try:
        enabled = await db_admin_req.get_group_setting(db, chat.id, "admin_requests_enabled")
        if not enabled:
            return
    except Exception:
        # If setting doesn't exist, assume enabled
        pass

    # Check rate limit
    try:
        rate_limit = await db_admin_req.get_group_setting(db, chat.id, "admin_requests_rate_limit")
        rate_period = await db_admin_req.get_group_setting(db, chat.id, "admin_requests_rate_period")
    except Exception:
        rate_limit = 3
        rate_period = 3600  # 1 hour

    recent_count = await db_admin_req.get_user_recent_request_count(
        db, chat.id, user.id, rate_period
    )

    if recent_count >= rate_limit:
        # User has exceeded rate limit
        remaining = rate_period // 60  # Convert to minutes
        log.info(
            f"[ADMIN_REQ] Rate limited | chat={chat.id} user={user.id} "
            f"recent_count={recent_count} limit={rate_limit}"
        )
        await message.reply_text(
            f"⚠️ You've reached your limit of {rate_limit} admin requests in the last {remaining} minutes. "
            f"Please wait before requesting help again.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Extract message content
    message_text = extract_mention_context(message)
    reply_to_msg_id = message.reply_to_message.message_id if message.reply_to_message else None

    # Create the request in database
    try:
        request_id = await db_admin_req.create_admin_request(
            pool=db,
            chat_id=chat.id,
            user_id=user.id,
            message_id=message.message_id,
            message_text=message_text,
            reply_to_msg_id=reply_to_msg_id,
        )

        # Increment user's request count
        await db_admin_req.increment_user_request_count(db, chat.id, user.id)
    except Exception as e:
        log.error(f"[ADMIN_REQ] Failed to create request | chat={chat.id} | error={e}")
        await message.reply_text(
            "⚠️ Failed to create admin request. Please try again or use /report command.",
            parse_mode=ParseMode.HTML,
        )
        return

    log.info(
        f"[ADMIN_REQ] Created request #{request_id} | chat={chat.id} user={user.id} "
        f"message={message.message_id}"
    )

    # Send confirmation to user
    await message.reply_text(
        f"✅ <b>Admin request #{request_id} sent!</b>\n"
        f"An admin will be notified and will help you shortly.",
        parse_mode=ParseMode.HTML,
    )

    # Notify all admins
    await _notify_admins(update, context, request_id, message_text, reply_to_msg_id)

    # Log the event
    await log_event(
        bot=context.bot,
        db=db,
        chat_id=chat.id,
        event_type="admin_request",
        actor=user,
        target=None,
        details={"request_id": request_id, "message_preview": message_text[:100]},
        chat_title=chat.title or "",
    )


async def _notify_admins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    request_id: int,
    message_text: str,
    reply_to_msg_id: Optional[int]
):
    """Send notification to all group admins."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    user_name = f"@{user.username}" if user.username else user.full_name

    # Build admin notification
    admin_text = (
        f"👋 <b>Admin Request #{request_id}</b>\n\n"
        f"<b>From:</b> {user_name} (<code>{user.id}</code>)\n"
        f"<b>Group:</b> {chat.title}\n"
        f"<b>Message:</b>\n"
        f"<code>{message_text[:300]}</code>"
    )

    if len(message_text) > 300:
        admin_text += "\n<i>... (message truncated)</i>"

    admin_text += f"\n\n<b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

    # Add link to the message if available
    if chat.username:
        # Public group
        msg_link = f"https://t.me/{chat.username}/{message.message_id}"
        admin_text += f"\n🔗 <a href=\"{msg_link}\">View Message</a>"
    else:
        # Private group - use reply_to_link if available
        if reply_to_msg_id:
            admin_text += f"\n📎 Reply to message <code>{reply_to_msg_id}</code>"

    # Inline keyboard for quick actions
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Responding", callback_data=f"admin_req:responding:{request_id}"),
            InlineKeyboardButton("✅ Close", callback_data=f"admin_req:close:{request_id}"),
        ],
        [
            InlineKeyboardButton("🔗 View in Chat", url=f"https://t.me/c/{str(chat.id)[4:]}/{message.message_id}" if not chat.username else None),
        ]
    ])

    # If private group, remove the View in Chat button (we already have the link above)
    if not chat.username:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📝 Responding", callback_data=f"admin_req:responding:{request_id}"),
                InlineKeyboardButton("✅ Close", callback_data=f"admin_req:close:{request_id}"),
            ]
        ])

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        notified_count = 0

        for admin in admins:
            if admin.user.is_bot:
                continue

            try:
                await context.bot.send_message(
                    chat_id=admin.user.id,
                    text=admin_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                notified_count += 1
            except Exception as e:
                # User might have blocked the bot or disabled DMs
                log.debug(f"[ADMIN_REQ] Could not notify admin {admin.user.id} | error={e}")

        log.info(
            f"[ADMIN_REQ] Notified {notified_count}/{len(admins)-1} admins "
            f"for request #{request_id}"
        )
    except Exception as e:
        log.error(f"[ADMIN_REQ] Failed to notify admins | chat={chat.id} | error={e}")


async def cmd_admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /admin_requests
    Admins only - show open admin requests for the group.
    """
    if not await is_admin(update, context):
        await update.effective_message.reply_text("❌ This command is for admins only.")
        return

    chat = update.effective_chat
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    if not db:
        await update.effective_message.reply_text("⚠️ Admin request system unavailable.")
        return

    open_requests = await db_admin_req.get_open_requests(db, chat.id)

    if not open_requests:
        await update.effective_message.reply_text(
            "✅ <b>No open admin requests</b>\n\nEverything is quiet!",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [f"📋 <b>Open Admin Requests ({len(open_requests)})</b>\n"]
    for req in open_requests[:10]:
        ts = req["created_at"].strftime("%m-%d %H:%M") if req["created_at"] else "?"
        user_id = req["user_id"]
        msg_preview = (req["message_text"] or "No message")[:60]
        lines.append(
            f"<b>#{req['id']}</b> — <code>{user_id}</code>\n"
            f"  <i>{msg_preview}</i>\n"
            f"  <i>📅 {ts}</i>"
        )

    if len(open_requests) > 10:
        lines.append(f"\n<i>…and {len(open_requests) - 10} more pending requests.</i>")

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


async def cmd_admin_req_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /admin_req_stats
    Admins only - show statistics about admin requests.
    """
    if not await is_admin(update, context):
        await update.effective_message.reply_text("❌ This command is for admins only.")
        return

    chat = update.effective_chat
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    if not db:
        await update.effective_message.reply_text("⚠️ Admin request system unavailable.")
        return

    stats = await db_admin_req.get_group_request_stats(db, chat.id)

    text = (
        f"📊 <b>Admin Request Statistics</b>\n\n"
        f"📝 <b>Total Requests:</b> {stats['total']}\n"
        f"🔓 <b>Open:</b> {stats['open']}\n"
        f"✅ <b>Closed:</b> {stats['closed']}\n"
    )

    if stats['avg_response_minutes'] > 0:
        text += f"⏱️ <b>Avg Response Time:</b> {stats['avg_response_minutes']} min\n"

    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_set_admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /set_admin_requests [on|off] [rate_limit] [rate_period]
    Admins only - configure admin request settings.

    Examples:
      /set_admin_requests on                - Enable feature
      /set_admin_requests off               - Disable feature
      /set_admin_requests on 5 30           - Enable with 5 requests per 30 min
    """
    if not await is_admin(update, context):
        await update.effective_message.reply_text("❌ This command is for admins only.")
        return

    chat = update.effective_chat
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    if not db or not context.args:
        # Show current settings
        try:
            enabled = await db_admin_req.get_group_setting(db, chat.id, "admin_requests_enabled")
            rate_limit = await db_admin_req.get_group_setting(db, chat.id, "admin_requests_rate_limit")
            rate_period = await db_admin_req.get_group_setting(db, chat.id, "admin_requests_rate_period")
        except Exception:
            enabled = True
            rate_limit = 3
            rate_period = 3600

        period_mins = rate_period // 60
        await update.effective_message.reply_text(
            f"⚙️ <b>Admin Request Settings</b>\n\n"
            f"🔘 <b>Status:</b> {'✅ Enabled' if enabled else '❌ Disabled'}\n"
            f"🔢 <b>Rate Limit:</b> {rate_limit} requests per {period_mins} minutes\n\n"
            f"<i>Usage:</i>\n"
            f"<code>/set_admin_requests on [limit] [period_min]</code>\n"
            f"<code>/set_admin_requests off</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Parse arguments
    action = context.args[0].lower()

    if action in ["off", "disable", "false"]:
        await db_admin_req.set_group_setting(db, chat.id, "admin_requests_enabled", False)
        await update.effective_message.reply_text(
            "❌ <b>Admin requests disabled</b>\n\n"
            "Users can still use /report to flag issues.",
            parse_mode=ParseMode.HTML,
        )
        return

    if action in ["on", "enable", "true"]:
        rate_limit = int(context.args[1]) if len(context.args) > 1 else 3
        rate_period = int(context.args[2]) * 60 if len(context.args) > 2 else 3600  # Convert minutes to seconds

        # Validate
        rate_limit = max(1, min(rate_limit, 20))  # Between 1 and 20
        rate_period = max(60, min(rate_period, 86400))  # Between 1 min and 24 hours

        await db_admin_req.set_group_setting(db, chat.id, "admin_requests_enabled", True)
        await db_admin_req.set_group_setting(db, chat.id, "admin_requests_rate_limit", rate_limit)
        await db_admin_req.set_group_setting(db, chat.id, "admin_requests_rate_period", rate_period)

        period_mins = rate_period // 60
        await update.effective_message.reply_text(
            f"✅ <b>Admin requests enabled</b>\n\n"
            f"🔢 <b>Rate Limit:</b> {rate_limit} requests per {period_mins} minutes",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.effective_message.reply_text(
        "⚠️ Invalid action. Use <code>/set_admin_requests</code> to see usage.",
        parse_mode=ParseMode.HTML,
    )


async def admin_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle callback queries from admin request notifications.
    Actions: responding, close
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, action, request_id_str = parts
    try:
        request_id = int(request_id_str)
    except ValueError:
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    admin = query.from_user

    if action == "responding":
        success = await db_admin_req.update_request_status(
            pool=db,
            request_id=request_id,
            status="responding",
            responded_by=admin.id,
        )

        if success:
            await query.edit_message_text(
                query.message.text + f"\n\n📝 <b>Responding:</b> @{admin.username or admin.first_name}",
                parse_mode=ParseMode.HTML,
            )
            log.info(
                f"[ADMIN_REQ] Responding status | request_id={request_id} "
                f"by={admin.id}"
            )
        else:
            await query.edit_message_text(
                query.message.text + "\n\n⚠️ Request not found.",
                parse_mode=ParseMode.HTML,
            )

    elif action == "close":
        success = await db_admin_req.update_request_status(
            pool=db,
            request_id=request_id,
            status="closed",
            responded_by=admin.id,
        )

        if success:
            emoji = "✅"
            await query.edit_message_text(
                query.message.text + f"\n\n{emoji} <b>Closed by:</b> @{admin.username or admin.first_name}",
                parse_mode=ParseMode.HTML,
            )
            log.info(
                f"[ADMIN_REQ] Closed | request_id={request_id} "
                f"by={admin.id}"
            )
        else:
            await query.edit_message_text(
                query.message.text + "\n\n⚠️ Request not found.",
                parse_mode=ParseMode.HTML,
            )


# Handler registration
admin_request_handlers = [
    # Message handler for @admins mentions
    # This is registered separately in factory.py with proper filter
]

# Command handlers
admin_request_command_handlers = [
    CommandHandler("admin_requests", cmd_admin_requests),
    CommandHandler("admin_req_stats", cmd_admin_req_stats),
    CommandHandler("set_admin_requests", cmd_set_admin_requests),
    CallbackQueryHandler(admin_request_callback, pattern=r"^admin_req:(responding|close):\d+$"),
]
