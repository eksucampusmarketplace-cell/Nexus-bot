import logging
from datetime import datetime

from telegram import ChatPermissions, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import (
    check_permissions,
    get_error,
    log_action,
    mention_user,
    parse_time,
    publish_event,
    resolve_target,
)
from bot.utils.localization import get_locale, get_user_lang
from db.client import db

log = logging.getLogger("[MOD_MUTE]")

# PTB version compatibility for ChatPermissions - import after telegram
from telegram import __version__ as PTB_VERSION  # noqa: E402

PTB_MAJOR = int(PTB_VERSION.split(".")[0])


def _get_unmute_permissions():
    """Get the correct ChatPermissions for unmuting based on PTB version."""
    if PTB_MAJOR >= 21:
        return ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
        )
    else:
        return ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )


def _get_restrict_permissions():
    """Get the correct ChatPermissions for restricting media based on PTB version."""
    if PTB_MAJOR >= 21:
        return ChatPermissions(
            can_send_messages=True,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
        )
    else:
        return ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )


async def _check_bot_rights(bot, chat_id: int) -> tuple[bool, str]:
    """Check if the bot has permission to restrict users."""
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if not getattr(bot_member, "can_restrict_members", False):
            return False, (
                "❌ I need **Restrict Users** permission to do this.\n"
                "Go to group settings → Administrators → Nexus Bot → enable 'Restrict Users'."
            )
        return True, ""
    except Exception:
        return True, ""


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await context.bot.restrict_chat_member(
            chat_id, target.id, permissions=ChatPermissions(can_send_messages=False)
        )

        # Save to DB
        query = """
        INSERT INTO mutes (chat_id, user_id, muted_by, reason)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id, user_id) DO UPDATE
        SET muted_by = EXCLUDED.muted_by, reason = EXCLUDED.reason,
            muted_at = NOW(), is_active = TRUE, unmute_at = NULL
        """
        await db.execute(query, chat_id, target.id, invoker.id, reason)

        await log_action(
            chat_id, "mute", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )

        # Update federation reputation (v21)
        try:
            import db.ops.federation as fed_ops

            # Get federations for this group
            feds = await fed_ops.get_group_federations(db.pool, chat_id)
            for fed in feds:
                # Decrease trust score by 10 points for mute
                await fed_ops.update_reputation(
                    db.pool, target.id, fed["id"], -10, f"Muted in group: {reason}"
                )
        except Exception as e:
            log.debug(f"Federation reputation update failed: {e}")

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
    except Forbidden:
        await update.message.reply_text(
            "❌ Cannot mute — I don't have Restrict Users rights.\n"
            "Make me admin with: Restrict Users permission."
        )
    except BadRequest as e:
        if "CHAT_ADMIN_REQUIRED" in str(e):
            await update.message.reply_text("❌ I need to be an admin first.")
        elif "user_not_found" in str(e).lower() or "USER_NOT_FOUND" in str(e):
            await update.message.reply_text("❌ User not found in this group.")
        else:
            await update.message.reply_text(f"❌ Telegram error: {e}")
    except Exception as e:
        log.error(f"Mute failed unexpectedly: {e}")
        await update.message.reply_text("❌ Unexpected error. Check bot logs.")


async def tmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data.get('db_pool') or context.bot_data.get('db')
    lang = await get_user_lang(db_pool, update.effective_user.id, update.effective_chat.id)
    locale = get_locale(lang)
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

    # Check bot has rights
    has_rights, error_msg = await _check_bot_rights(context.bot, chat_id)
    if not has_rights:
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    from datetime import timezone

    unmute_at = datetime.now(timezone.utc) + duration

    try:
        await context.bot.restrict_chat_member(
            chat_id,
            target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=unmute_at,
        )

        await db.execute(
            "INSERT INTO mutes (chat_id, user_id, muted_by, reason, unmute_at) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (chat_id, user_id) DO UPDATE "
            "SET muted_by=EXCLUDED.muted_by, reason=EXCLUDED.reason, "
            "is_active=TRUE, unmute_at=EXCLUDED.unmute_at",
            chat_id,
            target.id,
            invoker.id,
            reason,
            unmute_at,
        )

        # Update federation reputation (v21)
        try:
            import db.ops.federation as fed_ops

            # Get federations for this group
            feds = await fed_ops.get_group_federations(db.pool, chat_id)
            for fed in feds:
                # Decrease trust score by 8 points for temp mute
                await fed_ops.update_reputation(
                    db.pool, target.id, fed["id"], -8, f"Temp muted ({time_str}): {reason}"
                )
        except Exception as e:
            log.debug(f"Federation reputation update failed: {e}")

        await update.message.reply_text(
            f"🔇 Temp Muted | {await mention_user(target)}\n"
            f"⏱ Duration: {time_str}\n"
            f"📋 Reason: {reason}\n"
            f"👮 By: {await mention_user(invoker)}",
            parse_mode="Markdown",
        )
    except Forbidden:
        await update.message.reply_text(
            "❌ Cannot temp-mute — I don't have Restrict Users rights.\n"
            "Make me admin with: Restrict Users permission."
        )
    except BadRequest as e:
        if "CHAT_ADMIN_REQUIRED" in str(e):
            await update.message.reply_text("❌ I need to be an admin first.")
        elif "user_not_found" in str(e).lower() or "USER_NOT_FOUND" in str(e):
            await update.message.reply_text("❌ User not found in this group.")
        else:
            await update.message.reply_text(f"❌ Telegram error: {e}")
    except Exception as e:
        log.error(f"Tmute failed unexpectedly: {e}")
        await update.message.reply_text("❌ Unexpected error. Check bot logs.")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data.get('db_pool') or context.bot_data.get('db')
    lang = await get_user_lang(db_pool, update.effective_user.id, update.effective_chat.id)
    locale = get_locale(lang)
    chat_id = update.effective_chat.id
    target, _ = await resolve_target(update, context)

    if not target:
        await update.message.reply_text(get_error("no_target", lang))
        return

    # Check bot has rights
    has_rights, error_msg = await _check_bot_rights(context.bot, chat_id)
    if not has_rights:
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id,
            target.id,
            permissions=_get_unmute_permissions(),
        )
        await db.execute(
            "UPDATE mutes SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
            chat_id,
            target.id,
        )
        await update.message.reply_text(
            f"✅ Unmuted | {await mention_user(target)}", parse_mode="Markdown"
        )
    except Forbidden:
        await update.message.reply_text(
            "❌ Cannot unmute — I don't have Restrict Users rights.\n"
            "Make me admin with: Restrict Users permission."
        )
    except BadRequest as e:
        if "CHAT_ADMIN_REQUIRED" in str(e):
            await update.message.reply_text("❌ I need to be an admin first.")
        else:
            await update.message.reply_text(f"❌ Telegram error: {e}")
    except Exception as e:
        log.error(f"Unmute failed unexpectedly: {e}")
        await update.message.reply_text("❌ Unexpected error. Check bot logs.")


