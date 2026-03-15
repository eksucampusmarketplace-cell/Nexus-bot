"""
bot/handlers/blacklist.py

Blacklist management commands:
  /blacklist <word>         — add a word to the blacklist
  /blacklist                — show all blacklisted words
  /unblacklist <word>       — remove a word from the blacklist
  /blacklistmode <action>   — set action: delete|warn|mute|ban

Uses blacklist TABLE (not settings JSON) for proper enforcement.
"""

import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import ERRORS, RANK_ADMIN, get_user_rank
from db.client import db

log = logging.getLogger("[BLACKLIST]")

DEFAULT_BLACKLIST_ACTION = "delete"


async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    if not context.args:
        # Read from blacklist table
        try:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch("SELECT word, action FROM blacklist WHERE chat_id = $1", chat_id)
            words = [r["word"] for r in rows]
            if not words:
                await update.message.reply_text("📋 No blacklisted words in this group.")
                return
            text = f"🚫 *Blacklisted words ({len(words)}):*\n\n"
            text += " | ".join(f"`{w}`" for w in words)
            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception as e:
            log.error(f"Failed to list blacklist: {e}")
            await update.message.reply_text("❌ Failed to load blacklist.")
        return

    word = context.args[0].lower().strip()
    if not word:
        await update.message.reply_text("❓ Usage: /blacklist <word>")
        return

    try:
        async with db.pool.acquire() as conn:
            # Insert into blacklist table
            await conn.execute(
                """INSERT INTO blacklist (chat_id, word, action, added_by, added_at)
                   VALUES ($1, $2, $3, $4, NOW())
                   ON CONFLICT (chat_id, word) DO NOTHING""",
                chat_id, word, DEFAULT_BLACKLIST_ACTION, invoker.id
            )
        await update.message.reply_text(f"✅ Added to blacklist: *{word}*", parse_mode="Markdown")
        log.info(f"[BLACKLIST] Added '{word}' to blacklist in chat {chat_id}")
    except Exception as e:
        log.error(f"Failed to add blacklist word: {e}")
        await update.message.reply_text(f"❌ Failed to add to blacklist: {e}")


async def unblacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    if not context.args:
        await update.message.reply_text("❓ Usage: /unblacklist <word>")
        return

    word = context.args[0].lower().strip()

    try:
        async with db.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM blacklist WHERE chat_id = $1 AND word = $2",
                chat_id, word
            )
            if "DELETE 0" in result:
                await update.message.reply_text(f"❌ *{word}* is not in the blacklist.", parse_mode="Markdown")
                return
        await update.message.reply_text(f"✅ Removed from blacklist: *{word}*", parse_mode="Markdown")
        log.info(f"[BLACKLIST] Removed '{word}' from blacklist in chat {chat_id}")
    except Exception as e:
        log.error(f"Failed to remove blacklist word: {e}")
        await update.message.reply_text(f"❌ Failed to remove from blacklist: {e}")


async def blacklistmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    valid_modes = ["delete", "warn", "mute", "ban"]
    if not context.args or context.args[0].lower() not in valid_modes:
        await update.message.reply_text(
            f"❓ Usage: /blacklistmode <action>\nActions: {', '.join(valid_modes)}"
        )
        return

    mode = context.args[0].lower()
    word = context.args[1].lower().strip() if len(context.args) > 1 else None

    try:
        async with db.pool.acquire() as conn:
            if word:
                # Update specific word's action
                await conn.execute(
                    "UPDATE blacklist SET action = $1 WHERE chat_id = $2 AND word = $3",
                    mode, chat_id, word
                )
                await update.message.reply_text(f"✅ Blacklist action for '{word}' set to: *{mode}*", parse_mode="Markdown")
            else:
                # Set default action in settings
                row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
                settings = row["settings"] if row else {}
                if isinstance(settings, str):
                    try:
                        settings = json.loads(settings)
                    except Exception:
                        settings = {}
                settings["blacklist_mode"] = mode
                await conn.execute(
                    "UPDATE groups SET settings = $1 WHERE chat_id = $2",
                    json.dumps(settings), chat_id,
                )
                await update.message.reply_text(f"✅ Default blacklist action set to: *{mode}*", parse_mode="Markdown")
    except Exception as e:
        log.error(f"Failed to set blacklist mode: {e}")
        await update.message.reply_text(f"❌ Failed to set blacklist mode: {e}")
