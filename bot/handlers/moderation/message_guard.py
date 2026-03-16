import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank
from db.client import db

log = logging.getLogger("[MSG_GUARD]")


async def message_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Runs on every group message.
    1. Is sender an admin? -> skip all checks
    2. Language auto-detection (passive, non-blocking)
    3. Lock checks (media, stickers, links etc)
    4. Blacklist check
    5. Filter auto-reply check
    """
    if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
        return

    if not update.effective_message or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    message = update.effective_message
    user_id = update.effective_user.id
    text = message.text or message.caption or ""

    # 1. Is sender an admin?
    rank = await get_user_rank(context.bot, chat_id, user_id)
    is_admin = rank >= RANK_ADMIN

    # Admins skip enforcement (locks, flood, blacklist) but NOT keyword filters.
    # Filters (auto-replies) run for everyone including admins.
    if is_admin:
        if text:
            try:
                async with db.pool.acquire() as conn:
                    filter_rows = await conn.fetch(
                        "SELECT keyword, reply_content, response FROM filters WHERE chat_id = $1",
                        chat_id,
                    )
                    for filter_row in filter_rows:
                        keyword = filter_row["keyword"]
                        if keyword.isalpha():
                            pattern = (
                                r"(?<![a-zA-Z0-9_])" + re.escape(keyword) + r"(?![a-zA-Z0-9_])"
                            )
                            if re.search(pattern, text, re.IGNORECASE):
                                reply = (
                                    filter_row.get("reply_content")
                                    or filter_row.get("response")
                                    or ""
                                )
                                if reply:
                                    await _send_filter_reply(message, reply)
                                break
                        else:
                            if keyword.lower() in text.lower():
                                reply = (
                                    filter_row.get("reply_content")
                                    or filter_row.get("response")
                                    or ""
                                )
                                if reply:
                                    await _send_filter_reply(message, reply)
                                break
            except Exception as e:
                log.error(
                    f"[MSG_GUARD] Filter check failed for admin in {chat_id}: {e}", exc_info=True
                )
        return

    # Guard: ensure db.pool is available
    if not db or not db.pool:
        log.warning("[MSG_GUARD] db.pool is None — skipping checks for chat %s", chat_id)
        return

    # ── Passive Language Detection (v21) ───────────────────────────────────
    # Run in background - non-blocking
    message_text = update.effective_message.text or update.effective_message.caption or ""
    if message_text and db:
        try:
            from bot.utils.lang_detect import auto_detect_and_store

            pool = context.bot_data.get("db") or db.pool
            if pool:
                asyncio.create_task(
                    auto_detect_and_store(
                        db=pool,
                        user_id=update.effective_user.id,
                        chat_id=update.effective_chat.id,
                        telegram_code=update.effective_user.language_code,
                        first_name=update.effective_user.first_name,
                        last_name=update.effective_user.last_name,
                        message_text=message_text,
                    )
                )
        except Exception:
            # Never block message processing for language detection
            pass
    # ───────────────────────────────────────────────────────────────────────

    # ── Phase 1 & 3: Spam Signal Collection & ML Classifier ───────────────
    try:
        from bot.handlers.community_vote import detect_scam, start_community_vote
        from bot.ml.signal_collector import record_pattern_match, record_spam_signal

        # 1. Scam pattern detection (if not already handled by MessageHandler)
        # Note: auto_detect_scam runs in group 5, we are in group 0.
        # If we detect it here, we might want to trigger it early.
        scam_result = detect_scam(text)
        if scam_result:
            scam_type, scam_desc = scam_result
            asyncio.create_task(record_pattern_match(user_id, chat_id, text, scam_type))
            # We don't trigger the vote here to avoid duplication with auto_detect_scam
            # unless we want to return early. Let's just record the signal.

        # 2. ML Classifier
        from bot.ml.spam_classifier import classifier

        if classifier.is_trained and text and len(text) > 10:
            ml_result = classifier.predict(text)
            if ml_result["label"] == "spam" and ml_result["confidence"] > 0.85:
                # High confidence spam — trigger vote automatically
                await start_community_vote(
                    update,
                    context,
                    message,
                    scam_type="ml_classifier",
                    scam_description="🤖 ML Classifier: High confidence spam",
                    trigger_text=text[:200],
                    is_auto=True,
                )
                asyncio.create_task(
                    record_spam_signal(
                        user_id, chat_id, text, "ml_classifier", "spam", ml_result["confidence"]
                    )
                )
                # Since we started a vote, we might want to stop further checks
                # but usually we let message_guard continue unless we delete the message.
    except Exception as e:
        log.debug(f"Spam pipeline error: {e}")
    # ───────────────────────────────────────────────────────────────────────

    # 2. Flood check (Redis-backed counter with in-memory fallback)
    try:
        from bot.utils.flood_counter import flood_counter

        # Settings: 5 messages in 5 seconds
        if await flood_counter.is_flooding(chat_id, user_id, limit=5, window_secs=5):
            # Auto-mute 5 mins
            from telegram import ChatPermissions

            until = datetime.now(timezone.utc) + timedelta(minutes=5)
            await context.bot.restrict_chat_member(
                chat_id,
                user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            await message.reply_text("🚫 Flood detected. You are muted for 5 minutes.")
            return
    except Exception as e:
        log.debug(f"Flood check failed: {e}")

    # 3. Lock checks (using new canonical column names)
    locks = await db.fetchrow("SELECT * FROM locks WHERE chat_id = $1", chat_id)
    if locks:
        delete = False

        # Use new canonical names (matches what PUT /api/groups/{id}/locks saves)
        photo_locked = bool(locks.get("photo"))
        video_locked = bool(locks.get("video"))
        sticker_locked = bool(locks.get("sticker"))
        gif_locked = bool(locks.get("gif"))
        voice_locked = bool(locks.get("voice"))
        audio_locked = bool(locks.get("audio"))
        document_locked = bool(locks.get("document"))
        link_locked = bool(locks.get("link"))
        forward_locked = bool(locks.get("forward"))
        poll_locked = bool(locks.get("poll"))
        contact_locked = bool(locks.get("contact"))
        video_notes_locked = bool(locks.get("video_note"))

        if photo_locked and message.photo:
            delete = True
        elif video_locked and message.video:
            delete = True
        elif audio_locked and message.audio:
            delete = True
        elif document_locked and message.document:
            delete = True
        elif sticker_locked and message.sticker:
            delete = True
        elif gif_locked and message.animation:
            delete = True
        elif voice_locked and message.voice:
            delete = True
        elif link_locked and (
            message.entities and any(e.type in ["url", "text_link"] for e in message.entities)
        ):
            delete = True
        elif forward_locked and message.forward_from_chat:
            delete = True
        elif poll_locked and message.poll:
            delete = True
        elif contact_locked and message.contact:
            delete = True
        elif video_notes_locked and message.video_note:
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
            blacklist_rows = await conn.fetch(
                "SELECT word, action FROM blacklist WHERE chat_id = $1", chat_id
            )
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
                            chat_id,
                            user_id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=until,
                        )
                        await message.reply_text(
                            "🚫 Blacklisted word detected. You are muted for 10 minutes."
                        )
                        return
                    elif action == "ban":
                        await context.bot.ban_chat_member(chat_id, user_id)
                        await message.reply_text("🚫 Blacklisted word detected. You are banned.")
                        return
    except Exception as e:
        log.error(f"[MSG_GUARD] Blacklist check FAILED for chat {chat_id}: {e}", exc_info=True)

    # 5. Filter auto-reply check (word-boundary matching to avoid false positives)
    try:
        if text:
            async with db.pool.acquire() as conn:
                # Get all filters for this group
                filter_rows = await conn.fetch(
                    "SELECT keyword, reply_content, response FROM filters WHERE chat_id = $1",
                    chat_id,
                )
                for filter_row in filter_rows:
                    keyword = filter_row["keyword"]
                    # Use word-boundary regex for alpha keywords; substring match for non-alpha
                    if keyword.isalpha():
                        pattern = r"(?<![a-zA-Z0-9_])" + re.escape(keyword) + r"(?![a-zA-Z0-9_])"
                        if re.search(pattern, text, re.IGNORECASE):
                            reply = (
                                filter_row.get("reply_content") or filter_row.get("response") or ""
                            )
                            if reply:
                                await _send_filter_reply(message, reply)
                            break
                    else:
                        # Non-alpha keywords use substring match (original behavior)
                        if keyword.lower() in text.lower():
                            reply = (
                                filter_row.get("reply_content") or filter_row.get("response") or ""
                            )
                            if reply:
                                await _send_filter_reply(message, reply)
                            break
    except Exception as e:
        log.error(f"[MSG_GUARD] Filter check FAILED for chat {chat_id}: {e}", exc_info=True)

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
    import re

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.constants import ParseMode

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
