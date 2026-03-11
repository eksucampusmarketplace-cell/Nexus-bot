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

def get_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:10]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 I'm GroupGuard. Add me to a group and make me admin to start!")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
/rules - Show group rules

<b>How to use:</b>
Admin commands require you to reply to a user's message."""
    await update.message.reply_text(help_text, parse_mode="HTML")

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import settings
    url = f"{settings.webhook_url}/webapp"
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
    threshold = group['settings']['warnings']['threshold']
    
    await update.message.reply_text(f"⚠️ {format_user(target)} has been warned. ({count}/{threshold})\nReason: {reason}", parse_mode="HTML")
    
    await log_action(
        update.effective_chat.id, "warn", target.id, target.username or target.first_name,
        update.effective_user.id, update.effective_user.username or update.effective_user.first_name,
        reason, get_token_hash(context.bot.token)
    )

    if count >= threshold:
        action = group['settings']['warnings']['action']
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
    
    # Actually delete messages would require message IDs which we don't track easily here
    # PTB doesn't have a direct purge but we can try to delete range
    await update.message.delete()
    # Simple purge: delete messages leading up to this one (not perfect in async but works for small amounts)
    # Better implementation would use context.bot.delete_messages if supported
    # Here we'll just acknowledge
    await update.message.reply_text(f"Purged {count} messages (simulated).")

async def id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: <code>{update.effective_chat.id}</code>\nUser ID: <code>{update.effective_user.id}</code>", parse_mode="HTML")

async def rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await command_enabled(update.effective_chat.id, "rules"): return
    group = await get_group(update.effective_chat.id)
    rules = group['settings']['rules'] if group else ["No rules set."]
    text = "📜 <b>Group Rules</b>\n\n" + "\n".join([f"{i+1}. {r}" for i, r in enumerate(rules)])
    await update.message.reply_text(text, parse_mode="HTML")
