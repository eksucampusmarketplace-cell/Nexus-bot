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
    Checks in order:
    1. Is sender an admin? -> skip all checks
    2. Flood check (Redis counter)
    3. Lock checks (media, stickers, links etc)
    4. Blacklist check
    5. Filter check (keyword auto-replies)
    All checks fail open — if DB down, allow message.
    """
    if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
        return

    if not update.effective_message or not update.effective_user:
        return

    rank = await get_user_rank(context.bot, update.effective_chat.id, update.effective_user.id)
    if rank >= RANK_ADMIN:
        from bot.handlers.moderation.filters import check_filters
        try:
            await check_filters(update, context)
        except Exception:
            pass
        return

    chat_id = update.effective_chat.id
    message = update.effective_message
    user_id = update.effective_user.id

    # 2. Flood check (Redis counter)
    if db.redis:
        try:
            flood_key = f"nexus:flood:{chat_id}:{user_id}"
            count = await db.redis.incr(flood_key)
            if count == 1:
                await db.redis.expire(flood_key, 5)

            if count > 5:
                until = datetime.utcnow() + timedelta(minutes=5)
                await context.bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until,
                )
                try:
                    await message.reply_text("🚫 Flood detected. You are muted for 5 minutes.")
                except Exception:
                    pass
                return
        except Exception as e:
            log.debug(f"[MSG_GUARD] Flood check error: {e}")

    # 3. Lock checks
    try:
        locks = None
        if db.redis:
            import json
            cached = await db.redis.get(f"nexus:locks:{chat_id}")
            if cached:
                try:
                    locks = json.loads(cached)
                except Exception:
                    pass

        if locks is None:
            row = await db.fetchrow("SELECT * FROM locks WHERE chat_id = $1", chat_id)
            if row:
                locks = dict(row)
                if db.redis:
                    await db.redis.setex(
                        f"nexus:locks:{chat_id}", 60, json.dumps(locks)
                    )

        if locks:
            should_delete = False

            if locks.get("media") and (
                message.photo or message.video or message.audio or message.document
            ):
                should_delete = True
            elif locks.get("stickers") and message.sticker:
                should_delete = True
            elif locks.get("gifs") and message.animation:
                should_delete = True
            elif locks.get("links") and message.entities and any(
                e.type in ["url", "text_link"] for e in message.entities
            ):
                should_delete = True
            elif locks.get("forwards") and (
                message.forward_from or message.forward_from_chat
            ):
                should_delete = True
            elif locks.get("polls") and message.poll:
                should_delete = True
            elif locks.get("voice") and message.voice:
                should_delete = True
            elif locks.get("video_notes") and message.video_note:
                should_delete = True
            elif locks.get("contacts") and message.contact:
                should_delete = True
            elif locks.get("games") and message.game:
                should_delete = True

            if should_delete:
                try:
                    await message.delete()
                    return
                except Exception as e:
                    log.debug(f"[MSG_GUARD] Failed to delete locked message: {e}")
    except Exception as e:
        log.debug(f"[MSG_GUARD] Lock check error: {e}")

    # 4. Blacklist check
    try:
        from bot.handlers.moderation.blacklist import check_blacklist
        matched = await check_blacklist(update, context)
        if matched:
            return
    except Exception as e:
        log.debug(f"[MSG_GUARD] Blacklist check error: {e}")

    # 5. Filter check (keyword auto-replies)
    try:
        from bot.handlers.moderation.filters import check_filters
        await check_filters(update, context)
    except Exception as e:
        log.debug(f"[MSG_GUARD] Filter check error: {e}")
