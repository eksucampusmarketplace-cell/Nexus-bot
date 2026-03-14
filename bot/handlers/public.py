"""
bot/handlers/public.py

Public commands available to ALL group members (not just admins).

Commands:
  /rules         → show group rules
  /time          → show current group time (in group timezone)
  /id            → show user's Telegram ID (and chat ID)
  /report        → report a message to admins
  /kickme        → user requests to be kicked
  /adminlist     → list group admins
  /staff         → alias for /adminlist
  /invitelink    → get invite link (if allowed)
  /groupinfo     → show group statistics

Logs prefix: [PUBLIC_CMD]
"""

import logging
from datetime import datetime

import pytz
from telegram import Update
from telegram.ext import ContextTypes

from db.ops.automod import get_group_settings
from db.ops.reports import save_report
from bot.logging.log_channel import log_event

log = logging.getLogger("public_cmd")


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/rules — show group rules from settings."""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    settings = await get_group_settings(db, chat.id)
    rules = settings.get("rules_text") if settings else None

    if not rules:
        rules = await _generate_rules(settings)

    await msg.reply_text(f"📋 <b>Group Rules</b>\n\n{rules}", parse_mode="HTML")


async def cmd_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/time — show current time in group's timezone."""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    settings = await get_group_settings(db, chat.id)
    tz_name = settings.get("timezone", "UTC") if settings else "UTC"

    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%A, %d %B %Y")
    except Exception:
        now = datetime.utcnow()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%A, %d %B %Y")
        tz_name = "UTC"

    await msg.reply_text(
        f"🕐 <b>Group Time</b>\n\n" f"📅 {date_str}\n" f"⏰ {time_str}\n" f"🌍 Timezone: {tz_name}",
        parse_mode="HTML",
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/id — show user ID and chat ID."""
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    target = msg.reply_to_message.from_user if msg.reply_to_message else user

    await msg.reply_text(
        f"👤 <b>User ID:</b> <code>{target.id}</code>\n"
        f"💬 <b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"📝 <b>Username:</b> @{target.username or 'none'}",
        parse_mode="HTML",
    )


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /report [reason]
    Reports the replied-to message to group admins.
    Notifies all admins via private message.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data.get("db")

    if not msg.reply_to_message:
        await msg.reply_text("Reply to a message to report it.\n" "Usage: /report [reason]")
        return

    reported_msg = msg.reply_to_message
    reported_user = reported_msg.from_user
    reason = " ".join(context.args) if context.args else "No reason given"

    report_id = await save_report(
        db,
        chat.id,
        reporter_id=user.id,
        reported_id=reported_user.id if reported_user else None,
        message_id=reported_msg.message_id,
        reason=reason,
    )

    await msg.reply_text(f"✅ Report submitted (#{report_id}).\n" "Admins have been notified.")

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        reporter_name = f"@{user.username}" if user.username else user.full_name
        reported_name = (
            f"@{reported_user.username}"
            if reported_user and reported_user.username
            else (reported_user.full_name if reported_user else "Unknown")
        )

        alert_text = (
            f"🚨 <b>Report #{report_id}</b>\n\n"
            f"Group: {chat.title}\n"
            f"Reporter: {reporter_name}\n"
            f"Reported: {reported_name}\n"
            f"Reason: {reason}\n\n"
            f"Message: {(reported_msg.text or '')[:200]}"
        )

        for admin in admins:
            if admin.user.is_bot:
                continue
            try:
                await context.bot.send_message(
                    chat_id=admin.user.id, text=alert_text, parse_mode="HTML"
                )
            except Exception:
                pass
    except Exception as e:
        log.warning(f"[PUBLIC_CMD] Admin notify failed | {e}")

    await log_event(
        bot=context.bot,
        db=db,
        chat_id=chat.id,
        event_type="report",
        actor=user,
        details={"report_id": report_id, "reason": reason},
        chat_title=chat.title or "",
        bot_id=context.bot.id,
    )
    log.info(
        f"[PUBLIC_CMD] Report | chat={chat.id} "
        f"reporter={user.id} reported={reported_user.id if reported_user else None}"
    )


async def cmd_kickme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/kickme — user kicks themselves."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    try:
        await context.bot.ban_chat_member(chat.id, user.id)
        await context.bot.unban_chat_member(chat.id, user.id)
        await msg.reply_text(f"👢 {user.mention_html()} has left.", parse_mode="HTML")
        log.info(f"[PUBLIC_CMD] Kickme | chat={chat.id} user={user.id}")
    except Exception as e:
        await msg.reply_text(f"❌ Failed: {e}")


async def cmd_adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/adminlist — list all group admins."""
    msg = update.effective_message
    chat = update.effective_chat

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        lines = []
        for a in admins:
            if a.user.is_bot:
                continue
            name = a.user.full_name
            handle = f"@{a.user.username}" if a.user.username else ""
            role = "👑 Owner" if a.status == "creator" else "⚡ Admin"
            title = f" ({a.custom_title})" if getattr(a, "custom_title", None) else ""
            lines.append(f"{role} {name} {handle}{title}")

        await msg.reply_text(
            f"👮 <b>Admins ({len(lines)}):</b>\n\n" + "\n".join(lines), parse_mode="HTML"
        )
    except Exception as e:
        await msg.reply_text(f"❌ Failed to get admin list: {e}")


async def cmd_invitelink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/invitelink — get the group invite link."""
    msg = update.effective_message
    chat = update.effective_chat

    try:
        link = await context.bot.export_chat_invite_link(chat.id)
        await msg.reply_text(f"🔗 Invite link:\n{link}")
    except Exception as e:
        await msg.reply_text(f"❌ Failed to get invite link: {e}")


async def cmd_groupinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/groupinfo — show group statistics and settings."""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    settings = await get_group_settings(db, chat.id)
    tz_name = settings.get("timezone", "UTC") if settings else "UTC"

    try:
        count = await context.bot.get_chat_member_count(chat.id)
        admins = await context.bot.get_chat_administrators(chat.id)
        n_admins = sum(1 for a in admins if not a.user.is_bot)
    except Exception:
        count = "?"
        n_admins = "?"

    features = []
    if settings:
        if settings.get("captcha_enabled"):
            features.append("✅ CAPTCHA")
        if settings.get("auto_antiraid_enabled"):
            features.append("✅ Auto Anti-Raid")
        if settings.get("welcome_enabled"):
            features.append("✅ Welcome Messages")
        if settings.get("group_password"):
            features.append("✅ Group Password")

    features_str = "\n".join(features) or "Default settings"

    await msg.reply_text(
        f"📊 <b>{chat.title}</b>\n\n"
        f"👥 Members: {count}\n"
        f"👮 Admins: {n_admins}\n"
        f"🌍 Timezone: {tz_name}\n\n"
        f"<b>Features:</b>\n{features_str}",
        parse_mode="HTML",
    )


async def _generate_rules(settings: dict) -> str:
    """Auto-generate rules list from active locks."""
    if not settings:
        return "No rules configured."

    locks = settings.get("locks", {}) or {}
    rules = []
    n = 1

    LOCK_LABELS = {
        "link": "No Telegram links",
        "website": "No external links",
        "sticker": "No stickers",
        "gif": "No GIFs",
        "forward": "No forwarded messages",
        "photo": "No photos",
        "video": "No videos",
        "voice": "No voice messages",
        "bot": "No adding bots",
        "unofficial_tg": "No unofficial Telegram app ads",
    }

    for key, label in LOCK_LABELS.items():
        if locks.get(key):
            rules.append(f"{n}. {label}")
            n += 1

    if settings.get("max_warnings", 0):
        rules.append(f"{n}. Maximum {settings['max_warnings']} warnings before action")

    return "\n".join(rules) if rules else "Be respectful and follow group guidelines."
