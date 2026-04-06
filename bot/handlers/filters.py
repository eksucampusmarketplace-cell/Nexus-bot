"""
bot/handlers/filters.py

Keyword auto-reply filters management commands:
  /filter <keyword> <response>  — add/update a keyword auto-reply filter
  /filters                      — list all filters for this group
  /stop <keyword>               — remove a filter
  /stopall                      — remove all filters (owner only)
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import get_error, RANK_ADMIN, RANK_OWNER, get_user_rank
from bot.utils.localization import get_locale, get_user_lang
from db.client import db

log = logging.getLogger("[FILTERS]")


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user
    db_pool = context.bot_data.get("db_pool") or context.bot_data.get("db")
    lang = await get_user_lang(db_pool, invoker.id, chat_id)
    locale = get_locale(lang)

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(get_error("no_permission", lang))
        return

    if len(context.args) < 2:
        await update.message.reply_text("❓ Usage: /filter <keyword> <response>")
        return

    keyword = context.args[0].lower().strip()
    reply_content = " ".join(context.args[1:])

    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO filters (chat_id, keyword, reply_content, response) VALUES ($1, $2, $3, $3) "
                "ON CONFLICT (chat_id, keyword) DO UPDATE SET reply_content = EXCLUDED.reply_content, response = EXCLUDED.response",
                chat_id,
                keyword,
                reply_content,
            )
        await update.message.reply_text(f"✅ Filter added: *{keyword}*", parse_mode="Markdown")
        log.info(f"[FILTERS] Added filter '{keyword}' in chat {chat_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to add filter: {e}")


async def filters_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data.get('db_pool') or context.bot_data.get('db')
    lang = await get_user_lang(db_pool, update.effective_user.id, update.effective_chat.id)
    locale = get_locale(lang)
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(get_error("no_permission", lang))
        return

    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT keyword, reply_content FROM filters WHERE chat_id = $1 ORDER BY keyword",
                chat_id,
            )

        if not rows:
            await update.message.reply_text("📋 No filters set for this group.")
            return

        text = f"📋 *Filters in this group ({len(rows)}):*\n\n"
        for row in rows:
            preview = (
                row["reply_content"][:50] + "..."
                if len(row["reply_content"]) > 50
                else row["reply_content"]
            )
            text += f"• `{row['keyword']}` → {preview}\n"

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to fetch filters: {e}")


async def stop_filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data.get('db_pool') or context.bot_data.get('db')
    lang = await get_user_lang(db_pool, update.effective_user.id, update.effective_chat.id)
    locale = get_locale(lang)
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(get_error("no_permission", lang))
        return

    if not context.args:
        await update.message.reply_text("❓ Usage: /stop <keyword>")
        return

    keyword = context.args[0].lower().strip()

    try:
        async with db.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM filters WHERE chat_id = $1 AND keyword = $2",
                chat_id,
                keyword,
            )
        if "DELETE 0" in result:
            await update.message.reply_text(
                f"❌ No filter found for: *{keyword}*", parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"✅ Filter removed: *{keyword}*", parse_mode="Markdown"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to remove filter: {e}")


async def stopall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data.get('db_pool') or context.bot_data.get('db')
    lang = await get_user_lang(db_pool, update.effective_user.id, update.effective_chat.id)
    locale = get_locale(lang)
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_OWNER:
        await update.message.reply_text("❌ Only the group owner can remove all filters.")
        return

    try:
        async with db.pool.acquire() as conn:
            await conn.execute("DELETE FROM filters WHERE chat_id = $1", chat_id)
        await update.message.reply_text("✅ All filters removed.")
        log.info(f"[FILTERS] All filters removed in chat {chat_id} by {invoker.id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to remove filters: {e}")
