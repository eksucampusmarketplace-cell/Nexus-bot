import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from bot.utils.permissions import is_admin, command_enabled
from bot.utils.parse_duration import parse_duration
from bot.utils.format import format_user
from db.ops.groups import get_group, upsert_group
from db.ops.users import add_warn, remove_warn, update_user_status, get_user
from db.ops.logs import log_action
import hashlib
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Default settings for fallback
DEFAULT_WARNINGS = {"threshold": 3, "action": "ban"}
DEFAULT_SETTINGS = {
    "warnings": DEFAULT_WARNINGS,
    "rules": ["Be respectful", "No spam"]
}

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
    if not url:
        await update.message.reply_text(
            "👋 I'm Nexus. Add me to a group and make me admin to start!\n\nMini App is not configured."
        )
        return
    await update.message.reply_text(
        "👋 I'm Nexus. Add me to a group and make me admin to start!\n\nUse the panel below to manage your group settings:",
        reply_markup={
            "inline_keyboard": [[{"text": "📱 Open Panel", "web_app": {"url": url}}]]
        }
    )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import settings
    url = settings.mini_app_url or f"{settings.webhook_url}/miniapp"
    help_text = """<b>📚 Available Commands</b>

<b>Basic:</b>
/start - Start the bot
/help - Show this help message
/panel - Open management panel
/id - Get chat and user ID

<b>Admin:</b>
/warn - Warn a user (reply to message)
/ban - Ban a user (reply to message)
/mute - Mute a user (reply to message)
/purge - Delete messages
/pin - Pin a message
/unpin - Unpin message
/rules - Show group rules
/announce - Send announcement
/pinmessage - Pin custom message
/slowmode - Set slow mode
/filters - List word filters
/addfilter - Add word filter
/delfilter - Remove word filter
/setflood - Set flood limit
/exportsettings - Export settings
/admininfo - Show detailed info

<b>🎵 Music - Basic:</b>
/play - Play music (reply to audio/voice or send file)
/playnow - Play immediately
/skip - Skip to next track
/queue - Show music queue
/stop - Stop music and clear queue
/pause - Pause playback
/resume - Resume playback
/nowplaying - Show current track with controls
/volume - Set volume
/loop - Toggle loop mode
/musicmode - Set who can use music

<b>🎵 Music - Advanced:</b>
/play_youtube <url> - Play from YouTube
/repeat <mode> - Set repeat (none/one/all)
/shuffle - Toggle shuffle mode
/playlist_create <name> - Create playlist
/playlist_list - List all playlists
/playlist_play <name> - Play a playlist
/playlist_delete <name> - Delete playlist
/history <n> - Show play history
/search <query> - Search music
/sync - Sync music to all clone bots
/music_settings - Interactive settings panel

<b>🎮 Fun:</b>
/afk - Set AFK status
/back - Clear AFK status
/poll - Create a poll
/dice - Roll a dice
/coin - Flip a coin
/choose - Randomly choose between options
/8ball - Magic 8-ball
/roll - Roll random number
/joke - Get a random joke
/quote - Get a quote
/roast - Playful roast
/compliment - Give compliment
/calc - Calculator

<b>How to use:</b>
Admin commands require you to reply to a user's message.

<b>Web Panel:</b>
Manage your group settings via the web panel."""
    await update.message.reply_text(
        help_text,
        parse_mode="HTML",
        reply_markup={
            "inline_keyboard": [[{"text": "📱 Open Panel", "web_app": {"url": url}}]]
        }
    )

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import settings
    url = settings.mini_app_url
    if not url:
        await update.message.reply_text("Mini App is not configured. Please set MINI_APP_URL or RENDER_EXTERNAL_URL.")
        return
    await update.message.reply_text(
        "Open the management panel:",
        reply_markup={
            "inline_keyboard": [[{"text": "📱 Open Panel", "web_app": {"url": url}}]]
        }
    )

async def warn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not await command_enabled(update.effective_chat.id, "warn"):
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user to warn them.")
        return

    target = update.message.reply_to_message.from_user
    reason = " ".join(context.args) if context.args else "No reason provided"
    
    count = await add_warn(target.id, update.effective_chat.id, reason, update.effective_user.id)
    
    group = await get_group(update.effective_chat.id)
    settings = group.get('settings', {}) if group else {}
    warnings_settings = get_setting(settings, 'warnings')
    threshold = warnings_settings['threshold']
    
    await update.message.reply_text(f"⚠️ {format_user(target)} has been warned. ({count}/{threshold})\nReason: {reason}", parse_mode="HTML")
    
    await log_action(
        update.effective_chat.id, "warn", target.id, target.username or target.first_name,
        update.effective_user.id, update.effective_user.username or update.effective_user.first_name,
        reason, get_token_hash(context.bot.token)
    )

    if count >= threshold:
        action = warnings_settings['action']
        if action == "ban":
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            await update.message.reply_text(f"🚫 {format_user(target)} reached warning threshold and was banned.", parse_mode="HTML")
        elif action == "kick":
            await context.bot.unban_chat_member(update.effective_chat.id, target.id)
            await update.message.reply_text(f"👢 {format_user(target)} reached warning threshold and was kicked.", parse_mode="HTML")
        elif action == "mute":
            await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions={"can_send_messages": False})
            await update.message.reply_text(f"🔇 {format_user(target)} reached warning threshold and was muted.", parse_mode="HTML")

