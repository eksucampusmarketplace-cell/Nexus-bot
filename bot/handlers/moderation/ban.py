import logging
from datetime import datetime

from telegram import Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import (
    check_permissions,
    get_error,
    log_action,
    mention_user,
    notify_log_channel,
    parse_time,
    publish_event,
    resolve_target,
)
from bot.utils.localization import get_locale, get_user_lang
from db.client import db

log = logging.getLogger("[MOD_BAN]")


async def _check_bot_rights(bot, chat_id: int) -> tuple[bool, str]:
    """Check if the bot has permission to restrict/ban users."""
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if not getattr(bot_member, "can_restrict_members", False):
            return False, (
                "❌ I need **Ban Users** permission to do this.\n"
                "Go to group settings → Administrators → Nexus Bot → enable 'Ban Users'."
            )
        return True, ""
    except Exception:
        # If we can't check, proceed and let Telegram reject it
        return True, ""


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user
    db_pool = context.bot_data.get("db_pool") or context.bot_data.get("db")
    lang = await get_user_lang(db_pool, invoker.id, chat_id)
    locale = get_locale(lang)

    target, reason = await resolve_target(update, context)
    if not target:
        await update.message.reply_text(get_error("no_target", lang))
        return

    allowed, error_key = await check_permissions(context.bot, chat_id, invoker.id, target.id)
    if not allowed:
        await update.message.reply_text(get_error(error_key, lang))
        return

    # Check bot has rights
    has_rights, error_msg = await _check_bot_rights(context.bot, chat_id)
    if not has_rights:
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    reason = reason or "No reason provided"

    try:
        await context.bot.ban_chat_member(chat_id, target.id)

        # Save to DB
        query = """
        INSERT INTO bans (chat_id, user_id, banned_by, reason)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id, user_id) DO UPDATE
        SET banned_by = EXCLUDED.banned_by, reason = EXCLUDED.reason,
            banned_at = NOW(), is_active = TRUE, unban_at = NULL
        """
        await db.execute(query, chat_id, target.id, invoker.id, reason)

        # Log action
        await log_action(
            chat_id, "ban", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )

        # Phase 1: Record signal for ML pipeline
        import asyncio

        from bot.ml.signal_collector import record_mod_action

        asyncio.create_task(record_mod_action(target.id, chat_id, "ban", reason))

        # Update federation reputation (v21)
        try:
            import db.ops.federation as fed_ops

            # Get federations for this group
            feds = await fed_ops.get_group_federations(db.pool, chat_id)
            for fed in feds:
                # Decrease trust score by 30 points for ban
                await fed_ops.update_reputation(
                    db.pool, target.id, fed["id"], -30, f"Banned in group: {reason}"
                )
        except Exception as e:
            log.debug(f"Federation reputation update failed: {e}")

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
            locale.get("ban_confirmed", name=mention, reason=reason),
            parse_mode="HTML",
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

    except Forbidden:
        await update.message.reply_text(
            "❌ Cannot ban — I don't have Ban Users rights.\n"
            "Make me admin with: Ban Users + Delete Messages permissions."
        )
    except BadRequest as e:
        if "CHAT_ADMIN_REQUIRED" in str(e):
            await update.message.reply_text("❌ I need to be an admin first.")
        elif "user_not_found" in str(e).lower() or "USER_NOT_FOUND" in str(e):
            await update.message.reply_text("❌ User not found in this group.")
        else:
            await update.message.reply_text(f"❌ Telegram error: {e}")
    except Exception as e:
        log.error(f"Ban failed unexpectedly: {e}")
        await update.message.reply_text("❌ Unexpected error. Check bot logs.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user
    db_pool = context.bot_data.get("db_pool") or context.bot_data.get("db")
    lang = await get_user_lang(db_pool, invoker.id, chat_id)
    locale = get_locale(lang)

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
                    f"✅ Unbanned user ID `{user_id}`", parse_mode="HTML"
                )
                return
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to unban: {e}")
                return
        await update.message.reply_text(get_error("no_target", lang))
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
    db_pool = context.bot_data.get("db_pool") or context.bot_data.get("db")
    lang = await get_user_lang(db_pool, invoker.id, chat_id)
    locale = get_locale(lang)

    # Usage: /tban [@user|reply] <time> [reason]
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        if not context.args:
            await update.message.reply_text(get_error("invalid_time", lang))
            return
        time_str = context.args[0]
        reason = " ".join(context.args[1:]) or "No reason provided"
    else:
        if len(context.args) < 2:
            await update.message.reply_text(f"❌ Usage: /tban @user <time> [reason]")
            return
        # Use resolve_target for @username support
        # Temporarily remap args so resolve_target sees [target, ...rest]
        original_args = context.args
        context.args = [context.args[0]] + list(context.args[2:])  # skip time
        target, reason = await resolve_target(update, context)
        context.args = original_args  # restore
        time_str = original_args[1]
        reason = reason or "No reason provided"

        if not target:
            await update.message.reply_text(get_error("no_target", lang))
            return

    duration = parse_time(time_str)
    if not duration:
        await update.message.reply_text(get_error("invalid_time", lang))
        return

    allowed, error_key = await check_permissions(context.bot, chat_id, invoker.id, target.id)
    if not allowed:
        await update.message.reply_text(get_error(error_key, lang))
        return

    # Check bot has rights
    has_rights, error_msg = await _check_bot_rights(context.bot, chat_id)
    if not has_rights:
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    from datetime import timezone

    unban_at = datetime.now(timezone.utc) + duration

    try:
        await context.bot.ban_chat_member(chat_id, target.id, until_date=unban_at)

        # Save to DB
        query = """
        INSERT INTO bans (chat_id, user_id, banned_by, reason, unban_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (chat_id, user_id) DO UPDATE
        SET banned_by = EXCLUDED.banned_by, reason = EXCLUDED.reason,
            banned_at = NOW(), is_active = TRUE, unban_at = EXCLUDED.unban_at
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

        # Update federation reputation (v21)
        try:
            import db.ops.federation as fed_ops

            # Get federations for this group
            feds = await fed_ops.get_group_federations(db.pool, chat_id)
            for fed in feds:
                # Decrease trust score by 20 points for temp ban
                await fed_ops.update_reputation(
                    db.pool, target.id, fed["id"], -20, f"Temp banned ({time_str}): {reason}"
                )
        except Exception as e:
            log.debug(f"Federation reputation update failed: {e}")

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
    except Forbidden:
        await update.message.reply_text(
            "❌ Cannot temp-ban — I don't have Ban Users rights.\n"
            "Make me admin with: Ban Users + Delete Messages permissions."
        )
    except BadRequest as e:
        if "CHAT_ADMIN_REQUIRED" in str(e):
            await update.message.reply_text("❌ I need to be an admin first.")
        elif "user_not_found" in str(e).lower() or "USER_NOT_FOUND" in str(e):
            await update.message.reply_text("❌ User not found in this group.")
        else:
            await update.message.reply_text(f"❌ Telegram error: {e}")
    except Exception as e:
        log.error(f"Tban failed unexpectedly: {e}")
        await update.message.reply_text("❌ Unexpected error. Check bot logs.")


async def sban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silent ban - delete command message, no public notification."""
    db_pool = context.bot_data.get('db_pool') or context.bot_data.get('db')
    lang = await get_user_lang(db_pool, update.effective_user.id, update.effective_chat.id)
    locale = get_locale(lang)
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
        import asyncio

        from bot.ml.signal_collector import record_mod_action

        asyncio.create_task(record_mod_action(target.id, chat_id, "ban", reason))

        await log_action(
            chat_id, "sban", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )
        await publish_event(
            chat_id, "mod_action", {"action": "ban", "target_id": target.id, "silent": True}
        )
    except Forbidden:
        log.warning(f"[SBAN] Bot lacks ban rights in chat {chat_id}")
    except BadRequest as e:
        log.debug(f"[SBAN] BadRequest: {e}")
    except Exception as e:
        log.debug(f"[SBAN] Failed: {e}")
