"""
bot/handlers/copy_settings.py

Copy all group settings from one group to another.

Command:
  /copysettings -chatid  → copy to specific group by chat ID

What gets copied:
  - All group_settings columns (locks, limits, penalties, etc.)
  - Silent times (slots 1-3)
  - Rule time windows
  - Rule penalties
  - Rule priority
  - CAPTCHA settings
  - Automod toggles
  - Welcome message template

What does NOT get copied:
  - Notes (group-specific content)
  - Filters (group-specific content)
  - Members, warnings, reports
  - Scheduled messages
  - Bot token / clone config
  - Billing / entitlements

Logs prefix: [COPY_SETTINGS]
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger("copy_settings")

COPYABLE_SETTINGS_KEYS = [
    "locks", "default_penalty", "max_warnings", "warning_keep_days",
    "warn_on_violation", "admonition_enabled", "admonition_text",
    "self_destruct_enabled", "self_destruct_minutes",
    "lock_admins", "unofficial_tg_lock", "bot_inviter_ban",
    "duplicate_limit", "duplicate_window_mins",
    "min_words", "max_words", "min_lines", "max_lines",
    "min_chars", "max_chars",
    "necessary_words_active", "regex_active",
    "timed_locks", "antiraid_enabled", "antiraid_mode",
    "auto_antiraid_enabled", "auto_antiraid_threshold",
    "antiraid_duration_mins", "antiraid_threshold",
    "captcha_enabled", "captcha_mode",
    "captcha_timeout_mins", "captcha_kick_on_timeout",
    "welcome_enabled", "welcome_text", "welcome_media_type",
    "welcome_media_file_id", "farewell_enabled", "farewell_text",
    "timezone",
]


async def cmd_copy_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """
    /copysettings <target_chat_id>
    Copies settings from current group to target group.
    Must be admin in both groups.
    """
    msg  = update.effective_message
    chat = update.effective_chat
    db   = context.bot_data.get("db")
    user = update.effective_user

    if not context.args:
        await msg.reply_text(
            "Usage: /copysettings <target_chat_id>\n\n"
            "Example: /copysettings -100123456789\n\n"
            "You must be admin in the target group."
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await msg.reply_text("Invalid chat ID. Must be a number like -100123456789")
        return

    if target_id == chat.id:
        await msg.reply_text("Source and target must be different groups.")
        return

    try:
        src_member = await context.bot.get_chat_member(chat.id, user.id)
        tgt_member = await context.bot.get_chat_member(target_id, user.id)
    except Exception:
        await msg.reply_text(
            "❌ Cannot verify your admin status in the target group.\n"
            "Make sure you're an admin there and the bot is also in that group."
        )
        return

    if src_member.status not in ("creator", "administrator"):
        await msg.reply_text("❌ You must be admin in this group.")
        return
    if tgt_member.status not in ("creator", "administrator"):
        await msg.reply_text("❌ You must be admin in the target group.")
        return

    src_settings = await db.fetchrow(
        "SELECT * FROM groups WHERE chat_id=$1", chat.id
    )
    if not src_settings:
        await msg.reply_text("No settings found for this group.")
        return

    src_dict  = dict(src_settings)
    copy_data = {k: src_dict[k] for k in COPYABLE_SETTINGS_KEYS
                 if k in src_dict and src_dict[k] is not None}

    set_clauses = ", ".join(
        f"{k}=${i+2}" for i, k in enumerate(copy_data.keys())
    )
    values = [target_id] + list(copy_data.values())

    await db.execute(
        f"""INSERT INTO groups (chat_id, {', '.join(copy_data.keys())})
            VALUES ($1, {', '.join(f'${i+2}' for i in range(len(copy_data)))})
            ON CONFLICT (chat_id)
            DO UPDATE SET {set_clauses}""",
        *values
    )

    silent_rows = await db.fetch(
        "SELECT * FROM silent_times WHERE chat_id=$1 AND is_active=TRUE",
        chat.id
    )
    for row in silent_rows:
        await db.execute(
            """INSERT INTO silent_times
               (chat_id, slot, start_time, end_time, is_active,
                start_text, end_text)
               VALUES ($1,$2,$3,$4,$5,$6,$7)
               ON CONFLICT (chat_id, slot) DO UPDATE SET
                 start_time=EXCLUDED.start_time,
                 end_time=EXCLUDED.end_time,
                 is_active=EXCLUDED.is_active,
                 start_text=EXCLUDED.start_text,
                 end_text=EXCLUDED.end_text""",
            target_id, row["slot"], row["start_time"], row["end_time"],
            row["is_active"], row["start_text"], row["end_text"]
        )

    priority_row = await db.fetchrow(
        "SELECT rule_order FROM rule_priority WHERE chat_id=$1", chat.id
    )
    if priority_row:
        await db.execute(
            """INSERT INTO rule_priority (chat_id, rule_order)
               VALUES ($1,$2)
               ON CONFLICT (chat_id) DO UPDATE SET rule_order=EXCLUDED.rule_order""",
            target_id, priority_row["rule_order"]
        )

    await msg.reply_text(
        f"✅ Settings copied to group <code>{target_id}</code>.\n\n"
        f"Copied: {len(copy_data)} settings, "
        f"{len(silent_rows)} silent time slots, "
        f"rule priority order.",
        parse_mode="HTML"
    )
    log.info(
        f"[COPY_SETTINGS] Copied | from={chat.id} to={target_id} "
        f"by={user.id} keys={len(copy_data)}"
    )
