"""
bot/automod/engine.py

Central automod evaluation engine.
Called from MessageHandler for every non-admin message.

check_message(update, context) → AutomodResult

Evaluation order (respects rule_priority table):
  1. Whitelist check → skip if whitelisted
  2. Lock admins check → skip if admin AND lock_admins=False
  3. Silent time check → delete if in silent window
  4. Content type locks (with time window check)
  5. Unofficial Telegram detection
  6. Duplicate message check
  7. Word/line/char count checks
  8. Necessary words check
  9. REGEX pattern check
  10. Word filter (existing)
  11. Flood check (existing)

For each violation:
  - Get per-rule penalty (rule_penalties table)
  - Fall back to group default penalty
  - Apply penalty (delete/silence/kick/ban)
  - Send admonition if enabled (with self-destruct)
  - Push SSE event to Mini App

Logs prefix: [AUTOMOD]
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from telegram import Update, Message
from telegram.ext import ContextTypes

from db.ops.automod import (
    get_group_settings, get_rule_time_windows, get_rule_penalties,
    get_silent_times, get_necessary_words, get_regex_patterns,
    get_rule_priority, record_message_hash, get_recent_hash_count,
    get_whitelist
)
from bot.automod.penalties import apply_penalty, PenaltyType
from bot.automod.detectors import (
    detect_content_type, detect_unofficial_telegram,
    is_in_time_window
)
from api.routes.events import push_event

log = logging.getLogger("automod")


@dataclass
class AutomodResult:
    violated:    bool  = False
    rule_key:    str   = ""
    penalty:     str   = ""
    reason:      str   = ""
    deleted:     bool  = False
    actioned:    bool  = False


async def check_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> AutomodResult:
    """
    Main entry point. Called for every message.
    Returns AutomodResult — caller doesn't need to do anything else.
    """
    msg     = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user
    db      = context.bot_data.get("db")
    bot_id  = context.bot.id

    if not msg or not user or not chat:
        return AutomodResult()

    # Load settings
    settings    = await get_group_settings(db, chat.id)
    if not settings:
        return AutomodResult()

    # ── 1. Whitelist ──────────────────────────────────────────────────────
    whitelist = await get_whitelist(db, chat.id)
    if user.id in whitelist:
        return AutomodResult()

    # ── 2. Admin exemption ────────────────────────────────────────────────
    is_admin = await _is_admin(context, chat.id, user.id)
    if is_admin and not settings.get("lock_admins"):
        return AutomodResult()

    # Load per-rule config
    time_windows = await get_rule_time_windows(db, chat.id)
    penalties    = await get_rule_penalties(db, chat.id)
    priority     = await get_rule_priority(db, chat.id)
    now_time     = _now_in_tz(settings.get("timezone", "UTC"))

    # ── 3. Silent time check ──────────────────────────────────────────────
    silent_times = await get_silent_times(db, chat.id)
    for slot in silent_times:
        if slot["is_active"] and is_in_time_window(
            now_time, slot["start_time"], slot["end_time"]
        ):
            await msg.delete()
            return AutomodResult(
                violated=True, rule_key="silent_time",
                penalty="delete", deleted=True,
                reason="Group is in silent mode"
            )

    # ── 4. Content type locks (with time windows) ──────────────────────────
    locks     = settings.get("locks", {})
    timed_locks = settings.get("timed_locks", {})
    content_type = detect_content_type(msg)

    # Build ordered rule list
    ordered_rules = priority if priority else list(locks.keys())

    for rule_key in ordered_rules:
        # Check if lock is enabled
        lock_on = locks.get(rule_key, False)
        if not lock_on:
            continue

        # Check if content matches this rule
        if not _content_matches_rule(msg, content_type, rule_key):
            continue

        # Check time window (per-rule)
        tw = time_windows.get(rule_key)
        if tw:
            in_window = is_in_time_window(
                now_time, tw["start_time"], tw["end_time"]
            )
            if not in_window:
                continue  # lock only active during window, not now

        # Check timed lock
        tl = timed_locks.get(rule_key)
        if tl and not is_in_time_window(
            now_time, tl["start"], tl["end"]
        ):
            continue

        # Violation found — get penalty
        penalty_row = penalties.get(rule_key)
        penalty     = penalty_row["penalty"] if penalty_row else settings.get(
            "default_penalty", "delete"
        )
        duration    = penalty_row["duration_hours"] if penalty_row else 0

        result = AutomodResult(
            violated=True, rule_key=rule_key,
            penalty=penalty,
            reason=_rule_reason(rule_key)
        )
        await _enforce(msg, user, chat, context, settings, result, duration)
        await _push_sse(context, chat, user, result)
        return result

    # ── 5. Unofficial Telegram detection ──────────────────────────────────
    if settings.get("unofficial_tg_lock") and msg.text:
        if detect_unofficial_telegram(msg):
            result = AutomodResult(
                violated=True, rule_key="unofficial_tg",
                penalty=settings.get("default_penalty", "ban"),
                reason="Unofficial Telegram app advertisement"
            )
            await _enforce(msg, user, chat, context, settings, result, 0)
            await _push_sse(context, chat, user, result)
            return result

    # ── 6. Duplicate check ────────────────────────────────────────────────
    dup_limit  = settings.get("duplicate_limit", 0)
    dup_window = settings.get("duplicate_window_mins", 60)
    if dup_limit > 0 and msg.text:
        msg_hash = hashlib.md5(
            msg.text.strip().lower().encode()
        ).hexdigest()

        count = await get_recent_hash_count(
            db, chat.id, msg_hash, dup_window
        )
        if count >= dup_limit:
            result = AutomodResult(
                violated=True, rule_key="duplicate",
                penalty="delete",
                reason=f"Duplicate message (max {dup_limit} allowed)"
            )
            await _enforce(msg, user, chat, context, settings, result, 0)
            return result

        await record_message_hash(db, chat.id, msg_hash, user.id)

    # ── 7. Word/line/char count ───────────────────────────────────────────
    if msg.text:
        text       = msg.text
        word_count = len(text.split())
        line_count = len(text.splitlines())
        char_count = len(text)

        checks = [
            (settings.get("min_words", 0),  word_count, "<",
             f"Too few words (min {settings.get('min_words')})"),
            (settings.get("max_words", 0),  word_count, ">",
             f"Too many words (max {settings.get('max_words')})"),
            (settings.get("min_lines", 0),  line_count, "<",
             f"Too few lines (min {settings.get('min_lines')})"),
            (settings.get("max_lines", 0),  line_count, ">",
             f"Too many lines (max {settings.get('max_lines')})"),
            (settings.get("min_chars", 0),  char_count, "<",
             f"Too short (min {settings.get('min_chars')} chars)"),
            (settings.get("max_chars", 0),  char_count, ">",
             f"Too long (max {settings.get('max_chars')} chars)"),
        ]
        for limit, actual, op, reason in checks:
            if limit > 0:
                violated = (
                    (op == "<" and actual < limit) or
                    (op == ">" and actual > limit)
                )
                if violated:
                    result = AutomodResult(
                        violated=True, rule_key="text_length",
                        penalty="delete", reason=reason
                    )
                    await _enforce(
                        msg, user, chat, context, settings, result, 0
                    )
                    return result

    # ── 8. Necessary words ────────────────────────────────────────────────
    if settings.get("necessary_words_active") and msg.text:
        nec_words = await get_necessary_words(db, chat.id)
        if nec_words:
            text_lower = msg.text.lower()
            has_word   = any(w.lower() in text_lower for w in nec_words)
            if not has_word:
                result = AutomodResult(
                    violated=True, rule_key="necessary_words",
                    penalty="delete",
                    reason="Message must contain a required word"
                )
                await _enforce(
                    msg, user, chat, context, settings, result, 0
                )
                return result

    # ── 9. REGEX check ────────────────────────────────────────────────────
    if settings.get("regex_active") and msg.text:
        patterns = await get_regex_patterns(db, chat.id)
        for p in patterns:
            if not p["is_active"]:
                continue
            try:
                if re.search(p["pattern"], msg.text, re.IGNORECASE):
                    result = AutomodResult(
                        violated=True, rule_key="regex",
                        penalty=p.get("penalty", "delete"),
                        reason=f"Message matched pattern"
                    )
                    await _enforce(
                        msg, user, chat, context, settings, result, 0
                    )
                    return result
            except re.error:
                pass  # invalid pattern — skip

    return AutomodResult()


async def _enforce(
    msg, user, chat, context, settings,
    result: AutomodResult, duration_hours: int
):
    """Delete message, apply penalty, send admonition."""
    try:
        await msg.delete()
        result.deleted = True
    except Exception:
        pass

    penalty = result.penalty
    if penalty in ("silence", "kick", "ban"):
        await apply_penalty(
            context.bot, chat.id, user.id,
            PenaltyType(penalty), duration_hours
        )
        result.actioned = True

    # Send admonition if enabled
    if settings.get("admonition_enabled") and settings.get("warn_on_violation"):
        await _send_admonition(msg, user, chat, context, settings, result)

    # Auto-warn counting
    if settings.get("auto_warning_enabled"):
        await _record_warning(context, chat.id, user.id, settings)

    log.info(
        f"[AUTOMOD] Enforced | chat={chat.id} user={user.id} "
        f"rule={result.rule_key} penalty={result.penalty}"
    )


async def _send_admonition(
    msg, user, chat, context, settings, result: AutomodResult
):
    """Send violation reason message, auto-delete after self_destruct_minutes."""
    from db.ops.automod import get_user_warning_count
    db = context.bot_data.get("db")

    warn_count  = await get_user_warning_count(db, chat.id, user.id)
    max_warns   = settings.get("max_warnings", 5)
    warn_time   = settings.get("warning_keep_days", 7)

    # Build admonition text from template
    template = settings.get(
        "admonition_text",
        "⚠️ {user}, your message was deleted.\n"
        "Reason: {reason}\nPenalty: {penalty}\n"
        "Warnings: {user_warnings}/{warnings_count}"
    )
    text = template.format(
        user=f"@{user.username}" if user.username else user.first_name,
        reason=result.reason,
        penalty=result.penalty,
        user_warnings=warn_count,
        warnings_count=max_warns,
        warningstime=warn_time,
    )

    try:
        sent = await context.bot.send_message(
            chat_id=chat.id, text=text
        )
        # Self-destruct
        if settings.get("self_destruct_enabled"):
            minutes = settings.get("self_destruct_minutes", 2)
            import asyncio
            asyncio.create_task(_delete_after(sent, minutes * 60))
    except Exception:
        pass


async def _delete_after(message, delay_seconds: int):
    import asyncio
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception:
        pass


async def _record_warning(context, chat_id, user_id, settings):
    """Increment warning count. Apply punishment if max reached."""
    db         = context.bot_data.get("db")
    max_warns  = settings.get("max_warnings", 5)
    keep_days  = settings.get("warning_keep_days", 7)

    count = await context.bot_data["db"].fetchval(
        """
        SELECT COUNT(*) FROM user_warnings
        WHERE chat_id=$1 AND user_id=$2
        AND created_at > NOW() - INTERVAL '1 day' * $3
        """,
        chat_id, user_id, keep_days
    )
    await db.execute(
        "INSERT INTO user_warnings (chat_id, user_id) VALUES ($1,$2)",
        chat_id, user_id
    )
    count += 1

    if count >= max_warns:
        await apply_penalty(
            context.bot, chat_id, user_id,
            PenaltyType.silence, 12  # 12h silence on max warns
        )


async def _push_sse(context, chat, user, result: AutomodResult):
    """Push automod action to Mini App via SSE."""
    db       = context.bot_data.get("db")
    owner_id = await _get_owner_id(db, context.bot.id)
    if owner_id:
        push_event(owner_id, {
            "type":    "message_delete" if result.penalty == "delete" else "member_" + result.penalty,
            "title":   f"AutoMod: {result.rule_key}",
            "body":    f"{user.full_name} — {result.reason}",
            "chat_id": chat.id,
        })


def _content_matches_rule(msg, content_type: str, rule_key: str) -> bool:
    """Check if message content matches a given rule key."""
    CONTENT_MAP = {
        "photo":           "photo",
        "video":           "video",
        "sticker":         "sticker",
        "gif":             "animation",
        "voice":           "voice",
        "audio":           "audio",
        "file":            "document",
        "software":        "apk",
        "location":        "location",
        "phone":           "contact",
        "game":            "game",
        "poll":            "poll",
    }

    TEXT_CHECKS = {
        "link":            lambda m: _has_tg_link(m),
        "website":         lambda m: _has_website(m),
        "username":        lambda m: _has_username(m),
        "hashtag":         lambda m: _has_hashtag(m),
        "forward":         lambda m: m.forward_date is not None,
        "forward_channel": lambda m: (
            m.forward_from_chat is not None and
            m.forward_from_chat.type == "channel"
        ),
        "slash":           lambda m: (
            m.text and m.text.startswith("/")
        ),
        "no_caption":      lambda m: (
            (m.photo or m.video) and not m.caption
        ),
        "emoji_only":      lambda m: _is_emoji_only(m),
        "emoji":           lambda m: _has_emoji(m),
        "english":         lambda m: _has_english(m),
        "arabic_farsi":    lambda m: _has_arabic_farsi(m),
        "reply":           lambda m: (
            m.reply_to_message is not None
        ),
        "external_reply":  lambda m: (
            m.reply_to_message is not None and
            m.reply_to_message.forward_from_chat is not None
        ),
        "bot":             lambda m: (
            m.new_chat_members and
            any(u.is_bot for u in m.new_chat_members)
        ),
        "unofficial_tg":   lambda m: False,  # handled separately
        "spoiler":         lambda m: _has_spoiler(m),
        "text":            lambda m: bool(m.text and not m.text.startswith("/")),
    }

    if rule_key in CONTENT_MAP:
        return content_type == CONTENT_MAP[rule_key]

    if rule_key in TEXT_CHECKS:
        try:
            return TEXT_CHECKS[rule_key](msg)
        except Exception:
            return False

    return False


def _rule_reason(rule_key: str) -> str:
    REASONS = {
        "link":           "Telegram links are not allowed",
        "website":        "External links are not allowed",
        "username":       "Usernames (@mentions) are not allowed",
        "hashtag":        "Hashtags are not allowed",
        "photo":          "Photos are not allowed",
        "video":          "Videos are not allowed",
        "sticker":        "Stickers are not allowed",
        "gif":            "GIFs are not allowed",
        "voice":          "Voice messages are not allowed",
        "audio":          "Audio files are not allowed",
        "file":           "File uploads are not allowed",
        "forward":        "Forwarded messages are not allowed",
        "forward_channel":"Forwarding from channels is not allowed",
        "game":           "Games are not allowed",
        "poll":           "Polls are not allowed",
        "bot":            "Adding bots is not allowed",
        "unofficial_tg":  "Unofficial Telegram app advertisements are not allowed",
        "slash":          "Bot commands are not allowed",
        "no_caption":     "Posts must include a caption",
        "emoji_only":     "Emoji-only messages are not allowed",
        "emoji":          "Messages containing emoji are not allowed",
        "english":        "English text is not allowed",
        "arabic_farsi":   "Arabic/Farsi text is not allowed",
        "reply":          "Replies are not allowed",
        "external_reply": "External replies are not allowed",
        "spoiler":        "Spoiler content is not allowed",
        "text":           "Text messages are not allowed",
        "duplicate":      "Duplicate messages are not allowed",
        "text_length":    "Message length out of bounds",
        "necessary_words":"Message must contain a required word",
        "regex":          "Message matched a forbidden pattern",
        "silent_time":    "Group is in silent mode",
    }
    return REASONS.get(rule_key, "Rule violation")


def _now_in_tz(tz_name: str):
    """Return current time in given timezone as time object."""
    import pytz
    try:
        tz  = pytz.timezone(tz_name)
        now = datetime.now(tz)
        return now.time()
    except Exception:
        return datetime.now().time()


async def _is_admin(context, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


async def _get_owner_id(db, bot_id: int) -> int | None:
    if not db:
        return None
    row = await db.fetchrow(
        "SELECT owner_id FROM clone_bots WHERE bot_id=$1", bot_id
    )
    return row["owner_id"] if row else None


# ── Text analysis helpers ─────────────────────────────────────────────────

def _has_tg_link(msg) -> bool:
    import re
    text = msg.text or msg.caption or ""
    return bool(re.search(r't\.me/|telegram\.me/', text, re.I))

def _has_website(msg) -> bool:
    import re
    text = msg.text or msg.caption or ""
    # URL not from t.me
    has_url = bool(re.search(r'https?://|www\.', text, re.I))
    has_tg  = bool(re.search(r't\.me/|telegram\.me/', text, re.I))
    return has_url and not has_tg

def _has_username(msg) -> bool:
    import re
    text = msg.text or msg.caption or ""
    return bool(re.search(r'@\w+', text))

def _has_hashtag(msg) -> bool:
    import re
    text = msg.text or msg.caption or ""
    return bool(re.search(r'#\w+', text))

def _is_emoji_only(msg) -> bool:
    import emoji as emoji_lib
    text = msg.text or ""
    if not text:
        return False
    clean = emoji_lib.replace_emoji(text, '').strip()
    return len(clean) == 0 and len(text) > 0

def _has_emoji(msg) -> bool:
    import emoji as emoji_lib
    text = msg.text or msg.caption or ""
    return emoji_lib.emoji_count(text) > 0

def _has_english(msg) -> bool:
    import re
    text = msg.text or msg.caption or ""
    return bool(re.search(r'[a-zA-Z]', text))

def _has_arabic_farsi(msg) -> bool:
    import re
    text = msg.text or msg.caption or ""
    return bool(re.search(r'[\u0600-\u06FF\u0750-\u077F]', text))

def _has_spoiler(msg) -> bool:
    if not msg.entities:
        return False
    return any(e.type == "spoiler" for e in msg.entities)
