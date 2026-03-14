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
from db.client import db

log = logging.getLogger("[MOD_WARN]")


async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Add warning to DB
    await db.execute(
        "INSERT INTO warnings (chat_id, user_id, reason, issued_by) VALUES ($1, $2, $3, $4)",
        chat_id,
        target.id,
        reason,
        invoker.id,
    )

    # Count active warnings
    count = await db.fetchval(
        "SELECT COUNT(*) FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE",
        chat_id,
        target.id,
    )

    # Get warn settings
    settings = await db.fetchrow(
        "SELECT max_warns, warn_action, warn_duration FROM warn_settings WHERE chat_id = $1",
        chat_id,
    )
    if not settings:
        max_warns = 3
        warn_action = "mute"
    else:
        max_warns = settings["max_warns"]
        warn_action = settings["warn_action"]

    mention = await mention_user(target)
    await update.message.reply_text(
        f"⚠️ Warning | {mention}\n"
        f"📋 Reason: {reason}\n"
        f"🔢 Warnings: {count}/{max_warns}\n"
        f"👮 By: {await mention_user(invoker)}",
        parse_mode="Markdown",
    )

    await log_action(
        chat_id, "warn", target.id, target.full_name, invoker.id, invoker.full_name, reason
    )
    await publish_event(
        chat_id,
        "mod_action",
        {
            "action": "warn",
            "target_id": target.id,
            "target_name": target.full_name,
            "warn_count": count,
            "max_warns": max_warns,
            "reason": reason,
            "admin_id": invoker.id,
        },
    )

    if count >= max_warns:
        # Execute warn_action
        if warn_action == "mute":
            await context.bot.restrict_chat_member(
                chat_id, target.id, permissions={"can_send_messages": False}
            )
            await update.message.reply_text(
                f"🔇 {mention} reached max warnings and was muted.", parse_mode="Markdown"
            )
        elif warn_action == "ban":
            await context.bot.ban_chat_member(chat_id, target.id)
            await update.message.reply_text(
                f"🚫 {mention} reached max warnings and was banned.", parse_mode="Markdown"
            )
        elif warn_action == "kick":
            await context.bot.ban_chat_member(chat_id, target.id)
            await context.bot.unban_chat_member(chat_id, target.id)
            await update.message.reply_text(
                f"👢 {mention} reached max warnings and was kicked.", parse_mode="Markdown"
            )
        # Reset warns if reset_on_kick is true
        await db.execute(
            "UPDATE warnings SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
            chat_id,
            target.id,
        )


async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    target, _ = await resolve_target(update, context)
    if not target:
        return

    # Deactivate latest warning
    await db.execute(
        "UPDATE warnings SET is_active = FALSE WHERE id = ("
        "SELECT id FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE "
        "ORDER BY issued_at DESC LIMIT 1)",
        chat_id,
        target.id,
    )

    count = await db.fetchval(
        "SELECT COUNT(*) FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE",
        chat_id,
        target.id,
    )
    await update.message.reply_text(
        f"✅ Warning removed | {await mention_user(target)} ({count} remaining)",
        parse_mode="Markdown",
    )


async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    target, _ = await resolve_target(update, context)
    if not target:
        target = update.effective_user

    history = await db.fetch(
        "SELECT reason, issued_at FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE ORDER BY issued_at DESC",
        chat_id,
        target.id,
    )

    if not history:
        await update.message.reply_text(
            f"✅ No active warnings for {await mention_user(target)}", parse_mode="Markdown"
        )
        return

    text = f"⚠️ Warnings for {await mention_user(target)}: {len(history)}\n\n"
    for i, row in enumerate(history, 1):
        text += f"{i}. Reason: {row['reason']} — {row['issued_at'].strftime('%b %d')}\n"

    await update.message.reply_text(text, parse_mode="Markdown")
