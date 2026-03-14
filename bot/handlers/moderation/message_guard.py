import logging
from datetime import datetime, timedelta

from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank
from db.client import db

log = logging.getLogger("[MSG_GUARD]")


async def message_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Runs on every group message.
    1. Is sender an admin? -> skip all checks
    2. Lock checks (media, stickers, links etc)
    3. TODO: Blacklist check
    4. TODO: Filter check
    """
    if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
        return

    if not update.effective_message or not update.effective_user:
        return

    # 1. Is sender an admin?
    rank = await get_user_rank(context.bot, update.effective_chat.id, update.effective_user.id)
    if rank >= RANK_ADMIN:
        return

    chat_id = update.effective_chat.id
    message = update.effective_message
    user_id = update.effective_user.id

    # 2. Flood check (Redis counter)
    if db.redis:
        flood_key = f"nexus:flood:{chat_id}:{user_id}"
        count = await db.redis.incr(flood_key)
        if count == 1:
            await db.redis.expire(flood_key, 5)  # 5 second window

        if count > 5:  # More than 5 messages in 5 seconds
            try:
                # Auto-mute 5 mins
                until = datetime.utcnow() + timedelta(minutes=5)
                await context.bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until,
                )
                await message.reply_text("🚫 Flood detected. You are muted for 5 minutes.")
                return
            except Exception:
                pass

    # 3. Lock checks
    # Optimization: Cache locks in Redis
    locks = await db.fetchrow("SELECT * FROM locks WHERE chat_id = $1", chat_id)
    if locks:
        delete = False

        if locks["media"] and (message.photo or message.video or message.audio or message.document):
            delete = True
        elif locks["stickers"] and message.sticker:
            delete = True
        elif locks["gifs"] and message.animation:
            delete = True
        elif locks["links"] and (
            message.entities and any(e.type in ["url", "text_link"] for e in message.entities)
        ):
            delete = True
        elif locks["forwards"] and message.forward_from_chat:
            delete = True
        elif locks["polls"] and message.poll:
            delete = True
        elif locks["voice"] and message.voice:
            delete = True
        elif locks["video_notes"] and message.video_note:
            delete = True
        elif locks["contacts"] and message.contact:
            delete = True

        if delete:
            try:
                await message.delete()
                return  # Stop further checks
            except Exception as e:
                log.error(f"Failed to delete locked message: {e}")

    # TODO: Add filter and blacklist checks here
