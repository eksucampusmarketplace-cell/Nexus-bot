"""
bot/handlers/approval.py

Member approval system.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from db.ops.approval import add_approved_member, get_approved_members, remove_approved_member

log = logging.getLogger("approval")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    target = await _resolve_target(update, context)
    if not target:
        await msg.reply_text("Usage: /approve @username or reply to a user's message")
        return

    await add_approved_member(db, chat.id, target.id, approved_by=update.effective_user.id)

    # Also unrestrict the user if they were restricted (e.g. by CAPTCHA)
    try:
        from bot.handlers.moderation.mute import _get_unmute_permissions

        await context.bot.restrict_chat_member(
            chat.id, target.id, permissions=_get_unmute_permissions()
        )
        # Check for pending CAPTCHA and clean up
        from db.ops.captcha import get_pending_challenge, mark_challenge_passed

        challenge = await get_pending_challenge(db, chat.id, target.id)
        if challenge:
            await mark_challenge_passed(db, challenge["challenge_id"])
            try:
                await context.bot.delete_message(chat.id, challenge["message_id"])
            except Exception:
                pass

        # Clean up Member Booster and Channel Gate if applicable
        try:
            from db.ops.booster import grant_access, set_channel_verified

            await grant_access(chat.id, target.id)
            await set_channel_verified(chat.id, target.id)
        except Exception:
            pass

        # Clear any active mute in DB
        try:
            await db.execute(
                "UPDATE mutes SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
                chat.id,
                target.id,
            )
        except Exception:
            pass
    except Exception as e:
        log.debug(f"Failed to unrestrict on approve: {e}")

    name = f"@{target.username}" if target.username else target.full_name
    await msg.reply_text(
        f"✅ <b>{name}</b> is now approved.\n" f"They will bypass all automod rules.",
        parse_mode="HTML",
    )
    log.info(
        f"[APPROVAL] Approved | chat={chat.id} user={target.id} " f"by={update.effective_user.id}"
    )


async def cmd_unapprove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    target = await _resolve_target(update, context)
    if not target:
        await msg.reply_text("Usage: /unapprove @username or reply to a user's message")
        return

    await remove_approved_member(db, chat.id, target.id)

    name = f"@{target.username}" if target.username else target.full_name
    await msg.reply_text(f"✅ <b>{name}</b> approval removed.", parse_mode="HTML")
    log.info(f"[APPROVAL] Unapproved | chat={chat.id} user={target.id}")


async def cmd_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    members = await get_approved_members(db, chat.id)
    if not members:
        await msg.reply_text("No approved members in this group.")
        return

    lines = []
    for m in members[:50]:  # max 50 in message
        name = f"@{m['username']}" if m.get("username") else str(m["user_id"])
        lines.append(f"• {name}")

    text = f"✅ <b>Approved Members ({len(members)}):</b>\n\n"
    text += "\n".join(lines)
    if len(members) > 50:
        text += f"\n\n...and {len(members) - 50} more (see Mini App)"

    await msg.reply_text(text, parse_mode="HTML")


async def _resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get target user from reply or @mention in args."""
    msg = update.effective_message

    # From reply
    if msg.reply_to_message:
        return msg.reply_to_message.from_user

    # From args (@username)
    if context.args:
        username = context.args[0].lstrip("@")
        try:
            # Note: This requires the user to be known to the bot or cached.
            # In some cases, bot might not be able to get_chat_member by username if not admin.
            # But we try.
            chat_member = await context.bot.get_chat_member(
                update.effective_chat.id, f"@{username}"
            )
            return chat_member.user
        except Exception:
            pass

    return None


# ── Anti-raid commands ─────────────────────────────────────────────────────


async def cmd_antiraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")
    args = context.args or []

    get_settings = context.bot_data.get("get_settings")
    if not get_settings:
        # Fallback if get_settings is not in bot_data
        from db.ops.automod import get_group_settings

        settings = await get_group_settings(db, chat.id)
    else:
        settings = await get_settings(chat.id)

    from bot.antiraid.engine import manual_toggle_raid
    from db.ops.antiraid import get_active_session

    if not args or args[0] == "status":
        session = await get_active_session(db, chat.id)
        if session:
            await msg.reply_text(
                f"🚨 <b>Anti-raid: ACTIVE</b>\n"
                f"Triggered: {session['triggered_by']}\n"
                f"Joins blocked: {session['join_count']}\n"
                f"Ends: {session['ends_at'] or 'Manual unlock required'}",
                parse_mode="HTML",
            )
        else:
            status = "enabled" if settings.get("auto_antiraid_enabled") else "disabled"
            await msg.reply_text(
                f"🛡 Anti-raid: Inactive\n"
                f"Auto-antiraid: {status}\n"
                f"Threshold: {settings.get('auto_antiraid_threshold', 15)} joins/min"
            )
        return

    if args[0] == "on":
        result = await manual_toggle_raid(
            context.bot, chat.id, True, settings, db, update.effective_user.id
        )
        await msg.reply_text(result)

    elif args[0] == "off":
        result = await manual_toggle_raid(
            context.bot, chat.id, False, settings, db, update.effective_user.id
        )
        await msg.reply_text(result)


