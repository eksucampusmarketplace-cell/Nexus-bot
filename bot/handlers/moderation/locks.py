import logging

from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank, publish_event
from db.client import db

log = logging.getLogger("[MOD_LOCKS]")


async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Specify what to lock: media, stickers, gifs, links, etc."
        )
        return

    lock_type = context.args[0].lower()

    # Update DB
    valid_locks = [
        "media",
        "stickers",
        "gifs",
        "links",
        "forwards",
        "polls",
        "games",
        "voice",
        "video_notes",
        "contacts",
    ]
    if lock_type not in valid_locks and lock_type != "all":
        await update.message.reply_text(f"❌ Invalid lock type. Valid: {', '.join(valid_locks)}")
        return

    # For simplicity, we'll just update the DB. Actual enforcement should be in message_guard.py
    if lock_type == "all":
        updates = {lock_item: True for lock_item in valid_locks}
    else:
        updates = {lock_type: True}

    # Build query
    columns = ", ".join(updates.keys())
    values = ", ".join(["True"] * len(updates))

    await db.execute(
        f"""
        INSERT INTO locks (chat_id, {columns}) VALUES ($1, {values})
        ON CONFLICT (chat_id) DO UPDATE SET {", ".join([f"{k}=True" for k in updates.keys()])}
    """,
        chat_id,
    )

    await update.message.reply_text(f"🔒 Locked: {lock_type}")
    await publish_event(chat_id, "lock_change", {"lock_type": lock_type, "enabled": True})


async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        return

    if not context.args:
        return
    lock_type = context.args[0].lower()

    valid_locks = [
        "media",
        "stickers",
        "gifs",
        "links",
        "forwards",
        "polls",
        "games",
        "voice",
        "video_notes",
        "contacts",
    ]

    if lock_type == "all":
        updates = {lock_item: False for lock_item in valid_locks}
    elif lock_type in valid_locks:
        updates = {lock_type: False}
    else:
        return

    await db.execute(
        f"""
        INSERT INTO locks (chat_id, {", ".join(updates.keys())}) VALUES ($1, {", ".join(["False"] * len(updates))})
        ON CONFLICT (chat_id) DO UPDATE SET {", ".join([f"{k}=False" for k in updates.keys()])}
    """,
        chat_id,
    )

    await update.message.reply_text(f"🔓 Unlocked: {lock_type}")
    await publish_event(chat_id, "lock_change", {"lock_type": lock_type, "enabled": False})


async def locks_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    row = await db.fetchrow("SELECT * FROM locks WHERE chat_id = $1", chat_id)
    if not row:
        await update.message.reply_text("🔓 No locks active in this group.")
        return

    text = f"🔒 *Locks in {update.effective_chat.title}*\n\n"
    for key in row.keys():
        if key == "chat_id":
            continue
        status = "🔴 locked" if row[key] else "🟢 unlocked"
        text += f"{status} — {key}\n"

    await update.message.reply_text(text, parse_mode="Markdown")
