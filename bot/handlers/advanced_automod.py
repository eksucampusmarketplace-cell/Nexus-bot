"""
bot/handlers/advanced_automod.py

All new automod text commands parsed by the prefix engine.
These integrate with the existing triple-prefix command system.

New commands supported:

Timed rules:
  !lock link from 23:30 to 8:10
  !unlock link from 23:30 to 8:10  (remove time window)

Per-violation penalty:
  !kick link
  !silence photo 24        (silence for 24h)
  !delete forward
  !ban website

Silent times:
  !first silent time from 23 to 8
  !disable first silent time
  !second silent time from 10 to 14
  !third silent time from 18 to 20
  !delete all silent times

Self-destruct:
  !enable self-destruct
  !disable self-destruct
  !self-destruct time set on 2

Duplicate limiting:
  !duplicate set on 3
  !duplicate set on disable
  !duplicate in every 2 hours

Word/line counts:
  !minimum number of words set on 3
  !minimum number of words set on disable
  !maximum number of words set on 10
  !max.word.count 4
  !min.text.line 2
  !max.text.line 10
  !max.text.length 500
  !min.text.length 10

REGEX:
  !regex add ^\\d{10}$
  !regex remove ^\\d{10}$
  !regex list
  !regex test ^\\d{10}$ some test string

Necessary words:
  !be.in.text hello
  !!be.in.text hello
  !!beintexts            (clear all)

Lock admins:
  !lock admins
  !unlock admins

Timed locks:
  !timedlock image 08:00 12:00
  !!timedlock image

Templates (Mini App only — no text command needed)

Logs prefix: [AUTOMOD_CMD]
"""

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from db.ops.automod import (
    set_rule_time_window,
    remove_rule_time_window,
    set_rule_penalty,
    upsert_silent_time,
    disable_silent_time,
    clear_all_silent_times,
    update_group_setting,
    add_necessary_word,
    remove_necessary_word,
    clear_necessary_words,
    add_regex_pattern,
    remove_regex_pattern,
    get_regex_patterns,
    set_timed_lock,
    remove_timed_lock,
)

log = logging.getLogger("automod_cmd")

SLOT_MAP = {"first": 1, "second": 2, "third": 3}
VALID_LOCKS = {
    "link",
    "website",
    "username",
    "photo",
    "video",
    "sticker",
    "gif",
    "forward",
    "forward_channel",
    "text",
    "voice",
    "file",
    "software",
    "poll",
    "slash",
    "no_caption",
    "emoji_only",
    "emoji",
    "game",
    "english",
    "arabic_farsi",
    "reply",
    "external_reply",
    "bot",
    "unofficial_tg",
    "hashtag",
    "location",
    "phone",
    "audio",
    "spoiler",
}
VALID_PENALTIES = {"delete", "silence", "kick", "ban"}


