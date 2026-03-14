import logging
from datetime import datetime

from telegram import Update
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

log = logging.getLogger("[MOD_BAN]")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        # Save to DB
        query = """
        INSERT INTO bans (chat_id, user_id, banned_by, reason)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id, user_id) DO UPDATE 
        SET banned_by = EXCLUDED.banned_by, reason = EXCLUDED.reason, banned_at = NOW(), is_active = TRUE, unban_at = NULL
        """
        await db.execute(query, chat_id, target.id, invoker.id, reason)

        # Log action
        await log_action(
            chat_id, "ban", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )

        # Notify log channel
        await notify_log_channel(context.bot, chat_id, "ban", target, invoker, reason)

        # Publish event
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "ban",
                "target_id": target.id,
                "target_name": target.full_name,
                "target_username": target.username,
                "admin_id": invoker.id,
                "admin_name": invoker.full_name,
                "reason": reason,
                "duration": "permanent",
            },
        )

        # Success message
        mention = await mention_user(target)
        await update.message.reply_text(
            f"✅ Banned | {mention}\n"
            f"📋 Reason: {reason}\n"
            f"👮 By: {await mention_user(invoker)}",
            parse_mode="Markdown",
        )

        # Try to DM user
        try:
            await context.bot.send_message(
                target.id,
                f"🚫 You were banned from *{update.effective_chat.title}*\n" f"📋 Reason: {reason}",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    except Exception as e:
        log.error(f"Ban failed: {e}")
        await update.message.reply_text(f"❌ Failed to ban user: {str(e)}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    target, reason = await resolve_target(update, context)
    if not target:
        # Check if we have an ID in args
        if context.args and context.args[0].isdigit():
            user_id = int(context.args[0])
            # Need a user object for logging, but we might not have it.
            # We'll just use the ID.
            try:
                await context.bot.unban_chat_member(chat_id, user_id)
                await db.execute(
                    "UPDATE bans SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
                    chat_id,
                    user_id,
                )
                await update.message.reply_text(
                    f"✅ Unbanned user ID `{user_id}`", parse_mode="Markdown"
                )
                return
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to unban: {e}")
                return
        await update.message.reply_text(ERRORS["no_target"])
        return

    try:
        await context.bot.unban_chat_member(chat_id, target.id)
        await db.execute(
            "UPDATE bans SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
            chat_id,
            target.id,
        )

        # Log action
        await log_action(
            chat_id,
            "unban",
            target.id,
            target.full_name,
            invoker.id,
            invoker.full_name,
            "Manual unban",
        )

        # Publish event
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "unban",
                "target_id": target.id,
                "target_name": target.full_name,
                "target_username": target.username,
                "admin_id": invoker.id,
                "admin_name": invoker.full_name,
            },
        )

        await update.message.reply_text(
            f"✅ Unbanned | {await mention_user(target)}", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unban: {e}")


async def tban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Usage: /tban [@user|reply] <time> [reason]
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        if not context.args:
            await update.message.reply_text("❌ Please specify duration (e.g. 1h, 1d)")
            return
        time_str = context.args[0]
        reason = " ".join(context.args[1:]) or "No reason provided"
    else:
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: /tban @user <time> [reason]")
            return
        # Resolve target from first arg
        # This is a bit complex because resolve_target expects args to be [target, reason...]
        # Here it is [target, time, reason...]
        # I'll manually handle it
        target_str = context.args[0]
        time_str = context.args[1]
        reason = " ".join(context.args[2:]) or "No reason provided"

        try:
            if target_str.isdigit():
                member = await context.bot.get_chat_member(chat_id, int(target_str))
                target = member.user
            elif target_str.startswith("@"):
                # Still hard to resolve username to user object without more context
                await update.message.reply_text("❌ Mention the user or use their ID.")
                return
            else:
                await update.message.reply_text("❌ Invalid target.")
                return
        except Exception:
            await update.message.reply_text("❌ User not found.")
            return

    duration = parse_time(time_str)
    if not duration:
        await update.message.reply_text(ERRORS["invalid_time"])
        return

    allowed, error_key = await check_permissions(context.bot, chat_id, invoker.id, target.id)
    if not allowed:
        await update.message.reply_text(ERRORS.get(error_key, "Permission denied."))
        return

    unban_at = datetime.utcnow() + duration

    try:
        await context.bot.ban_chat_member(chat_id, target.id, until_date=unban_at)

        # Save to DB
        query = """
        INSERT INTO bans (chat_id, user_id, banned_by, reason, unban_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (chat_id, user_id) DO UPDATE 
        SET banned_by = EXCLUDED.banned_by, reason = EXCLUDED.reason, banned_at = NOW(), is_active = TRUE, unban_at = EXCLUDED.unban_at
        """
        await db.execute(query, chat_id, target.id, invoker.id, reason, unban_at)

        # Log action
        await log_action(
            chat_id,
            "tban",
            target.id,
            target.full_name,
            invoker.id,
            invoker.full_name,
            reason,
            time_str,
        )

        # Publish event
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "tban",
                "target_id": target.id,
                "target_name": target.full_name,
                "reason": reason,
                "duration": time_str,
                "admin_id": invoker.id,
            },
        )

        mention = await mention_user(target)
        await update.message.reply_text(
            f"✅ Temp Banned | {mention}\n"
            f"⏱ Duration: {time_str}\n"
            f"📋 Reason: {reason}\n"
            f"👮 By: {await mention_user(invoker)}\n"
            f"Unban time: {unban_at.strftime('%Y-%m-%d %H:%M')} UTC",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to tban: {e}")


async def sban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silent ban - delete command message, no public notification."""
    # Similar to ban, but deletes messages
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    target, reason = await resolve_target(update, context)
    if not target:
        return

    allowed, error_key = await check_permissions(context.bot, chat_id, invoker.id, target.id)
    if not allowed:
        return

    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        await update.message.delete()
        # Still log and publish event
        await log_action(
            chat_id, "sban", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )
        await publish_event(
            chat_id, "mod_action", {"action": "ban", "target_id": target.id, "silent": True}
        )
    except Exception:
        pass
