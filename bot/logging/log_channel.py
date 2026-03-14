"""
bot/logging/log_channel.py

Central log channel dispatcher.
Called from every bot action handler to post structured log messages
to the group's configured log channel.

Usage:
    from bot.logging.log_channel import log_event

    await log_event(
        bot=context.bot,
        db=db,
        chat_id=chat.id,
        event_type="ban",
        actor=update.effective_user,
        target=target_user,
        details={"reason": "Spam links", "duration": "permanent"}
    )

Logs prefix: [LOG_CHANNEL]
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from telegram import Bot, User
from telegram.error import TelegramError

from db.ops.log_channel import get_log_channel, get_log_categories, log_activity

log = logging.getLogger("log_channel")

EVENT_META = {
    "ban": ("🚫", "BAN"),
    "mute": ("🔇", "MUTE"),
    "warn": ("⚠️", "WARN"),
    "kick": ("👢", "KICK"),
    "delete": ("🗑", "DELETE"),
    "join": ("👋", "JOIN"),
    "leave": ("🚪", "LEAVE"),
    "raid": ("🚨", "RAID"),
    "antiraid_start": ("🛡", "ANTI-RAID START"),
    "antiraid_end": ("🛡", "ANTI-RAID END"),
    "captcha_pass": ("✅", "CAPTCHA PASSED"),
    "captcha_fail": ("❌", "CAPTCHA FAILED"),
    "filter": ("🔍", "FILTER TRIGGERED"),
    "blocklist": ("🚫", "BLOCKLIST"),
    "settings_change": ("⚙️", "SETTINGS CHANGED"),
    "pin": ("📌", "PIN"),
    "unpin": ("📌", "UNPIN"),
    "report": ("🚨", "REPORT"),
    "note_access": ("📝", "NOTE ACCESSED"),
    "schedule_send": ("📅", "SCHEDULED SEND"),
    "password_pass": ("🔐", "PASSWORD PASSED"),
    "password_fail": ("🔐", "PASSWORD FAILED"),
    "import": ("📥", "IMPORT"),
    "export": ("📤", "EXPORT"),
    "reset": ("🔄", "RESET"),
    "inline_query": ("⚡", "INLINE QUERY"),
}

CATEGORY_MAP = {
    "ban": "ban",
    "mute": "mute",
    "warn": "warn",
    "kick": "kick",
    "delete": "delete",
    "join": "join",
    "leave": "leave",
    "raid": "raid",
    "antiraid_start": "raid",
    "antiraid_end": "raid",
    "captcha_pass": "captcha",
    "captcha_fail": "captcha",
    "filter": "filter",
    "blocklist": "blocklist",
    "settings_change": "settings",
    "pin": "pin",
    "unpin": "pin",
    "report": "report",
    "note_access": "note",
    "schedule_send": "schedule",
    "password_pass": "password",
    "password_fail": "password",
    "import": "import_export",
    "export": "import_export",
    "reset": "import_export",
    "inline_query": "settings",
}


async def log_event(
    bot: Bot,
    db,
    chat_id: int,
    event_type: str,
    actor: Optional[User] = None,
    target: Optional[User] = None,
    details: dict = None,
    chat_title: str = "",
    bot_id: int = 0,
):
    """
    Main entry point. Call this from every action handler.
    Writes to activity_log table and posts to log channel if configured.
    """
    details = details or {}

    # ── 1. Write to activity log (always) ─────────────────────────────────
    try:
        await log_activity(
            db,
            chat_id=chat_id,
            bot_id=bot_id,
            event_type=event_type,
            actor_id=actor.id if actor else None,
            target_id=target.id if target else None,
            actor_name=_user_label(actor),
            target_name=_user_label(target),
            details=details,
        )
    except Exception as e:
        log.warning(f"[LOG_CHANNEL] activity_log write failed: {e}")

    # ── 2. Post to log channel (if configured + category enabled) ──────────
    try:
        channel_id = await get_log_channel(db, chat_id)
    except Exception:
        return

    if not channel_id:
        return

    try:
        categories = await get_log_categories(db, chat_id)
    except Exception:
        categories = {}

    category = CATEGORY_MAP.get(event_type)
    if category and not categories.get(category, True):
        return

    text = _build_log_message(event_type, actor, target, details, chat_title, chat_id)

    try:
        await bot.send_message(
            chat_id=channel_id, text=text, parse_mode="HTML", disable_web_page_preview=True
        )
        log.debug(
            f"[LOG_CHANNEL] Posted | chat={chat_id} " f"type={event_type} channel={channel_id}"
        )
    except TelegramError as e:
        log.warning(f"[LOG_CHANNEL] Post failed | chat={chat_id} " f"channel={channel_id} err={e}")


def _build_log_message(
    event_type: str,
    actor: Optional[User],
    target: Optional[User],
    details: dict,
    chat_title: str,
    chat_id: int,
) -> str:
    """Build a rich HTML log message."""
    emoji, label = EVENT_META.get(event_type, ("📋", event_type.upper()))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [f"{emoji} <b>{label}</b>"]

    if chat_title:
        lines.append(f"├ <b>Chat:</b> {chat_title} (<code>{chat_id}</code>)")

    if actor:
        lines.append(f"├ <b>By:</b> {_user_html(actor)}")

    if target:
        lines.append(f"├ <b>Target:</b> {_user_html(target)}")

    DETAIL_LABELS = {
        "rule_key": "Rule",
        "reason": "Reason",
        "penalty": "Penalty",
        "duration": "Duration",
        "note_name": "Note",
        "filter_keyword": "Filter",
        "template": "Template",
        "schedule_type": "Schedule",
        "report_id": "Report #",
        "settings_key": "Setting",
        "old_value": "Old value",
        "new_value": "New value",
        "export_keys": "Exported keys",
        "query": "Query",
    }

    for key, label_str in DETAIL_LABELS.items():
        if key in details and details[key] is not None:
            val = str(details[key])
            if len(val) > 80:
                val = val[:80] + "…"
            lines.append(f"├ <b>{label_str}:</b> {val}")

    preview = details.get("message_preview")
    if preview:
        preview = preview[:200].replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"├ <b>Preview:</b>\n<code>{preview}</code>")

    lines.append(f"└ <b>Time:</b> {now}")

    return "\n".join(lines)


def _user_html(user: User) -> str:
    """Format user as clickable mention + ID."""
    name = user.full_name or f"User {user.id}"
    if user.username:
        return (
            f'<a href="tg://user?id={user.id}">{name}</a> '
            f"(@{user.username}, <code>{user.id}</code>)"
        )
    return f'<a href="tg://user?id={user.id}">{name}</a> (<code>{user.id}</code>)'


def _user_label(user: Optional[User]) -> str:
    if not user:
        return ""
    if user.username:
        return f"@{user.username}"
    return user.full_name or str(user.id)