async def handle_automod_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Parse and dispatch all advanced automod commands.
    Called after basic prefix detection confirms it's an admin command.
    """
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")
    text = (msg.text or "").strip()

    # Normalize
    cmd = text.lstrip("!.").strip().lower()

    # ── Timed rule: !lock link from 23:30 to 8:10 ────────────────────────
    m = re.match(r"lock (\w+) from (\d{1,2}(?::\d{2})?) to (\d{1,2}(?::\d{2})?)", cmd)
    if m:
        rule_key = m.group(1)
        start = _normalize_time(m.group(2))
        end = _normalize_time(m.group(3))
        if rule_key in VALID_LOCKS:
            await set_rule_time_window(db, chat.id, rule_key, start, end)
            await msg.reply_text(
                f"⏰ Lock <b>{rule_key}</b> active from " f"{start} to {end}", parse_mode="HTML"
            )
        return

    # ── Per-violation penalty: !kick link / !silence photo 24 ────────────
    m = re.match(r"(kick|silence|delete|ban) (\w+)(?:\s+(\d+))?", cmd)
    if m:
        penalty = m.group(1)
        rule_key = m.group(2)
        duration = int(m.group(3)) if m.group(3) else 0
        if rule_key in VALID_LOCKS and penalty in VALID_PENALTIES:
            await set_rule_penalty(db, chat.id, rule_key, penalty, duration)
            dur_str = f" for {duration}h" if duration else ""
            await msg.reply_text(
                f"⚖️ Violation of <b>{rule_key}</b> → " f"<b>{penalty}</b>{dur_str}",
                parse_mode="HTML",
            )
        return

    # ── Silent time: !first silent time from 23 to 8 ─────────────────────
    m = re.match(
        r"(first|second|third) silent time from (\d{1,2}(?::\d{2})?) to (\d{1,2}(?::\d{2})?)", cmd
    )
    if m:
        slot = SLOT_MAP[m.group(1)]
        start = _normalize_time(m.group(2))
        end = _normalize_time(m.group(3))
        await upsert_silent_time(db, chat.id, slot, start, end)
        await msg.reply_text(f"🔕 Silent time {slot}: {start} → {end}", parse_mode="HTML")
        return

    # ── Disable silent time ───────────────────────────────────────────────
    m = re.match(r"disable (first|second|third) silent time", cmd)
    if m:
        slot = SLOT_MAP[m.group(1)]
        await disable_silent_time(db, chat.id, slot)
        await msg.reply_text(f"✅ Silent time {slot} disabled")
        return

    if cmd == "delete all silent times":
        await clear_all_silent_times(db, chat.id)
        await msg.reply_text("✅ All silent times cleared")
        return

    # ── Self-destruct ─────────────────────────────────────────────────────
    if cmd == "enable self-destruct":
        await update_group_setting(db, chat.id, "self_destruct_enabled", True)
        await msg.reply_text("💣 Self-destruct enabled — bot messages will auto-delete")
        return
    if cmd == "disable self-destruct":
        await update_group_setting(db, chat.id, "self_destruct_enabled", False)
        await msg.reply_text("✅ Self-destruct disabled")
        return
    m = re.match(r"self-destruct time set on (\d+)", cmd)
    if m:
        mins = int(m.group(1))
        await update_group_setting(db, chat.id, "self_destruct_minutes", mins)
        await msg.reply_text(f"⏱ Bot messages will delete after {mins} minute(s)")
        return

    # ── Duplicate limiting ────────────────────────────────────────────────
    m = re.match(r"duplicate set on (\d+|disable)", cmd)
    if m:
        val = m.group(1)
        n = 0 if val == "disable" else int(val)
        await update_group_setting(db, chat.id, "duplicate_limit", n)
        await msg.reply_text(f"📋 Duplicate limit: {'disabled' if n == 0 else n}")
        return
    m = re.match(r"duplicate in every (\d+) hours?", cmd)
    if m:
        mins = int(m.group(1)) * 60
        await update_group_setting(db, chat.id, "duplicate_window_mins", mins)
        await msg.reply_text(f"⏱ Duplicate window: {m.group(1)} hour(s)")
        return
    m = re.match(r"duplicate in every (\d+) min", cmd)
    if m:
        mins = int(m.group(1))
        await update_group_setting(db, chat.id, "duplicate_window_mins", mins)
        await msg.reply_text(f"⏱ Duplicate window: {mins} minute(s)")
        return

    # ── Word/line counts ──────────────────────────────────────────────────
    COUNT_CMDS = {
        r"minimum number of words set on (\d+|disable)": ("min_words", "Minimum words"),
        r"maximum number of words set on (\d+|disable)": ("max_words", "Maximum words"),
        r"min\.word\.count (\d+)": ("min_words", "Minimum words"),
        r"max\.word\.count (\d+)": ("max_words", "Maximum words"),
        r"min\.text\.line (\d+)": ("min_lines", "Minimum lines"),
        r"max\.text\.line (\d+)": ("max_lines", "Maximum lines"),
        r"min\.text\.length (\d+)": ("min_chars", "Minimum chars"),
        r"max\.text\.length (\d+)": ("max_chars", "Maximum chars"),
    }
    for pattern, (setting_key, label) in COUNT_CMDS.items():
        m = re.match(pattern, cmd)
        if m:
            val = m.group(1)
            n = 0 if val == "disable" else int(val)
            await update_group_setting(db, chat.id, setting_key, n)
            await msg.reply_text(f"📏 {label}: {'disabled' if n == 0 else n}")
            return

    # ── REGEX ─────────────────────────────────────────────────────────────
    m = re.match(r"regex add (.+)", cmd)
    if m:
        pattern = m.group(1).strip()
        try:
            re.compile(pattern)
            await add_regex_pattern(db, chat.id, pattern)
            await msg.reply_text(f"🔍 REGEX added: <code>{pattern}</code>", parse_mode="HTML")
        except re.error as e:
            await msg.reply_text(f"❌ Invalid REGEX: {e}")
        return

    m = re.match(r"regex remove (.+)", cmd)
    if m:
        await remove_regex_pattern(db, chat.id, m.group(1).strip())
        await msg.reply_text("✅ REGEX pattern removed")
        return

    if cmd == "regex list":
        patterns = await get_regex_patterns(db, chat.id)
        if not patterns:
            await msg.reply_text("No REGEX patterns set")
            return
        lines = [f"• <code>{p['pattern']}</code>" for p in patterns]
        await msg.reply_text("🔍 <b>REGEX Patterns:</b>\n" + "\n".join(lines), parse_mode="HTML")
        return

    m = re.match(r"regex test (.+?) (.+)", cmd)
    if m:
        pattern = m.group(1)
        test_str = m.group(2)
        try:
            match = bool(re.search(pattern, test_str, re.IGNORECASE))
            await msg.reply_text(
                f"🔍 Pattern: <code>{pattern}</code>\n"
                f"String: <code>{test_str}</code>\n"
                f"Match: {'✅ YES' if match else '❌ NO'}",
                parse_mode="HTML",
            )
        except re.error as e:
            await msg.reply_text(f"❌ Invalid REGEX: {e}")
        return

    # ── Necessary words ───────────────────────────────────────────────────
    m = re.match(r"be\.in\.text (.+)", cmd)
    if m:
        word = m.group(1).strip()
        await add_necessary_word(db, chat.id, word)
        await update_group_setting(db, chat.id, "necessary_words_active", True)
        await msg.reply_text(f"📝 Required word added: <b>{word}</b>", parse_mode="HTML")
        return

    # Handle !!be.in.text (remove) from original prefix
    if cmd.startswith("!be.in.text"):
        word = cmd.replace("!be.in.text", "").strip()
        await remove_necessary_word(db, chat.id, word)
        await msg.reply_text(f"✅ Required word removed: <b>{word}</b>", parse_mode="HTML")
        return
    if cmd == "beintexts":
        await clear_necessary_words(db, chat.id)
        await msg.reply_text("✅ All required words cleared")
        return

    # ── Lock/unlock admins ────────────────────────────────────────────────
    if cmd == "lock admins":
        await update_group_setting(db, chat.id, "lock_admins", True)
        await msg.reply_text("🔒 Admins are now subject to all rules")
        return
    if cmd == "unlock admins":
        await update_group_setting(db, chat.id, "lock_admins", False)
        await msg.reply_text("✅ Admins are exempt from rules")
        return

    # ── Timed locks ───────────────────────────────────────────────────────
    m = re.match(r"timedlock (\w+) (\d{1,2}:\d{2}) (\d{1,2}:\d{2})", cmd)
    if m:
        rule_key = m.group(1)
        start = m.group(2)
        end = m.group(3)
        await set_timed_lock(db, chat.id, rule_key, start, end)
        await msg.reply_text(
            f"⏰ <b>{rule_key}</b> locked from {start} to {end}", parse_mode="HTML"
        )
        return

    m = re.match(r"!!timedlock (\w+)", cmd)
    if m:
        await remove_timed_lock(db, chat.id, m.group(1))
        await msg.reply_text(f"✅ Timed lock removed for {m.group(1)}")
        return


def _normalize_time(t: str) -> str:
    """Convert '8' → '08:00', '23:30' → '23:30'"""
    if ":" not in t:
        return f"{int(t):02d}:00"
    parts = t.split(":")
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
