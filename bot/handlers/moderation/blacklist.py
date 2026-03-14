import logging

from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank
from db.client import db

log = logging.getLogger("[MOD_BLACKLIST]")

VALID_ACTIONS = ["delete", "warn", "mute", "kick", "ban"]


async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        await update.message.reply_text("❌ You don't have permission to manage the blacklist.")
        return

    if not context.args:
        rows = await db.fetch(
            "SELECT word, action FROM blacklist WHERE chat_id = $1 ORDER BY word", chat_id
        )
        if not rows:
            await update.message.reply_text("🚫 No blacklisted words in this group.")
            return

        text = f"🚫 *Blacklist in {update.effective_chat.title}*\n\n"
        for row in rows:
            text += f"• `{row['word']}` — {row['action']}\n"
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    word = context.args[0].lower()
    action = context.args[1].lower() if len(context.args) > 1 else "delete"

    if action not in VALID_ACTIONS:
        await update.message.reply_text(
            f"❌ Invalid action. Valid: {', '.join(VALID_ACTIONS)}"
        )
        return

    await db.execute(
        "INSERT INTO blacklist (chat_id, word, action, added_by) VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (chat_id, word) DO UPDATE SET action = EXCLUDED.action",
        chat_id,
        word,
        action,
        update.effective_user.id,
    )

    if db.redis:
        await db.redis.delete(f"nexus:blacklist:{chat_id}")

    await update.message.reply_text(
        f"✅ Added `{word}` to blacklist (action: {action})", parse_mode="Markdown"
    )


async def unblacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        await update.message.reply_text("❌ You don't have permission to manage the blacklist.")
        return

    if not context.args:
        await update.message.reply_text("❌ Usage: /unblacklist <word>")
        return

    word = context.args[0].lower()
    await db.execute(
        "DELETE FROM blacklist WHERE chat_id = $1 AND word = $2", chat_id, word
    )

    if db.redis:
        await db.redis.delete(f"nexus:blacklist:{chat_id}")

    await update.message.reply_text(f"✅ `{word}` removed from blacklist.", parse_mode="Markdown")


async def blacklistmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await get_user_rank(context.bot, chat_id, update.effective_user.id) < RANK_ADMIN:
        return

    if not context.args or context.args[0].lower() not in VALID_ACTIONS:
        await update.message.reply_text(
            f"❌ Usage: /blacklistmode <action>\nValid: {', '.join(VALID_ACTIONS)}"
        )
        return

    mode = context.args[0].lower()
    await db.execute(
        "UPDATE blacklist SET action = $1 WHERE chat_id = $2", mode, chat_id
    )

    if db.redis:
        await db.redis.delete(f"nexus:blacklist:{chat_id}")

    await update.message.reply_text(f"✅ Blacklist mode set to: **{mode}**", parse_mode="Markdown")


async def check_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check message against blacklist.
    Returns True if a blacklisted word was found and action was taken.
    """
    chat_id = update.effective_chat.id
    message = update.effective_message
    if not message or not message.text:
        return False

    text_lower = message.text.lower()

    blacklist_data = None
    if db.redis:
        import json
        cached = await db.redis.get(f"nexus:blacklist:{chat_id}")
        if cached:
            try:
                blacklist_data = json.loads(cached)
            except Exception:
                pass

    if blacklist_data is None:
        rows = await db.fetch(
            "SELECT word, action FROM blacklist WHERE chat_id = $1", chat_id
        )
        blacklist_data = [dict(r) for r in rows]
        if db.redis and blacklist_data:
            import json
            await db.redis.setex(
                f"nexus:blacklist:{chat_id}", 600, json.dumps(blacklist_data)
            )

    user = update.effective_user
    for entry in blacklist_data:
        word = entry["word"]
        import re as _re
        pattern = word.replace("*", ".*")
        if _re.search(pattern, text_lower):
            action = entry.get("action", "delete")
            try:
                await message.delete()
            except Exception:
                pass

            if action == "warn":
                warn_count = await db.fetchval(
                    "SELECT COUNT(*) FROM warnings WHERE chat_id = $1 AND user_id = $2 AND is_active = TRUE",
                    chat_id,
                    user.id,
                )
                await db.execute(
                    "INSERT INTO warnings (chat_id, user_id, reason, issued_by) VALUES ($1, $2, $3, $4)",
                    chat_id,
                    user.id,
                    f"Blacklisted word: {word}",
                    context.bot.id,
                )
                try:
                    await context.bot.send_message(
                        user.id,
                        f"⚠️ Your message was removed in *{update.effective_chat.title}* "
                        f"for containing a blacklisted word.",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

            elif action == "mute":
                try:
                    await context.bot.restrict_chat_member(
                        chat_id,
                        user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                    )
                except Exception:
                    pass

            elif action == "kick":
                try:
                    await context.bot.ban_chat_member(chat_id, user.id)
                    await context.bot.unban_chat_member(chat_id, user.id)
                except Exception:
                    pass

            elif action == "ban":
                try:
                    await context.bot.ban_chat_member(chat_id, user.id)
                except Exception:
                    pass

            return True

    return False
