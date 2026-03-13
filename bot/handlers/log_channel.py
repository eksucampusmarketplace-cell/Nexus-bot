"""
bot/handlers/log_channel.py

Commands to configure the log channel.

/setlog              → reply in target channel to link it
/setlog -100...      → set by channel ID
/unsetlog            → remove log channel
/logchannel          → show current log channel info

The bot must be admin in the log channel to post messages.

After /setlog:
  Bot tests by posting a "Log channel configured" message.
  If it fails → error message, log channel not saved.

Logs prefix: [LOG_CHANNEL_CMD]
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.error import TelegramError

from db.ops.log_channel import get_log_channel, get_log_categories

log = logging.getLogger("log_channel_cmd")


async def cmd_setlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setlog -100123456789
    or forward a message from the channel and reply with /setlog
    """
    msg  = update.effective_message
    chat = update.effective_chat
    db   = context.bot_data.get("db")

    channel_id = None

    if context.args:
        try:
            channel_id = int(context.args[0])
        except ValueError:
            await msg.reply_text("Usage: /setlog <channel_id>")
            return

    elif msg.reply_to_message and msg.reply_to_message.forward_from_chat:
        channel_id = msg.reply_to_message.forward_from_chat.id

    if not channel_id:
        await msg.reply_text(
            "Usage:\n"
            "1. /setlog <channel_id>\n"
            "2. Forward a message from your log channel, then reply with /setlog"
        )
        return

    try:
        await context.bot.send_message(
            chat_id    = channel_id,
            text       = (
                "✅ <b>Nexus Log Channel Configured</b>\n\n"
                f"Group: <b>{chat.title}</b> (<code>{chat.id}</code>)\n"
                "All moderation actions will be logged here."
            ),
            parse_mode = "HTML"
        )
    except TelegramError as e:
        await msg.reply_text(
            f"❌ Could not post to channel <code>{channel_id}</code>.\n"
            "Make sure the bot is an admin in that channel.\n\n"
            f"Error: {e}",
            parse_mode="HTML"
        )
        return

    from db.ops.automod import update_group_setting
    await update_group_setting(db, chat.id, "log_channel_id", channel_id)
    await msg.reply_text(
        f"✅ Log channel set to <code>{channel_id}</code>.\n"
        "A test message has been posted.",
        parse_mode="HTML"
    )
    log.info(
        f"[LOG_CHANNEL_CMD] Set | chat={chat.id} channel={channel_id}"
    )


async def cmd_unsetlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unsetlog — remove log channel."""
    msg  = update.effective_message
    chat = update.effective_chat
    db   = context.bot_data.get("db")

    from db.ops.automod import update_group_setting
    await update_group_setting(db, chat.id, "log_channel_id", None)
    await msg.reply_text("✅ Log channel removed.")
    log.info(f"[LOG_CHANNEL_CMD] Unset | chat={chat.id}")


async def cmd_logchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/logchannel — show current log channel and category status."""
    msg  = update.effective_message
    chat = update.effective_chat
    db   = context.bot_data.get("db")

    channel_id = await get_log_channel(db, chat.id)
    if not channel_id:
        await msg.reply_text(
            "No log channel configured.\n"
            "Use /setlog <channel_id> to set one."
        )
        return

    categories = await get_log_categories(db, chat.id)

    cat_lines = []
    for cat, enabled in sorted(categories.items()):
        icon = "✅" if enabled else "❌"
        cat_lines.append(f"{icon} {cat}")

    await msg.reply_text(
        f"📡 <b>Log Channel:</b> <code>{channel_id}</code>\n\n"
        f"<b>Categories:</b>\n" + "\n".join(cat_lines) + "\n\n"
        "Use the Mini App to toggle categories.",
        parse_mode="HTML"
    )