async def smute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await context.bot.restrict_chat_member(
            chat_id, target.id, permissions=ChatPermissions(can_send_messages=False)
        )
        if update.message.reply_to_message:
            try:
                await update.message.reply_to_message.delete()
            except Exception:
                pass
        try:
            await update.message.delete()
        except Exception:
            pass

        await db.execute(
            "INSERT INTO mutes (chat_id, user_id, muted_by, reason) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT (chat_id, user_id) DO UPDATE "
            "SET muted_by=EXCLUDED.muted_by, reason=EXCLUDED.reason, "
            "muted_at=NOW(), is_active=TRUE, unmute_at=NULL",
            chat_id,
            target.id,
            invoker.id,
            reason,
        )
        await log_action(
            chat_id, "smute", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "smute",
                "target_id": target.id,
                "target_name": target.full_name,
                "admin_id": invoker.id,
                "reason": reason,
            },
        )
    except Forbidden:
        log.warning(f"[SMUTE] Bot lacks restrict rights in chat {chat_id}")
    except BadRequest as e:
        log.debug(f"[SMUTE] BadRequest: {e}")
    except Exception as e:
        log.debug(f"[SMUTE] Failed: {e}")


async def restrict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await context.bot.restrict_chat_member(
            chat_id,
            target.id,
            permissions=_get_restrict_permissions(),
        )
        await update.message.reply_text(
            f"🔒 Restricted | {await mention_user(target)}\n"
            f"📋 Reason: {reason}\n"
            f"👮 By: {await mention_user(invoker)}",
            parse_mode="Markdown",
        )
        await log_action(
            chat_id, "restrict", target.id, target.full_name, invoker.id, invoker.full_name, reason
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "restrict",
                "target_id": target.id,
                "target_name": target.full_name,
                "admin_id": invoker.id,
                "reason": reason,
            },
        )
    except Forbidden:
        await update.message.reply_text(
            "❌ Cannot restrict — I don't have Restrict Users rights.\n"
            "Make me admin with: Restrict Users permission."
        )
    except BadRequest as e:
        if "CHAT_ADMIN_REQUIRED" in str(e):
            await update.message.reply_text("❌ I need to be an admin first.")
        else:
            await update.message.reply_text(f"❌ Telegram error: {e}")
    except Exception as e:
        log.error(f"Restrict failed unexpectedly: {e}")
        await update.message.reply_text("❌ Unexpected error. Check bot logs.")


async def unrestrict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data.get('db_pool') or context.bot_data.get('db')
    lang = await get_user_lang(db_pool, update.effective_user.id, update.effective_chat.id)
    locale = get_locale(lang)
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    target, _ = await resolve_target(update, context)
    if not target:
        await update.message.reply_text(get_error("no_target", lang))
        return

    # Check bot has rights
    has_rights, error_msg = await _check_bot_rights(context.bot, chat_id)
    if not has_rights:
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id,
            target.id,
            permissions=_get_unmute_permissions(),
        )
        await update.message.reply_text(
            f"🔓 Unrestricted | {await mention_user(target)}", parse_mode="Markdown"
        )
        await log_action(
            chat_id,
            "unrestrict",
            target.id,
            target.full_name,
            invoker.id,
            invoker.full_name,
            "Unrestricted",
        )
        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "unrestrict",
                "target_id": target.id,
                "target_name": target.full_name,
                "admin_id": invoker.id,
            },
        )
    except Forbidden:
        await update.message.reply_text(
            "❌ Cannot unrestrict — I don't have Restrict Users rights.\n"
            "Make me admin with: Restrict Users permission."
        )
    except BadRequest as e:
        if "CHAT_ADMIN_REQUIRED" in str(e):
            await update.message.reply_text("❌ I need to be an admin first.")
        else:
            await update.message.reply_text(f"❌ Telegram error: {e}")
    except Exception as e:
        log.error(f"Unrestrict failed unexpectedly: {e}")
        await update.message.reply_text("❌ Unexpected error. Check bot logs.")
