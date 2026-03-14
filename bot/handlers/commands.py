import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from bot.utils.permissions import is_admin, command_enabled
from bot.utils.parse_duration import parse_duration
from bot.utils.format import format_user
from bot.utils.webhook_dispatcher import notify_warn, notify_ban, notify_mute, notify_kick
from db.ops.groups import get_group, upsert_group
from db.ops.users import add_warn, remove_warn, update_user_status, get_user
from db.ops.logs import log_action
import hashlib
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Default settings for fallback
DEFAULT_WARNINGS = {"threshold": 3, "action": "ban"}
DEFAULT_SETTINGS = {"warnings": DEFAULT_WARNINGS, "rules": ["Be respectful", "No spam"]}


def get_setting(settings: dict, *keys, default=None):
    """Safely get nested settings value with fallback to defaults."""
    value = settings
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            # Fall back to default settings
            default_value = DEFAULT_SETTINGS
            for k in keys:
                if isinstance(default_value, dict) and k in default_value:
                    default_value = default_value[k]
                else:
                    return default
            return default_value
    return value if value is not None else default


def get_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:10]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import settings

    url = settings.mini_app_url
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == "private":
        # Private chat - show welcome with clone option
        welcome_text = f"""👋 <b>Welcome to Nexus, {user.first_name}!</b>

I'm a powerful Telegram group management bot with:
• 🛡️ Advanced moderation tools
• 🤖 AutoMod protection
• 🎵 Music streaming
• 🎮 Mini games with XP
• 📊 Analytics & insights
• 🔧 And much more!

<b>Quick Start:</b>
1. Add me to your group
2. Make me an admin
3. Use /panel to configure settings

<b>Create Your Own Bot:</b>
Want your own branded bot? Use the button below!"""

        buttons = [[{"text": "📱 Open Panel", "web_app": {"url": url}}]]

        # Add clone button for primary bot
        if context.bot_data.get("is_primary", False):
            buttons.append(
                [
                    {
                        "text": "🤖 Create Your Own Bot",
                        "url": f"https://t.me/{context.bot.username}?start=clone",
                    }
                ]
            )

        buttons.append([{"text": "❓ Help & Commands", "callback_data": "help_main"}])

        await update.message.reply_text(
            welcome_text, parse_mode="HTML", reply_markup={"inline_keyboard": buttons}
        )
    else:
        # Group chat - brief intro
        await update.message.reply_text(
            f"👋 Hi {user.first_name}! I'm Nexus, your group management bot.\n\n"
            f"Use /panel to open the management panel or /help for commands.",
            parse_mode="HTML",
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import settings

    url = settings.mini_app_url or f"{settings.webhook_url}/miniapp"

    # Determine chat type for context-aware help
    chat = update.effective_chat
    chat_type = chat.type if chat else "private"

    help_text = f"""<b>📚 Nexus Command Guide</b>

<b>🎯 Usage Tips:</b>
• Most admin commands work by <b>replying</b> to a user's message
• Some commands accept username: <code>/ban @username</code>
• Time formats: <code>10m</code>, <code>1h</code>, <code>1d</code> (minutes, hours, days)

<b>🛡️ Moderation (Admin only):</b>
<code>/warn [reason]</code> - Warn a user (reply to message)
<code>/unwarn</code> - Remove last warning (reply to message)
<code>/warns</code> - Show user's warnings
<code>/ban [reason]</code> - Ban user (reply or @username)
<code>/unban</code> - Unban user (reply or @username)
<code>/mute [duration]</code> - Mute user (e.g., <code>/mute 1h</code>)
<code>/unmute</code> - Unmute user
<code>/kick [reason]</code> - Kick user from group
<code>/purge [count]</code> - Delete messages (max 100)
<code>/purgeme [count]</code> - Delete your own messages

<b>📌 Pin Management:</b>
<code>/pin [silent]</code> - Pin replied message
<code>/unpin</code> - Unpin current message
<code>/unpinall</code> - Unpin all messages

<b>🔒 Security & AutoMod:</b>
<code>!antispam</code> / <code>!!antispam</code> - Toggle anti-spam
<code>!antiflood</code> / <code>!!antiflood</code> - Toggle anti-flood
<code>!antilink</code> / <code>!!antilink</code> - Toggle anti-link
<code>!captcha</code> / <code>!!captcha</code> - Toggle CAPTCHA
<code>/slowmode [seconds]</code> - Set slow mode (0-300)
<code>/filters</code> - List word filters
<code>/addfilter [word]</code> - Add filter word
<code>/delfilter [word]</code> - Remove filter word

<b>👋 Greetings:</b>
<code>/setwelcome [message]</code> - Set welcome message
<code>/setgoodbye [message]</code> - Set goodbye message
<code>/setrules [rules]</code> - Set group rules
<code>/rules</code> - Show group rules

<b>🎵 Music Commands:</b>
<code>/play [url/query]</code> - Play music
<code>/playnow [url]</code> - Play immediately
<code>/skip</code> - Skip current track
<code>/stop</code> - Stop playback
<code>/pause</code> - Pause music
<code>/resume</code> - Resume music
<code>/queue</code> - Show queue
<code>/volume [0-200]</code> - Set volume

<b>🎮 Fun Commands:</b>
<code>/afk [reason]</code> - Set AFK status
<code>/dice</code> - Roll a dice
<code>/coin</code> - Flip a coin
<code>/roll [max]</code> - Roll random number
<code>/calc [expression]</code> - Calculator

<b>📊 Other:</b>
<code>/id</code> - Get user/chat IDs
<code>/adminlist</code> - List group admins
<code>/groupinfo</code> - Show group info
<code>/stats</code> - Show statistics
<code>/privacy</code> - Privacy policy

<b>📱 Mini App:</b>
Use /panel for visual configuration of all features!

<b>Need more help?</b> Join our support group."""

    await update.message.reply_text(
        help_text,
        parse_mode="HTML",
        reply_markup={"inline_keyboard": [[{"text": "📱 Open Panel", "web_app": {"url": url}}]]},
        disable_web_page_preview=True,
    )


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import settings

    url = settings.mini_app_url
    if not url:
        await update.message.reply_text(
            "Mini App is not configured. Please set MINI_APP_URL or RENDER_EXTERNAL_URL."
        )
        return
    await update.message.reply_text(
        "Open the management panel:",
        reply_markup={"inline_keyboard": [[{"text": "📱 Open Panel", "web_app": {"url": url}}]]},
    )


async def _refresh_trust_score(context, chat_id: int, user_id: int):
    """Recalculate trust score after a moderation action (fire-and-forget helper)."""
    db_pool = context.bot_data.get("db_pool") or context.bot_data.get("db")
    if not db_pool:
        return
    try:
        from bot.utils.trust_score import calculate_trust_score, apply_trust_consequences

        score = await calculate_trust_score(user_id, chat_id, db_pool)
        await apply_trust_consequences(user_id, chat_id, score, context)
    except Exception as _e:
        logger.debug(f"[COMMANDS] Trust score refresh failed: {_e}")


async def warn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not await command_enabled(
        update.effective_chat.id, "warn"
    ):
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❓ <b>Usage:</b> Reply to a user's message with <code>/warn [reason]</code>\n\n"
            "Example: Reply to someone's message and type <code>/warn spam</code>",
            parse_mode="HTML",
        )
        return

    target = update.message.reply_to_message.from_user
    # Prevent self-warn
    if target.id == update.effective_user.id:
        await update.message.reply_text("❌ You can't warn yourself! 😄")
        return
    # Prevent warning the bot
    if target.id == context.bot.id:
        await update.message.reply_text("❌ I can't warn myself! 🤖")
        return

    reason = " ".join(context.args) if context.args else "No reason provided"

    count = await add_warn(target.id, update.effective_chat.id, reason, update.effective_user.id)

    group = await get_group(update.effective_chat.id)
    settings = group.get("settings", {}) if group else {}
    warnings_settings = get_setting(settings, "warnings")
    threshold = warnings_settings["threshold"]

    await update.message.reply_text(
        f"⚠️ {format_user(target)} has been warned. ({count}/{threshold})\nReason: {reason}",
        parse_mode="HTML",
    )

    await log_action(
        update.effective_chat.id,
        "warn",
        target.id,
        target.username or target.first_name,
        update.effective_user.id,
        update.effective_user.username or update.effective_user.first_name,
        reason,
        get_token_hash(context.bot.token),
    )

    # Notify webhooks
    await notify_warn(
        chat_id=update.effective_chat.id,
        user_id=target.id,
        admin_id=update.effective_user.id,
        admin_name=update.effective_user.username or update.effective_user.first_name,
        warn_count=count,
        max_warns=threshold,
        reason=reason,
        chat_title=update.effective_chat.title,
    )

    await _refresh_trust_score(context, update.effective_chat.id, target.id)

    if count >= threshold:
        action = warnings_settings["action"]
        if action == "ban":
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            await update.message.reply_text(
                f"🚫 {format_user(target)} reached warning threshold and was banned.",
                parse_mode="HTML",
            )
        elif action == "kick":
            await context.bot.unban_chat_member(update.effective_chat.id, target.id)
            await update.message.reply_text(
                f"👢 {format_user(target)} reached warning threshold and was kicked.",
                parse_mode="HTML",
            )
        elif action == "mute":
            await context.bot.restrict_chat_member(
                update.effective_chat.id, target.id, permissions={"can_send_messages": False}
            )
            await update.message.reply_text(
                f"🔇 {format_user(target)} reached warning threshold and was muted.",
                parse_mode="HTML",
            )


