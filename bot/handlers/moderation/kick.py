import logging

from telegram import Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import (
    check_permissions,
    get_error,
    log_action,
    mention_user,
    publish_event,
    resolve_target,
)
from bot.utils.localization import get_locale, get_user_lang

log = logging.getLogger("[MOD_KICK]")


async def _check_bot_rights(bot, chat_id: int) -> tuple[bool, str]:
    """Check if the bot has permission to restrict/ban users (needed for kick)."""
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if not getattr(bot_member, "can_restrict_members", False):
            return False, (
                "❌ I need **Ban Users** permission to kick.\n"
                "Go to group settings → Administrators → Nexus Bot → enable 'Ban Users'."
            )
        return True, ""
    except Exception:
        return True, ""


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await context.bot.unban_chat_member(chat_id, target.id)

        await log_action(
            chat_id, "kick", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )

        # Update federation reputation (v21)
        try:
            from db.client import db
            import db.ops.federation as fed_ops

            # Get federations for this group
            feds = await fed_ops.get_group_federations(db.pool, chat_id)
            for fed in feds:
                # Decrease trust score by 15 points for kick
                await fed_ops.update_reputation(
                    db.pool, target.id, fed["id"], -15, f"Kicked from group: {reason}"
                )
        except Exception as e:
            log.debug(f"Federation reputation update failed: {e}")

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
    except Forbidden:
        await update.message.reply_text(
            "❌ Cannot kick — I don't have Ban Users rights.\n"
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
        log.error(f"Kick failed unexpectedly: {e}")
        await update.message.reply_text("❌ Unexpected error. Check bot logs.")


async def skick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data.get('db_pool') or context.bot_data.get('db')
    lang = await get_user_lang(db_pool, update.effective_user.id, update.effective_chat.id)
    locale = get_locale(lang)
    chat_id = update.effective_chat.id
    invoker = update.effective_user
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
        await context.bot.unban_chat_member(chat_id, target.id)
        if update.message.reply_to_message:
            try:
                await update.message.reply_to_message.delete()
            except Exception:
                pass
        try:
            await update.message.delete()
        except Exception:
            pass
        await log_action(
            chat_id, "skick", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "skick",
                "target_id": target.id,
                "target_name": target.full_name,
                "admin_id": invoker.id,
                "reason": reason,
            },
        )
    except Forbidden:
        log.warning(f"[SKICK] Bot lacks ban rights in chat {chat_id}")
    except BadRequest as e:
        log.debug(f"[SKICK] BadRequest: {e}")
    except Exception as e:
        log.debug(f"[SKICK] Failed: {e}")
