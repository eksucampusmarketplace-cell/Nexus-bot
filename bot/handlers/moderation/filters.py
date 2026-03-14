import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank, mention_user
from db.client import db

log = logging.getLogger("[MOD_FILTERS]")


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        await update.message.reply_text("❌ You don't have permission to add filters.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /filter <keyword> <response>\n"
            "Example: /filter hello Hi there! Welcome."
        )
        return

    keyword = context.args[0].lower()
    response = " ".join(context.args[1:])

    count = await db.fetchval(
        "SELECT COUNT(*) FROM filters WHERE chat_id = $1", chat_id
    )
    if count >= 200:
        await update.message.reply_text("❌ Maximum 200 filters reached for this group.")
        return

    await db.execute(
        "INSERT INTO filters (chat_id, keyword, response, added_by) VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (chat_id, keyword) DO UPDATE SET response = EXCLUDED.response",
        chat_id,
        keyword,
        response,
        update.effective_user.id,
    )

    if db.redis:
        await db.redis.delete(f"nexus:filters:{chat_id}")

    await update.message.reply_text(f"✅ Filter added: `{keyword}`", parse_mode="Markdown")


async def filters_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = await db.fetch(
        "SELECT keyword, response FROM filters WHERE chat_id = $1 ORDER BY keyword", chat_id
    )

    if not rows:
        await update.message.reply_text("📋 No filters set for this group.")
        return

    text = f"📋 *Filters in {update.effective_chat.title}*\n\n"
    for row in rows:
        preview = row["response"][:40] + "..." if len(row["response"]) > 40 else row["response"]
        text += f"• `{row['keyword']}` → {preview}\n"
    text += f"\nTotal: {len(rows)} filters"

    await update.message.reply_text(text, parse_mode="Markdown")


async def stop_filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        await update.message.reply_text("❌ You don't have permission to remove filters.")
        return

    if not context.args:
        await update.message.reply_text("❌ Usage: /stop <keyword>")
        return

    keyword = context.args[0].lower()
    result = await db.execute(
        "DELETE FROM filters WHERE chat_id = $1 AND keyword = $2", chat_id, keyword
    )

    if db.redis:
        await db.redis.delete(f"nexus:filters:{chat_id}")

    if "DELETE 0" in str(result):
        await update.message.reply_text(f"❌ No filter found for `{keyword}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"✅ Filter `{keyword}` removed.", parse_mode="Markdown")


async def stopall_filters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    from bot.handlers.moderation.utils import RANK_OWNER
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_OWNER:
        await update.message.reply_text("❌ Only the group owner can remove all filters.")
        return

    await db.execute("DELETE FROM filters WHERE chat_id = $1", chat_id)
    if db.redis:
        await db.redis.delete(f"nexus:filters:{chat_id}")
    await update.message.reply_text("✅ All filters removed.")


async def check_filters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if a message matches any filter and auto-reply.
    Returns True if a filter matched.
    """
    chat_id = update.effective_chat.id
    message = update.effective_message
    if not message or not message.text:
        return False

    text_lower = message.text.lower()

    filters_list = None
    if db.redis:
        import json
        cached = await db.redis.get(f"nexus:filters:{chat_id}")
        if cached:
            try:
                filters_list = json.loads(cached)
            except Exception:
                pass

    if filters_list is None:
        rows = await db.fetch(
            "SELECT keyword, response FROM filters WHERE chat_id = $1", chat_id
        )
        filters_list = [dict(r) for r in rows]
        if db.redis and filters_list:
            import json
            await db.redis.setex(
                f"nexus:filters:{chat_id}", 600, json.dumps(filters_list)
            )

    user = update.effective_user
    for f in filters_list:
        if f["keyword"] in text_lower:
            response = f["response"]
            mention = f"[{user.first_name}](tg://user?id={user.id})"
            response = response.replace("{mention}", mention)
            response = response.replace("{name}", user.first_name or "")
            response = response.replace("{id}", str(user.id))
            response = response.replace(
                "{group}", update.effective_chat.title or ""
            )
            try:
                await message.reply_text(response, parse_mode="Markdown")
            except Exception:
                try:
                    await message.reply_text(response)
                except Exception:
                    pass
            return True

    return False
