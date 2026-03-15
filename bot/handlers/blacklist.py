"""
bot/handlers/blacklist.py

Blacklist management commands:
  /blacklist <word>         — add a word to the blacklist
  /blacklist                — show all blacklisted words
  /unblacklist <word>       — remove a word from the blacklist
  /blacklistmode <action>   — set action: delete|warn|mute|ban
"""

import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import ERRORS, RANK_ADMIN, get_user_rank
from db.client import db

log = logging.getLogger("[BLACKLIST]")


async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    if not context.args:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
        settings = row["settings"] if row else {}
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except Exception:
                settings = {}
        words = settings.get("blacklist_words", [])
        if not words:
            await update.message.reply_text("📋 No blacklisted words in this group.")
            return
        text = f"🚫 *Blacklisted words ({len(words)}):*\n\n"
        text += " | ".join(f"`{w}`" for w in words)
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    word = context.args[0].lower().strip()
    if not word:
        await update.message.reply_text("❓ Usage: /blacklist <word>")
        return

    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
            settings = row["settings"] if row else {}
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except Exception:
                    settings = {}
            words = settings.get("blacklist_words", [])
            if word in words:
                await update.message.reply_text(f"ℹ️ *{word}* is already blacklisted.", parse_mode="Markdown")
                return
            words.append(word)
            settings["blacklist_words"] = words
            await conn.execute(
                "UPDATE groups SET settings = $1 WHERE chat_id = $2",
                json.dumps(settings), chat_id,
            )
        await update.message.reply_text(f"✅ Added to blacklist: *{word}*", parse_mode="Markdown")
        log.info(f"[BLACKLIST] Added '{word}' to blacklist in chat {chat_id}")
    except Exception as e:
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
            row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
            settings = row["settings"] if row else {}
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except Exception:
                    settings = {}
            words = settings.get("blacklist_words", [])
            if word not in words:
                await update.message.reply_text(f"❌ *{word}* is not in the blacklist.", parse_mode="Markdown")
                return
            settings["blacklist_words"] = [w for w in words if w != word]
            await conn.execute(
                "UPDATE groups SET settings = $1 WHERE chat_id = $2",
                json.dumps(settings), chat_id,
            )
        await update.message.reply_text(f"✅ Removed from blacklist: *{word}*", parse_mode="Markdown")
    except Exception as e:
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

    try:
        async with db.pool.acquire() as conn:
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
        await update.message.reply_text(f"✅ Blacklist action set to: *{mode}*", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to set blacklist mode: {e}")