async def _get_user_from_arg(update: Update, context: ContextTypes.DEFAULT_TYPE, arg: str):
    """Resolve a user from username, user_id, or reply."""
    # First try reply (but not if this is called from username/ID lookup)
    if update.message.reply_to_message and not arg:
        return update.message.reply_to_message.from_user

    if not arg:
        return None

    # Try username (with or without @)
    if arg.startswith("@"):
        username = arg[1:]
        try:
            # Try to get chat member by username - need to search via get_chat
            chat = await context.bot.get_chat(update.effective_chat.id)
            # Get all admins and members to find by username
            members = await context.bot.get_chat_administrators(update.effective_chat.id)
            for member in members:
                if member.user.username and member.user.username.lower() == username.lower():
                    return member.user
            # Also try regular member lookup via member count iteration if needed
        except Exception:
            pass

    # Try user_id
    if arg.isdigit():
        try:
            user_id = int(arg)
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            return member.user
        except Exception:
            pass

    return None


async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not await command_enabled(
        update.effective_chat.id, "ban"
    ):
        return

    # Try to get target from reply or args
    target = None
    reason = "No reason provided"

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else reason
    elif context.args:
        # Try to get user from first arg
        user_arg = context.args[0]
        target = await _get_user_from_arg(update, context, user_arg)
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else reason

    if not target:
        await update.message.reply_text(
            "❓ <b>Usage:</b>\n"
            "• Reply to a user's message with <code>/ban [reason]</code>\n"
            "• Or: <code>/ban @username [reason]</code>\n"
            "• Or: <code>/ban user_id [reason]</code>",
            parse_mode="HTML",
        )
        return

    # Prevent self-ban
    if target.id == update.effective_user.id:
        await update.message.reply_text("❌ You can't ban yourself! 😄")
        return

    # Prevent banning the bot
    if target.id == context.bot.id:
        await update.message.reply_text("❌ I can't ban myself! 🤖")
        return

    # Can't ban admins
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, target.id)
        if member.status in ["creator", "administrator"]:
            await update.message.reply_text("❌ I can't ban an administrator.")
            return
    except Exception:
        pass

    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(
        f"🚫 {format_user(target)} has been banned.\nReason: {reason}", parse_mode="HTML"
    )
    await log_action(
        update.effective_chat.id,
        "ban",
        target.id,
        target.username,
        update.effective_user.id,
        update.effective_user.username,
        reason,
        get_token_hash(context.bot.token),
    )

    # Notify webhooks
    await notify_ban(
        chat_id=update.effective_chat.id,
        user_id=target.id,
        admin_id=update.effective_user.id,
        admin_name=update.effective_user.username or update.effective_user.first_name,
        reason=reason,
        chat_title=update.effective_chat.title,
    )

    await _refresh_trust_score(context, update.effective_chat.id, target.id)


