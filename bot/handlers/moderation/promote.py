from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import (
    ERRORS,
    RANK_OWNER,
    check_permissions,
    log_action,
    mention_user,
    publish_event,
    resolve_target,
)
from db.client import db


async def promote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Only owner can promote
    from bot.handlers.moderation.utils import get_user_rank

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_OWNER:
        await update.message.reply_text("❌ Only the group owner can promote members.")
        return

    target, title = await resolve_target(update, context)
    if not target:
        await update.message.reply_text(ERRORS["no_target"])
        return

    try:
        await context.bot.promote_chat_member(
            chat_id,
            target.id,
            can_change_info=False,
            can_post_messages=True,
            can_edit_messages=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_promote_members=False,
        )

        if title:
            try:
                await context.bot.set_chat_administrator_custom_title(
                    chat_id, target.id, title[:16]
                )
                await db.execute(
                    "INSERT INTO admin_titles (chat_id, user_id, title, set_by) VALUES ($1, $2, $3, $4) "
                    "ON CONFLICT (chat_id, user_id) DO UPDATE SET title=EXCLUDED.title",
                    chat_id,
                    target.id,
                    title[:16],
                    invoker.id,
                )
            except Exception:
                pass

        await update.message.reply_text(
            f"⭐ Promoted | {await mention_user(target)}\n"
            f"📛 Title: {title or 'Admin'}\n"
            f"👑 By: {await mention_user(invoker)}",
            parse_mode="Markdown",
        )

        await publish_event(
            chat_id,
            "mod_action",
            {
                "action": "promote",
                "target_id": target.id,
                "target_name": target.full_name,
                "title": title or "Admin",
                "admin_id": invoker.id,
            },
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to promote: {e}")


async def demote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    from bot.handlers.moderation.utils import get_user_rank

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_OWNER:
        return

    target, _ = await resolve_target(update, context)
    if not target:
        return

    try:
        await context.bot.promote_chat_member(
            chat_id,
            target.id,
            can_change_info=False,
            can_post_messages=False,
            can_edit_messages=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_promote_members=False,
        )
        await update.message.reply_text(
            f"📉 Demoted | {await mention_user(target)}", parse_mode="Markdown"
        )
        await publish_event(
            chat_id,
            "mod_action",
            {"action": "demote", "target_id": target.id, "admin_id": invoker.id},
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to demote: {e}")


async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        text = f"👮 Admins in *{update.effective_chat.title}*\n\n"
        for admin in admins:
            status = "Owner" if admin.status == "creator" else "Admin"
            custom_title = admin.custom_title or ""
            text += f"• {await mention_user(admin.user)} — {status} {f'({custom_title})' if custom_title else ''}\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to fetch admins: {e}")


async def title_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_OWNER:
        await update.message.reply_text("❌ Only the group owner can set admin titles.")
        return

    target, title = await resolve_target(update, context)
    if not target:
        await update.message.reply_text(ERRORS["no_target"])
        return

    if not title:
        await update.message.reply_text("❓ Usage: /title @user <title>")
        return

    try:
        await context.bot.set_chat_administrator_custom_title(chat_id, target.id, title[:16])
        await db.execute(
            "INSERT INTO admin_titles (chat_id, user_id, title, set_by) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (chat_id, user_id) DO UPDATE SET title=EXCLUDED.title",
            chat_id, target.id, title[:16], invoker.id,
        )
        await update.message.reply_text(
            f"📛 Title set to *{title[:16]}* for {await mention_user(target)}", parse_mode="Markdown"
        )
        await publish_event(chat_id, "mod_action", {"action": "title", "target_id": target.id, "title": title[:16], "admin_id": invoker.id})
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to set title: {e}")