async def cmd_autoantiraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")
    args = context.args or []

    from db.ops.automod import update_group_setting

    if not args:
        await msg.reply_text(
            "/autoantiraid on [threshold]\n"
            "/autoantiraid off\n"
            "/autoantiraid mode restrict|ban|captcha\n"
            "/autoantiraid duration 30\n"
            "/autoantiraid 20  (set threshold)"
        )
        return

    if args[0] == "on":
        await update_group_setting(db, chat.id, "auto_antiraid_enabled", True)
        if len(args) > 1 and args[1].isdigit():
            await update_group_setting(db, chat.id, "auto_antiraid_threshold", int(args[1]))
        await msg.reply_text("✅ Auto anti-raid enabled")

    elif args[0] == "off":
        await update_group_setting(db, chat.id, "auto_antiraid_enabled", False)
        await msg.reply_text("✅ Auto anti-raid disabled")

    elif args[0] == "mode" and len(args) > 1:
        mode = args[1].lower()
        if mode in ("restrict", "ban", "captcha"):
            await update_group_setting(db, chat.id, "antiraid_mode", mode)
            await msg.reply_text(f"✅ Anti-raid mode: {mode}")
        else:
            await msg.reply_text("Modes: restrict | ban | captcha")

    elif args[0] == "duration" and len(args) > 1 and args[1].isdigit():
        await update_group_setting(db, chat.id, "antiraid_duration_mins", int(args[1]))
        await msg.reply_text(
            f"✅ Raid auto-ends after {args[1]} min"
            + (" (manual unlock)" if args[1] == "0" else "")
        )

    elif args[0].isdigit():
        await update_group_setting(db, chat.id, "auto_antiraid_threshold", int(args[0]))
        await msg.reply_text(f"✅ Anti-raid threshold: {args[0]} joins/min")


async def cmd_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")
    args = context.args or []

    from db.ops.automod import update_group_setting

    if not args:
        get_settings = context.bot_data.get("get_settings")
        if not get_settings:
            from db.ops.automod import get_group_settings

            settings = await get_group_settings(db, chat.id)
        else:
            settings = await get_settings(chat.id)

        mode = settings.get("captcha_mode", "button")
        enabled = settings.get("captcha_enabled", False)
        timeout = settings.get("captcha_timeout_mins", 5)
        await msg.reply_text(
            f"🤖 <b>CAPTCHA Status</b>\n"
            f"Enabled: {'✅' if enabled else '❌'}\n"
            f"Mode: {mode}\n"
            f"Timeout: {timeout} min",
            parse_mode="HTML",
        )
        return

    if args[0] == "on":
        await update_group_setting(db, chat.id, "captcha_enabled", True)
        await msg.reply_text("✅ CAPTCHA enabled for new members")
    elif args[0] == "off":
        await update_group_setting(db, chat.id, "captcha_enabled", False)
        await msg.reply_text("✅ CAPTCHA disabled")


async def cmd_captchamode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")
    args = context.args or []

    from db.ops.automod import update_group_setting

    if not args:
        await msg.reply_text(
            "Usage:\n"
            "/captchamode button\n"
            "/captchamode math\n"
            "/captchamode text\n"
            "/captchamode timeout 5"
        )
        return

    if args[0] in ("button", "math", "text"):
        await update_group_setting(db, chat.id, "captcha_mode", args[0])
        await msg.reply_text(f"✅ CAPTCHA mode: {args[0]}")

    elif args[0] == "timeout" and len(args) > 1 and args[1].isdigit():
        await update_group_setting(db, chat.id, "captcha_timeout_mins", int(args[1]))
        await msg.reply_text(f"✅ CAPTCHA timeout: {args[1]} min")