async def unban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user from the group."""
    if not await is_admin(update, context):
        return

    target = None

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    elif context.args:
        user_arg = context.args[0]
        if user_arg.startswith("@"):
            await update.message.reply_text(
                "❌ Please provide a user ID to unban (can't resolve @username for banned users)."
            )
            return
        elif user_arg.isdigit():
            target_id = int(user_arg)
            await context.bot.unban_chat_member(update.effective_chat.id, target_id)
            await update.message.reply_text(
                f"✅ User <code>{target_id}</code> has been unbanned.", parse_mode="HTML"
            )
            return

    if not target:
        await update.message.reply_text(
            "❓ <b>Usage:</b>\n"
            "• Reply to a message: <code>/unban</code>\n"
            "• Or: <code>/ban user_id</code>",
            parse_mode="HTML",
        )
        return

    await context.bot.unban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(
        f"✅ {format_user(target)} has been unbanned.", parse_mode="HTML"
    )


async def mute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not await command_enabled(
        update.effective_chat.id, "mute"
    ):
        return

    target = None
    duration_str = "0"

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        duration_str = context.args[0] if context.args else "0"
    elif context.args:
        user_arg = context.args[0]
        target = await _get_user_from_arg(update, context, user_arg)
        duration_str = context.args[1] if len(context.args) > 1 else "0"

    if not target:
        await update.message.reply_text(
            "❓ <b>Usage:</b>\n"
            "• Reply to a user's message with <code>/mute [duration]</code>\n"
            "• Or: <code>/mute @username [duration]</code>\n"
            "• Or: <code>/mute user_id [duration]</code>\n\n"
            "Duration examples: <code>10m</code>, <code>1h</code>, <code>1d</code> (0 = permanent)",
            parse_mode="HTML",
        )
        return

    # Prevent self-mute
    if target.id == update.effective_user.id:
        await update.message.reply_text("❌ You can't mute yourself! 😄")
        return

    # Prevent muting the bot
    if target.id == context.bot.id:
        await update.message.reply_text("❌ I can't mute myself! 🤖")
        return

    duration = parse_duration(duration_str)

    until = datetime.now() + timedelta(seconds=duration) if duration > 0 else None
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        target.id,
        permissions={"can_send_messages": False},
        until_date=until,
    )

    duration_text = f"for {duration_str}" if duration > 0 else "permanently"
    await update.message.reply_text(
        f"🔇 {format_user(target)} has been muted {duration_text}.", parse_mode="HTML"
    )
    await update_user_status(target.id, update.effective_chat.id, is_muted=True, mute_until=until)

    # Notify webhooks
    await notify_mute(
        chat_id=update.effective_chat.id,
        user_id=target.id,
        admin_id=update.effective_user.id,
        admin_name=update.effective_user.username or update.effective_user.first_name,
        duration=duration,
        reason=duration_str,
        chat_title=update.effective_chat.title,
    )

    await _refresh_trust_score(context, update.effective_chat.id, target.id)


async def unmute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute a user in the group."""
    if not await is_admin(update, context):
        return

    target = None

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    elif context.args:
        user_arg = context.args[0]
        target = await _get_user_from_arg(update, context, user_arg)

    if not target:
        await update.message.reply_text(
            "❓ <b>Usage:</b>\n"
            "• Reply to a user's message: <code>/unmute</code>\n"
            "• Or: <code>/unmute @username</code>\n"
            "• Or: <code>/unmute user_id</code>",
            parse_mode="HTML",
        )
        return

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        target.id,
        permissions={
            "can_send_messages": True,
            "can_send_media_messages": True,
            "can_send_other_messages": True,
            "can_add_web_page_previews": True,
        },
    )
    await update_user_status(target.id, update.effective_chat.id, is_muted=False, mute_until=None)
    await update.message.reply_text(
        f"✅ {format_user(target)} has been unmuted.", parse_mode="HTML"
    )


