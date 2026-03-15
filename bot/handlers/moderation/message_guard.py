import logging
import re
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
    3. Blacklist check
    4. Filter auto-reply check
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
    text = message.text or message.caption or ""

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

    # 3. Lock checks (support both old and new column names)
    locks = await db.fetchrow("SELECT * FROM locks WHERE chat_id = $1", chat_id)
    if locks:
        delete = False

        # Check old column names first, then new ones for compatibility
        media_locked = locks.get("media") or locks.get("photo") or locks.get("video")
        stickers_locked = locks.get("stickers") or locks.get("sticker")
        gifs_locked = locks.get("gifs") or locks.get("gif")
        links_locked = locks.get("links") or locks.get("link")
        forwards_locked = locks.get("forwards") or locks.get("forward")
        polls_locked = locks.get("polls") or locks.get("poll")
        voice_locked = locks.get("voice")
        video_notes_locked = locks.get("video_notes")
        contacts_locked = locks.get("contacts") or locks.get("contact")

        if media_locked and (message.photo or message.video or message.audio or message.document):
            delete = True
        elif stickers_locked and message.sticker:
            delete = True
        elif gifs_locked and message.animation:
            delete = True
        elif links_locked and (
            message.entities and any(e.type in ["url", "text_link"] for e in message.entities)
        ):
            delete = True
        elif forwards_locked and message.forward_from_chat:
            delete = True
        elif polls_locked and message.poll:
            delete = True
        elif voice_locked and message.voice:
            delete = True
        elif video_notes_locked and message.video_note:
            delete = True
        elif contacts_locked and message.contact:
            delete = True

        if delete:
            try:
                await message.delete()
                return  # Stop further checks
            except Exception as e:
                log.error(f"Failed to delete locked message: {e}")

    # 4. Blacklist check (using blacklist table)
    try:
        async with db.pool.acquire() as conn:
            blacklist_rows = await conn.fetch("SELECT word, action FROM blacklist WHERE chat_id = $1", chat_id)
            for row in blacklist_rows:
                word = row["word"].lower()
                if word in text.lower():
                    action = row.get("action", "delete")
                    if action == "delete":
                        await message.delete()
                        return
                    elif action == "mute":
                        until = datetime.utcnow() + timedelta(minutes=10)
                        await context.bot.restrict_chat_member(
                            chat_id, user_id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=until
                        )
                        await message.reply_text(f"🚫 Blacklisted word detected. You are muted for 10 minutes.")
                        return
                    elif action == "ban":
                        await context.bot.ban_chat_member(chat_id, user_id)
                        await message.reply_text(f"🚫 Blacklisted word detected. You are banned.")
                        return
    except Exception as e:
        log.debug(f"Blacklist check error: {e}")

    # 5. Filter auto-reply check
    try:
        if text:
            async with db.pool.acquire() as conn:
                # Try reply_content first, then fall back to response
                filter_row = await conn.fetchrow(
                    """SELECT keyword, reply_content, response FROM filters 
                       WHERE chat_id = $1 AND $2 ILIKE '%' || keyword || '%' 
                       LIMIT 1""",
                    chat_id, text
                )
                if filter_row:
                    reply = filter_row.get("reply_content") or filter_row.get("response") or ""
                    if reply:
                        await _send_filter_reply(message, reply)
    except Exception as e:
        log.debug(f"Filter check error: {e}")

    # ── XP Award ─────────────────────────────────────────────────────────
    # Award XP for sending a message (non-blocking, create_task)
    try:
        import asyncio
        from bot.engagement.xp import XPEngine

        xp_engine = XPEngine()
        pool = context.bot_data.get("db") or db.pool
        redis = context.bot_data.get("redis")

        asyncio.create_task(
            xp_engine.award_xp(
                pool=pool,
                redis=redis,
                bot=context.bot,
                chat_id=chat_id,
                user_id=user_id,
                bot_id=context.bot.id,
                amount=1,
                reason="message",
            )
        )
    except Exception:
        # Never block message processing for XP
        pass


async def _send_filter_reply(message, reply: str):
    """
    Send filter reply with support for HTML, Markdown, and inline buttons.
    1. If '---' in reply: split on first ---, parse [Label](URL) lines as InlineKeyboardButton rows
    2. Detect parse mode: HTML if <b>/<i>/<code> found, MARKDOWN_V2 if **/__/``` found
    3. Try with parse_mode first, fall back to plain text on error
    4. Pass reply_markup=InlineKeyboardMarkup(rows) if buttons were parsed
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.constants import ParseMode
    import re

    text_part = reply
    rows = []

    if "---" in reply:
        parts = reply.split("---", 1)
        text_part = parts[0].strip()
        button_part = parts[1].strip()

        for line in button_part.split("\n"):
            line = line.strip()
            if not line:
                continue
            matches = re.findall(r"\[(.*?)\]\((.*?)\)", line)
            if matches:
                row = [InlineKeyboardButton(label, url=url) for label, url in matches]
                rows.append(row)

    # Detect parse mode
    parse_mode = None
    if any(tag in text_part for tag in ["<b>", "<i>", "<code>"]):
        parse_mode = ParseMode.HTML
    elif any(tag in text_part for tag in ["**", "__", "```"]):
        parse_mode = ParseMode.MARKDOWN_V2

    reply_markup = InlineKeyboardMarkup(rows) if rows else None

    try:
        await message.reply_text(text_part, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception:
        # Fallback to plain text on error
        await message.reply_text(text_part, reply_markup=reply_markup)