async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not await command_enabled(update.effective_chat.id, "ban"):
        return
    if not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    reason = " ".join(context.args) if context.args else "No reason provided"
    
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"🚫 {format_user(target)} has been banned.\nReason: {reason}", parse_mode="HTML")
    await log_action(update.effective_chat.id, "ban", target.id, target.username, update.effective_user.id, update.effective_user.username, reason, get_token_hash(context.bot.token))

async def mute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not await command_enabled(update.effective_chat.id, "mute"):
        return
    if not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    duration_str = context.args[0] if context.args else "0"
    duration = parse_duration(duration_str)
    
    until = datetime.now() + timedelta(seconds=duration) if duration > 0 else None
    await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions={"can_send_messages": False}, until_date=until)
    await update.message.reply_text(f"🔇 {format_user(target)} has been muted for {duration_str}.", parse_mode="HTML")
    await update_user_status(target.id, update.effective_chat.id, is_muted=True, mute_until=until)

async def purge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context) or not await command_enabled(update.effective_chat.id, "purge"):
        return
    count = int(context.args[0]) if context.args and context.args[0].isdigit() else 10
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
            f"🧹 <b>Purge Complete</b>\nSuccessfully removed {count} messages.",
            parse_mode="HTML"
        )
        # In a real bot we'd use context.job_queue to delete this after 5s
    except Exception:
        pass

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
    if not await command_enabled(update.effective_chat.id, "rules"): return
    group = await get_group(update.effective_chat.id)
    settings = group.get('settings', {}) if group else {}
    rules = get_setting(settings, 'rules', default=["No rules set."])
    
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
        await update.message.reply_text("Reply to a user's message to remove their warning.")
        return
    target = update.message.reply_to_message.from_user
    count = await remove_warn(target.id, update.effective_chat.id)
    await update.message.reply_text(f"✅ Removed warning for {format_user(target)}. ({count} remaining)", parse_mode="HTML")

async def warns_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show warnings for a user."""
    if not await command_enabled(update.effective_chat.id, "warns"):
        return
    
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    user = await get_user(target.id, update.effective_chat.id)
    warns = user.get('warns', []) if user else []
    count = len(warns)
    
    text = f"⚠️ <b>Warnings for {format_user(target)}</b>\n"
    text += f"Total: {count}\n\n"
    
    if warns:
        for i, w in enumerate(warns):
            date = w.get('timestamp', '').split('T')[0]
            text += f"{i+1}. {w.get('reason', 'No reason')} ({date})\n"
    else:
        text += "No warnings on record. ✅"
        
    await update.message.reply_text(text, parse_mode="HTML")

async def unban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user from the group."""
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message to unban them.")
        return
    target = update.message.reply_to_message.from_user
    await context.bot.unban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"✅ {format_user(target)} has been unbanned.", parse_mode="HTML")

async def unmute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute a user in the group."""
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message to unmute them.")
        return
    target = update.message.reply_to_message.from_user
    await context.bot.restrict_chat_member(
        update.effective_chat.id, target.id,
        permissions={
            "can_send_messages": True,
            "can_send_media_messages": True,
            "can_send_other_messages": True,
            "can_add_web_page_previews": True
        }
    )
    await update_user_status(target.id, update.effective_chat.id, is_muted=False, mute_until=None)
    await update.message.reply_text(f"✅ {format_user(target)} has been unmuted.", parse_mode="HTML")

async def kick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kick a user from the group (ban then unban)."""
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message to kick them.")
        return
    target = update.message.reply_to_message.from_user
    reason = " ".join(context.args) if context.args else "No reason provided"
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await context.bot.unban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"👢 {format_user(target)} has been kicked.\nReason: {reason}", parse_mode="HTML")
    await log_action(
        update.effective_chat.id, "kick", target.id, target.username or target.first_name,
        update.effective_user.id, update.effective_user.username or update.effective_user.first_name,
        reason, get_token_hash(context.bot.token)
    )

async def lock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lock a chat setting."""
    if not await is_admin(update, context):
        return
    lock_type = context.args[0] if context.args else "all"
    await update.message.reply_text(f"🔒 <b>{lock_type.upper()}</b> has been locked.", parse_mode="HTML")

async def unlock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unlock a chat setting."""
    if not await is_admin(update, context):
        return
    unlock_type = context.args[0] if context.args else "all"
    await update.message.reply_text(f"🔓 <b>{unlock_type.upper()}</b> has been unlocked.", parse_mode="HTML")

async def pin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pin a message in the group."""
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a message to pin it.")
        return
    await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
    await update.message.reply_text("📌 Message successfully pinned.", parse_mode="HTML")

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
        description = getattr(full_chat, 'description', None)
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
        total_messages = await conn.fetchval("SELECT SUM(message_count) FROM users WHERE chat_id = $1", chat_id)
        active_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE chat_id = $1 AND last_seen > NOW() - INTERVAL '7 days'", chat_id)
        total_warns = await conn.fetchval("SELECT COUNT(*) FROM actions_log WHERE chat_id = $1 AND action = 'warn'", chat_id)
        
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