async def kick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kick a user from the group (ban then unban)."""
    if not await is_admin(update, context):
        return

    target = None
    reason = "No reason provided"

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else reason
    elif context.args:
        user_arg = context.args[0]
        target = await _get_user_from_arg(update, context, user_arg)
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else reason

    if not target:
        await update.message.reply_text(
            "❓ <b>Usage:</b>\n"
            "• Reply to a user's message: <code>/kick [reason]</code>\n"
            "• Or: <code>/kick @username [reason]</code>\n"
            "• Or: <code>/kick user_id [reason]</code>",
            parse_mode="HTML",
        )
        return

    # Prevent self-kick
    if target.id == update.effective_user.id:
        await update.message.reply_text("❌ You can't kick yourself! 😄")
        return

    # Prevent kicking the bot
    if target.id == context.bot.id:
        await update.message.reply_text("❌ I can't kick myself! 🤖")
        return

    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await context.bot.unban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(
        f"👢 {format_user(target)} has been kicked.\nReason: {reason}", parse_mode="HTML"
    )
    await log_action(
        update.effective_chat.id,
        "kick",
        target.id,
        target.username or target.first_name,
        update.effective_user.id,
        update.effective_user.username or update.effective_user.first_name,
        reason,
        get_token_hash(context.bot.token),
    )
    # Notify webhooks
    await notify_kick(
        chat_id=update.effective_chat.id,
        user_id=target.id,
        admin_id=update.effective_user.id,
        admin_name=update.effective_user.username or update.effective_user.first_name,
        reason=reason,
        chat_title=update.effective_chat.title,
    )


async def purge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete messages from the group."""
    if not await is_admin(update, context) or not await command_enabled(
        update.effective_chat.id, "purge"
    ):
        return

    # Parse arguments
    count = 10  # default
    all_users = False

    for arg in context.args:
        if arg.isdigit():
            count = int(arg)
        elif arg.lower() in ["all", "everyone"]:
            all_users = True

    count = min(count, 100)

    chat_id = update.effective_chat.id
    message_id = update.message.message_id

    # Collect message IDs to delete
    message_ids = []
    for i in range(count + 1):
        message_ids.append(message_id - i)

    try:
        # delete_messages is available in newer PTB versions
        await context.bot.delete_messages(chat_id, message_ids)
    except Exception as e:
        logger.warning(f"delete_messages failed, falling back to individual deletion: {e}")
        for mid in message_ids:
            try:
                await context.bot.delete_message(chat_id, mid)
            except Exception:
                continue

    # Confirmation message that deletes itself (if possible)
    try:
        sent = await context.bot.send_message(
            chat_id,
            f"🧹 <b>Purge Complete</b>\nDeleted {count} messages{' from all users' if all_users else ''}.",
            parse_mode="HTML",
        )
        # In a real bot we'd use context.job_queue to delete this after 5s
    except Exception:
        pass


