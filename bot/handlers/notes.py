"""
bot/handlers/notes.py

Group notes management:
  /savenote <name> [text]  — save a note (reply to any message to save media)
  /note <name>             — retrieve and send a note
  /delnote <name>          — delete a note
  /notes                   — list all notes for this group
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import ERRORS, RANK_ADMIN, get_user_rank
from db.client import db
import db.ops.notes as notes_db

log = logging.getLogger("[NOTES]")


async def savenote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    if not context.args:
        await update.message.reply_text("❓ Usage: /savenote <name> [text]\nOr reply to a message with /savenote <name>")
        return

    name = context.args[0].lower().strip()
    content = " ".join(context.args[1:]) if len(context.args) > 1 else None
    file_id = None
    media_type = None

    reply = update.message.reply_to_message
    if reply:
        if not content and reply.text:
            content = reply.text
        if reply.photo:
            file_id = reply.photo[-1].file_id
            media_type = "photo"
        elif reply.video:
            file_id = reply.video.file_id
            media_type = "video"
        elif reply.audio:
            file_id = reply.audio.file_id
            media_type = "audio"
        elif reply.document:
            file_id = reply.document.file_id
            media_type = "document"
        elif reply.sticker:
            file_id = reply.sticker.file_id
            media_type = "sticker"
        elif reply.voice:
            file_id = reply.voice.file_id
            media_type = "voice"
        elif reply.animation:
            file_id = reply.animation.file_id
            media_type = "animation"

    if not content and not file_id:
        await update.message.reply_text("❌ Please provide text or reply to a message to save as a note.")
        return

    try:
        await notes_db.save_note(
            db.pool, chat_id, name, content, file_id, media_type, [], invoker.id
        )
        await update.message.reply_text(f"✅ Note *{name}* saved.", parse_mode="Markdown")
        log.info(f"[NOTES] Saved note '{name}' in chat {chat_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to save note: {e}")


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("❓ Usage: /note <name>")
        return

    name = context.args[0].lower().strip()

    try:
        note = await notes_db.get_note(db.pool, chat_id, name)
        if not note:
            await update.message.reply_text(f"❌ No note found with name: *{name}*", parse_mode="Markdown")
            return

        buttons = note.get("buttons") or []
        if isinstance(buttons, str):
            import json
            try:
                buttons = json.loads(buttons)
            except Exception:
                buttons = []

        reply_markup = None
        if buttons:
            keyboard = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons if b.get("text") and b.get("url")]
            if keyboard:
                reply_markup = InlineKeyboardMarkup(keyboard)

        media_type = note.get("media_type")
        file_id = note.get("file_id")
        content = note.get("content") or ""

        if media_type == "photo" and file_id:
            await update.message.reply_photo(file_id, caption=content or None, reply_markup=reply_markup)
        elif media_type == "video" and file_id:
            await update.message.reply_video(file_id, caption=content or None, reply_markup=reply_markup)
        elif media_type == "audio" and file_id:
            await update.message.reply_audio(file_id, caption=content or None, reply_markup=reply_markup)
        elif media_type == "document" and file_id:
            await update.message.reply_document(file_id, caption=content or None, reply_markup=reply_markup)
        elif media_type == "sticker" and file_id:
            await update.message.reply_sticker(file_id)
        elif media_type == "voice" and file_id:
            await update.message.reply_voice(file_id, caption=content or None, reply_markup=reply_markup)
        elif media_type == "animation" and file_id:
            await update.message.reply_animation(file_id, caption=content or None, reply_markup=reply_markup)
        else:
            if content:
                await update.message.reply_text(content, reply_markup=reply_markup)
            else:
                await update.message.reply_text(f"📝 Note *{name}* has no content.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to retrieve note: {e}")


async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    if not context.args:
        await update.message.reply_text("❓ Usage: /delnote <name>")
        return

    name = context.args[0].lower().strip()

    try:
        deleted = await notes_db.delete_note(db.pool, chat_id, name)
        if deleted:
            await update.message.reply_text(f"✅ Note *{name}* deleted.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ No note found: *{name}*", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to delete note: {e}")


async def notes_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    try:
        notes = await notes_db.get_notes(db.pool, chat_id)
        if not notes:
            await update.message.reply_text("📝 No notes saved in this group.")
            return

        text = f"📝 *Notes in this group ({len(notes)}):*\n\n"
        for note in notes:
            media_indicator = f" [{note['media_type']}]" if note.get("media_type") else ""
            text += f"• `{note['name']}`{media_indicator}\n"
        text += "\nUse /note <name> to retrieve a note."
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to fetch notes: {e}")
