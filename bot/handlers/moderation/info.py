from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import mention_user, resolve_target
from db.client import db


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    target, _ = await resolve_target(update, context)
    if not target:
        target = update.effective_user

    # Get stats from DB
    warn_count = await db.fetchval(
        "SELECT COUNT(*) FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE",
        chat_id,
        target.id,
    )
    is_muted = await db.fetchval(
        "SELECT EXISTS(SELECT 1 FROM mutes WHERE chat_id = $1 AND user_id = $2 "
        "AND is_active = TRUE)",
        chat_id,
        target.id,
    )

    try:
        member = await context.bot.get_chat_member(chat_id, target.id)
        status = member.status.capitalize()
    except Exception:
        status = "Unknown"

    text = "👤 *User Information*\n\n"
    text += f"🪪 Name: {target.full_name}\n"
    text += f"👤 Username: @{target.username if target.username else 'None'}\n"
    text += f"🔢 ID: `{target.id}`\n"
    text += f"🔗 Link: [User Link](tg://user?id={target.id})\n\n"

    text += "📊 *In this group:*\n"
    text += f"├ Status: {status}\n"
    text += f"├ Warnings: {warn_count}/3\n"
    text += f"└ Muted: {'Yes' if is_muted else 'No'}\n\n"
    text += "📜 Use `/history` to see full moderation history."

    await update.message.reply_text(text, parse_mode="Markdown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    target, _ = await resolve_target(update, context)
    if not target:
        target = update.effective_user

    # Fetch last 15 moderation actions for this user in this chat
    history = await db.fetch(
        "SELECT action, admin_name, reason, duration, done_at FROM mod_logs "
        "WHERE chat_id = $1 AND target_id = $2 "
        "ORDER BY done_at DESC LIMIT 15",
        chat_id,
        target.id,
    )

    if not history:
        await update.message.reply_text(
            f"✅ No moderation history for {await mention_user(target)}", parse_mode="Markdown"
        )
        return

    text = f"📜 *Moderation History for* {await mention_user(target)}:\n\n"
    for i, row in enumerate(history, 1):
        action = row["action"].upper()
        admin = row["admin_name"] or "Unknown Admin"
        reason = row["reason"] or "No reason"
        date = row["done_at"].strftime("%b %d, %H:%M")

        text += f"{i}. *{action}* — {date}\n"
        text += f"   └ 👮 {admin} | 📋 {reason}\n"
        if row["duration"]:
            text += f"   └ ⏱ Duration: {row['duration']}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target, _ = await resolve_target(update, context)
    if not target:
        target = update.effective_user

    await update.message.reply_text(
        f"👤 @{target.username if target.username else target.first_name} — ID: `{target.id}`\n"
        f"💬 This group — ID: `{update.effective_chat.id}`",
        parse_mode="Markdown",
    )