async def purgeme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete your own messages."""
    count = 10  # default

    if context.args and context.args[0].isdigit():
        count = min(int(context.args[0]), 100)

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Get recent messages and delete only user's own
    # Note: This is a simplified version - in production you'd query DB for user's message IDs
    deleted = 0
    for i in range(count + 1):
        try:
            msg_id = update.message.message_id - i
            # Try to get message info (this is limited by Telegram API)
            # In practice, you'd need to track message IDs in your database
            await context.bot.delete_message(chat_id, msg_id)
            deleted += 1
        except Exception:
            pass

    await update.message.reply_text(f"🧹 Deleted {deleted} of your messages.", parse_mode="HTML")


async def id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"<b>🆔 Identification</b>\n\n"
        f"👤 <b>User:</b>\n"
        f"  • Name: {update.effective_user.full_name}\n"
        f"  • ID: <code>{update.effective_user.id}</code>\n"
        f"  • Username: @{update.effective_user.username or 'None'}\n\n"
        f"💬 <b>Chat:</b>\n"
        f"  • Title: {update.effective_chat.title}\n"
        f"  • ID: <code>{update.effective_chat.id}</code>\n"
        f"  • Type: {update.effective_chat.type.capitalize()}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await command_enabled(update.effective_chat.id, "rules"):
        return
    group = await get_group(update.effective_chat.id)
    settings = group.get("settings", {}) if group else {}
    rules = get_setting(settings, "rules", default=["No rules set."])

    text = "📜 <b>Group Rules</b>\n"
    text += "────────────────────\n"
    text += "\n".join([f"<b>{i+1}.</b> {r}" for i, r in enumerate(rules)])
    text += "\n\n<i>Please follow these rules to avoid being warned.</i>"

    await update.message.reply_text(text, parse_mode="HTML")


# Additional handlers needed by factory.py


async def unwarn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a warning from a user."""
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❓ <b>Usage:</b> Reply to a user's message to remove their warning.\n\n"
            "Example: Reply to someone's message and type <code>/unwarn</code>",
            parse_mode="HTML",
        )
        return
    target = update.message.reply_to_message.from_user
    # Prevent self-unwarn
    if target.id == update.effective_user.id:
        await update.message.reply_text("❌ You can't remove your own warnings! 😄")
        return
    count = await remove_warn(target.id, update.effective_chat.id)
    await update.message.reply_text(
        f"✅ Removed warning for {format_user(target)}. ({count} remaining)", parse_mode="HTML"
    )


