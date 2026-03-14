import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import (
    ERRORS,
    check_permissions,
    log_action,
    mention_user,
    publish_event,
    resolve_target,
)


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await context.bot.ban_chat_member(chat_id, target.id)
        await context.bot.unban_chat_member(chat_id, target.id)

        await log_action(
            chat_id, "kick", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "kick",
                "target_id": target.id,
                "target_name": target.full_name,
                "admin_id": invoker.id,
                "reason": reason,
            },
        )

        await update.message.reply_text(
            f"👢 Kicked | {await mention_user(target)}\n"
            f"📋 Reason: {reason}\n"
            f"👮 By: {await mention_user(invoker)}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to kick: {e}")
