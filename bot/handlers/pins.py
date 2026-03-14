"""
bot/handlers/pins.py

Full pin management system.

Commands:
  /pin [silent]      → pin replied-to message (silent = no notification)
  /unpin             → unpin current pinned message
  /unpinall          → unpin all messages
  /repin             → re-pin the last pinned message
  /editpin <text>    → edit the pinned message content
  /delpin            → delete the pinned message entirely

Logs prefix: [PINS]
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.error import TelegramError

from db.ops.pins import record_pin, get_current_pin, get_last_pin, mark_unpinned
from bot.logging.log_channel import log_event

log = logging.getLogger("pins")


async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /pin [silent]
    Pins the replied-to message.
    With 'silent': no notification sent to members.
    """
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")
    args = context.args or []
    silent = "silent" in args

    if not msg.reply_to_message:
        await msg.reply_text("Reply to a message to pin it.")
        return

    target_id = msg.reply_to_message.message_id
    try:
        await context.bot.pin_chat_message(
            chat_id=chat.id, message_id=target_id, disable_notification=silent
        )
        await record_pin(db, chat.id, target_id, pinned_by=update.effective_user.id)
        await msg.reply_text(f"📌 Message pinned{'(silently)' if silent else ''}.")
        await log_event(
            bot=context.bot,
            db=db,
            chat_id=chat.id,
            event_type="pin",
            actor=update.effective_user,
            details={"message_id": target_id},
            chat_title=chat.title or "",
            bot_id=context.bot.id,
        )
        log.info(f"[PINS] Pinned | chat={chat.id} msg={target_id}")
    except TelegramError as e:
        await msg.reply_text(f"❌ Failed to pin: {e}")


async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unpin — unpin the current pinned message."""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    try:
        await context.bot.unpin_chat_message(chat_id=chat.id)
        await mark_unpinned(db, chat.id)
        await msg.reply_text("✅ Message unpinned.")
        await log_event(
            bot=context.bot,
            db=db,
            chat_id=chat.id,
            event_type="unpin",
            actor=update.effective_user,
            chat_title=chat.title or "",
            bot_id=context.bot.id,
        )
        log.info(f"[PINS] Unpinned | chat={chat.id}")
    except TelegramError as e:
        await msg.reply_text(f"❌ Failed to unpin: {e}")


async def cmd_unpinall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unpinall — unpin all messages in group."""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    try:
        await context.bot.unpin_all_chat_messages(chat_id=chat.id)
        await db.execute("UPDATE pinned_messages SET is_current=FALSE WHERE chat_id=$1", chat.id)
        await msg.reply_text("✅ All messages unpinned.")
        log.info(f"[PINS] Unpinned all | chat={chat.id}")
    except TelegramError as e:
        await msg.reply_text(f"❌ Failed to unpin all: {e}")


async def cmd_repin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/repin — re-pin the last pinned message."""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    last = await get_last_pin(db, chat.id)
    if not last:
        await msg.reply_text("No previous pin found.")
        return

    try:
        await context.bot.pin_chat_message(
            chat_id=chat.id, message_id=last["message_id"], disable_notification=True
        )
        await record_pin(db, chat.id, last["message_id"], update.effective_user.id)
        await msg.reply_text("📌 Previous message re-pinned.")
        log.info(f"[PINS] Re-pinned | chat={chat.id} msg={last['message_id']}")
    except TelegramError as e:
        await msg.reply_text(f"❌ Failed to re-pin: {e}")


async def cmd_editpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /editpin <new text>
    Edits the currently pinned message text.
    Requires the pinned message to be a bot message.
    """
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    if not context.args:
        await msg.reply_text("Usage: /editpin <new message text>")
        return

    current = await get_current_pin(db, chat.id)
    if not current:
        await msg.reply_text("No pinned message tracked.")
        return

    new_text = " ".join(context.args)
    try:
        await context.bot.edit_message_text(
            chat_id=chat.id, message_id=current["message_id"], text=new_text
        )
        await msg.reply_text("✅ Pinned message updated.")
        log.info(f"[PINS] Edited pin | chat={chat.id}")
    except TelegramError as e:
        await msg.reply_text(f"❌ Failed to edit: {e}")


async def cmd_delpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delpin — delete the pinned message entirely."""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    current = await get_current_pin(db, chat.id)
    if not current:
        await msg.reply_text("No pinned message tracked.")
        return

    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=current["message_id"])
        await mark_unpinned(db, chat.id)
        await msg.reply_text("✅ Pinned message deleted.")
        log.info(f"[PINS] Deleted pin | chat={chat.id}")
    except TelegramError as e:
        await msg.reply_text(f"❌ Failed to delete pinned message: {e}")
