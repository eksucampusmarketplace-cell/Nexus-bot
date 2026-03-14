from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank
from db.client import db


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    row = await db.fetchrow("SELECT rules_text FROM group_rules WHERE chat_id = $1", chat_id)
    if not row or not row["rules_text"]:
        await update.message.reply_text("📜 No rules set for this group.")
        return

    await update.message.reply_text(
        f"📜 *Rules of {update.effective_chat.title}*\n\n{row['rules_text']}", parse_mode="Markdown"
    )


async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        return

    rules_text = ""
    if update.message.reply_to_message:
        rules_text = update.message.reply_to_message.text
    elif context.args:
        rules_text = " ".join(context.args)
    else:
        await update.message.reply_text("❌ Provide rules text or reply to a message.")
        return

    await db.execute(
        "INSERT INTO group_rules (chat_id, rules_text, updated_by) VALUES ($1, $2, $3) "
        "ON CONFLICT (chat_id) DO UPDATE SET rules_text=EXCLUDED.rules_text, updated_by=EXCLUDED.updated_by, updated_at=NOW()",
        chat_id,
        rules_text,
        update.effective_user.id,
    )
    await update.message.reply_text("✅ Group rules updated.")


async def clearrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        return
    await db.execute("DELETE FROM group_rules WHERE chat_id = $1", chat_id)
    await update.message.reply_text("✅ Group rules cleared.")