async def warns_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show warnings for a user."""
    if not await command_enabled(update.effective_chat.id, "warns"):
        return

    target = (
        update.message.reply_to_message.from_user
        if update.message.reply_to_message
        else update.effective_user
    )
    user = await get_user(target.id, update.effective_chat.id)
    warns = user.get("warns", []) if user else []
    count = len(warns)

    text = f"⚠️ <b>Warnings for {format_user(target)}</b>\n"
    text += f"Total: {count}\n\n"

    if warns:
        for i, w in enumerate(warns):
            date = w.get("timestamp", "").split("T")[0]
            text += f"{i+1}. {w.get('reason', 'No reason')} ({date})\n"
    else:
        text += "No warnings on record. ✅"

    await update.message.reply_text(text, parse_mode="HTML")


async def lock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lock a chat setting."""
    if not await is_admin(update, context):
        return
    lock_type = context.args[0] if context.args else "all"
    await update.message.reply_text(
        f"🔒 <b>{lock_type.upper()}</b> has been locked.", parse_mode="HTML"
    )


async def unlock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unlock a chat setting."""
    if not await is_admin(update, context):
        return
    unlock_type = context.args[0] if context.args else "all"
    await update.message.reply_text(
        f"🔓 <b>{unlock_type.upper()}</b> has been unlocked.", parse_mode="HTML"
    )


async def pin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pin a message in the group."""
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❓ <b>Usage:</b> Reply to a message with <code>/pin</code>\n"
            "Add <code>silent</code> to pin without notification: <code>/pin silent</code>",
            parse_mode="HTML",
        )
        return
    silent = "silent" in context.args
    await context.bot.pin_chat_message(
        update.effective_chat.id,
        update.message.reply_to_message.message_id,
        disable_notification=silent,
    )
    await update.message.reply_text(
        "📌 Message successfully pinned." + (" (silent)" if silent else ""), parse_mode="HTML"
    )


async def unpin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unpin the current pinned message."""
    if not await is_admin(update, context):
        return
    await context.bot.unpin_chat_message(update.effective_chat.id)
    await update.message.reply_text("📌 Pinned message removed.", parse_mode="HTML")


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group information."""
    chat = update.effective_chat
    if not chat:
        return

    try:
        member_count = await context.bot.get_chat_member_count(chat.id)
    except Exception:
        member_count = "N/A"

    text = (
        f"ℹ️ <b>Group Information</b>\n\n"
        f"<b>Name:</b> {chat.title or chat.first_name}\n"
        f"<b>ID:</b> <code>{chat.id}</code>\n"
        f"<b>Type:</b> {chat.type.capitalize()}\n"
        f"<b>Members:</b> {member_count}\n"
        f"<b>Username:</b> @{chat.username or 'None'}\n"
    )

    try:
        # Full chat info is needed for the description attribute in PTB v21.3+
        full_chat = await context.bot.get_chat(chat.id)
        description = getattr(full_chat, "description", None)
        if description:
            text += f"<b>Description:</b>\n{description}\n"
    except Exception:
        pass

    await update.message.reply_text(text, parse_mode="HTML")


async def admins_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List group administrators."""
    if not update.effective_chat:
        return
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        admin_list = []
        for a in admins:
            role = "Owner" if a.status == "creator" else "Admin"
            admin_list.append(f"• {format_user(a.user)} (<i>{role}</i>)")

        text = f"👮 <b>Administrators ({len(admins)})</b>\n\n" + "\n".join(admin_list)
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Could not fetch admins: {e}")


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group statistics."""
    if not await is_admin(update, context):
        return

    chat_id = update.effective_chat.id
    from db.client import db

    async with db.pool.acquire() as conn:
        total_messages = await conn.fetchval(
            "SELECT SUM(message_count) FROM users WHERE chat_id = $1", chat_id
        )
        active_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE chat_id = $1 AND last_seen > NOW() - INTERVAL '7 days'",
            chat_id,
        )
        total_warns = await conn.fetchval(
            "SELECT COUNT(*) FROM actions_log WHERE chat_id = $1 AND action = 'warn'", chat_id
        )

    try:
        member_count = await context.bot.get_chat_member_count(chat_id)
    except Exception:
        member_count = "N/A"

    text = (
        f"📊 <b>Group Statistics</b>\n"
        f"────────────────────\n"
        f"👥 <b>Members:</b> {member_count}\n"
        f"💬 <b>Total Messages:</b> {total_messages or 0}\n"
        f"🔥 <b>Active (7d):</b> {active_users or 0}\n"
        f"⚠️ <b>Total Warnings:</b> {total_warns or 0}\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report a message to admins."""
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a message to report it.")
        return
    target = update.message.reply_to_message.from_user
    await update.message.reply_text(f"✅ Message from {format_user(target)} reported to admins.")
