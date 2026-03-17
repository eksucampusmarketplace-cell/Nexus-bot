import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank, publish_event
from db.client import db

log = logging.getLogger("[MOD_LOCKS]")

# Valid lock types with miniapp-compatible column names (canonical names only)
VALID_LOCKS = [
    "photo",
    "video",
    "sticker",
    "gif",
    "voice",
    "audio",
    "document",
    "link",
    "forward",
    "poll",
    "contact",
    "video_note",
]

# Map legacy names to new column names
LOCK_COLUMN_MAP = {
    "media": "photo",
    "stickers": "sticker",
    "gifs": "gif",
    "links": "link",
    "forwards": "forward",
    "polls": "poll",
    "contacts": "contact",
    "video_notes": "video_note",
}


async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        return

    if not context.args:
        await update.message.reply_text(f"❌ Specify what to lock: {', '.join(VALID_LOCKS[:6])}...")
        return

    lock_type = context.args[0].lower()

    # Normalize user input before DB write
    lock_type = LOCK_COLUMN_MAP.get(lock_type, lock_type)

    if lock_type not in VALID_LOCKS and lock_type != "all":
        await update.message.reply_text(f"❌ Invalid lock type. Valid: {', '.join(VALID_LOCKS)}")
        return

    if lock_type == "all":
        updates = {
            "photo": True,
            "video": True,
            "sticker": True,
            "gif": True,
            "link": True,
            "forward": True,
            "poll": True,
            "voice": True,
            "video_note": True,
            "contact": True,
        }
    else:
        updates = {lock_type: True}

    # Build query using proper asyncpg context
    columns = ", ".join(updates.keys())
    placeholders = ", ".join([f"${i+2}" for i in range(len(updates))])
    values = list(updates.values())

    async with db.pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO locks (chat_id, {columns}) VALUES ($1, {placeholders})
            ON CONFLICT (chat_id) DO UPDATE SET {
                ", ".join([f"{k}=EXCLUDED.{k}" for k in updates.keys()])
            }
            """,
            chat_id,
            *values,
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

    # Normalize user input before DB write
    lock_type = LOCK_COLUMN_MAP.get(lock_type, lock_type)

    if lock_type == "all":
        updates = {
            "photo": False,
            "video": False,
            "sticker": False,
            "gif": False,
            "link": False,
            "forward": False,
            "poll": False,
            "voice": False,
            "video_note": False,
            "contact": False,
        }
    elif lock_type in VALID_LOCKS:
        updates = {lock_type: False}
    else:
        return

    async with db.pool.acquire() as conn:
        placeholders = ", ".join([f"${i+2}" for i in range(len(updates))])
        values = list(updates.values())
        await conn.execute(
            f"""
            INSERT INTO locks (chat_id, {", ".join(updates.keys())})
            VALUES ($1, {placeholders})
            ON CONFLICT (chat_id) DO UPDATE SET {
                ", ".join([f"{k}=EXCLUDED.{k}" for k in updates.keys()])
            }
            """,
            chat_id,
            *values,
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


async def open_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        return
    from telegram import ChatPermissions

    perms = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
    )
    await context.bot.set_chat_permissions(chat_id, perms)
    await update.message.reply_text("🔓 Group opened — all members can send messages.")
    await publish_event(chat_id, "group_opened", {})


async def close_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        return
    from telegram import ChatPermissions

    perms = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_invite_users=False,
    )
    await context.bot.set_chat_permissions(chat_id, perms)
    await update.message.reply_text("🔒 Group closed — members cannot send messages.")
    await publish_event(chat_id, "group_closed", {})
