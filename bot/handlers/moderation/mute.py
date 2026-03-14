import logging
from datetime import datetime

from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import (
    ERRORS,
    check_permissions,
    log_action,
    mention_user,
    notify_log_channel,
    parse_time,
    publish_event,
    resolve_target,
)
from db.client import db

log = logging.getLogger("[MOD_MUTE]")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    target, reason = await resolve_target(update, context)
    if not target:
        await update.message.reply_text(ERRORS["no_target"])
        return

    allowed, error_key = await check_permissions(context.bot, chat_id, invoker.id, target.id)
    if not allowed:
        await update.message.reply_text(ERRORS.get(error_key, "Permission denied."))
        return

    reason = reason or "No reason provided"

    try:
        await context.bot.restrict_chat_member(
            chat_id, target.id, permissions=ChatPermissions(can_send_messages=False)
        )

        # Save to DB
        query = """
        INSERT INTO mutes (chat_id, user_id, muted_by, reason)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id, user_id) DO UPDATE 
        SET muted_by = EXCLUDED.muted_by, reason = EXCLUDED.reason, muted_at = NOW(), is_active = TRUE, unmute_at = NULL
        """
        await db.execute(query, chat_id, target.id, invoker.id, reason)

        await log_action(
            chat_id, "mute", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )

        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "mute",
                "target_id": target.id,
                "target_name": target.full_name,
                "admin_id": invoker.id,
                "reason": reason,
                "duration": "permanent",
            },
        )

        await update.message.reply_text(
            f"🔇 Muted | {await mention_user(target)}\n"
            f"📋 Reason: {reason}\n"
            f"👮 By: {await mention_user(invoker)}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute: {e}")


async def tmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Logic similar to tban for parsing args
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        if not context.args:
            await update.message.reply_text("❌ Please specify duration (e.g. 1h, 30m)")
            return
        time_str = context.args[0]
        reason = " ".join(context.args[1:]) or "No reason provided"
    else:
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: /tmute @user <time> [reason]")
            return
        target_str = context.args[0]
        time_str = context.args[1]
        reason = " ".join(context.args[2:]) or "No reason provided"
        # ... resolve target ... (omitted for brevity, assume target is resolved)
        try:
            member = await context.bot.get_chat_member(chat_id, int(target_str))
            target = member.user
        except Exception:
            await update.message.reply_text("❌ User not found.")
            return

    duration = parse_time(time_str)
    if not duration:
        await update.message.reply_text(ERRORS["invalid_time"])
        return

    unmute_at = datetime.utcnow() + duration

    try:
        await context.bot.restrict_chat_member(
            chat_id,
            target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=unmute_at,
        )

        await db.execute(
            "INSERT INTO mutes (chat_id, user_id, muted_by, reason, unmute_at) VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (chat_id, user_id) DO UPDATE SET muted_by=EXCLUDED.muted_by, reason=EXCLUDED.reason, is_active=TRUE, unmute_at=EXCLUDED.unmute_at",
            chat_id,
            target.id,
            invoker.id,
            reason,
            unmute_at,
        )

        await update.message.reply_text(
            f"🔇 Temp Muted | {await mention_user(target)}\n"
            f"⏱ Duration: {time_str}\n"
            f"📋 Reason: {reason}\n"
            f"👮 By: {await mention_user(invoker)}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to tmute: {e}")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    target, _ = await resolve_target(update, context)

    if not target:
        await update.message.reply_text(ERRORS["no_target"])
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id,
            target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        await db.execute(
            "UPDATE mutes SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
            chat_id,
            target.id,
        )
        await update.message.reply_text(
            f"✅ Unmuted | {await mention_user(target)}", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unmute: {e}")
