"""
bot/handlers/personality_cmd.py

Bot Personality Presets — one-click tone switching.

Commands:
  /personality              — Show current tone and available presets
  /personality <tone>       — Switch to a preset tone
  /personality preview      — Preview all tones side by side

Available tones: warm, professional, strict, playful, neutral

Log prefix: [PERSONA]
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.personality.engine import TONES, PersonalityEngine
from bot.utils.permissions import is_admin

log = logging.getLogger("persona")

TONE_EMOJIS = {
    "warm": "💙",
    "professional": "💼",
    "strict": "🚨",
    "playful": "🎈",
    "neutral": "⚖️",
}


async def cmd_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show or switch bot personality."""
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command only works in groups.")
        return

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can change the bot personality.")
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    if not context.args:
        # Show current personality and buttons to switch
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT persona_tone FROM groups WHERE chat_id=$1", chat.id
            )

        current = row["persona_tone"] if row and row["persona_tone"] else "neutral"

        buttons = []
        for tone, desc in TONES.items():
            emoji = TONE_EMOJIS.get(tone, "")
            marker = " (current)" if tone == current else ""
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{emoji} {tone.title()}{marker}",
                        callback_data=f"persona:{tone}",
                    )
                ]
            )

        await update.message.reply_text(
            f"<b>Bot Personality</b>\n\n"
            f"Current tone: <b>{current}</b>\n\n"
            f"Tap a button to switch:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    sub = context.args[0].lower()

    if sub == "preview":
        await _preview_tones(update)
        return

    # Direct tone switch
    if sub not in TONES:
        await update.message.reply_text(
            f"Unknown tone. Available: {', '.join(TONES.keys())}"
        )
        return

    await _set_tone(update, db, chat.id, sub)


async def handle_persona_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle personality button clicks."""
    query = update.callback_query
    data = query.data

    if not data.startswith("persona:"):
        return

    tone = data.split(":")[1]
    if tone not in TONES:
        await query.answer("Invalid tone.")
        return

    chat = update.effective_chat

    # Check admin
    try:
        member = await context.bot.get_chat_member(chat.id, query.from_user.id)
        if member.status not in ("creator", "administrator"):
            await query.answer("Only admins can change this.", show_alert=True)
            return
    except Exception:
        await query.answer("Could not verify permissions.")
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    await _set_tone_db(db, chat.id, tone)

    emoji = TONE_EMOJIS.get(tone, "")
    await query.answer(f"Switched to {tone}!")

    try:
        # Show preview of new tone
        engine = PersonalityEngine(tone=tone)
        preview = engine.get_preview()

        await query.edit_message_text(
            f"<b>Personality Updated!</b>\n\n"
            f"Tone: {emoji} <b>{tone.title()}</b>\n\n"
            f"Example warn:\n<i>{preview['warn']}</i>\n\n"
            f"Example ban:\n<i>{preview['ban']}</i>\n\n"
            f"Use /personality to change again.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    log.info(f"[PERSONA] Changed | chat={chat.id} tone={tone}")


async def _set_tone(update, db, chat_id, tone):
    """Set personality tone and confirm."""
    await _set_tone_db(db, chat_id, tone)

    engine = PersonalityEngine(tone=tone)
    preview = engine.get_preview()
    emoji = TONE_EMOJIS.get(tone, "")

    await update.message.reply_text(
        f"<b>Personality set to {emoji} {tone.title()}</b>\n\n"
        f"Example warn:\n<i>{preview['warn']}</i>\n\n"
        f"Example ban:\n<i>{preview['ban']}</i>",
        parse_mode=ParseMode.HTML,
    )
    log.info(f"[PERSONA] Set | chat={chat_id} tone={tone}")


async def _set_tone_db(db, chat_id, tone):
    """Update tone in database."""
    async with db.acquire() as conn:
        await conn.execute(
            """UPDATE groups SET persona_tone=$1 WHERE chat_id=$2""",
            tone,
            chat_id,
        )


async def _preview_tones(update):
    """Show preview of all tones."""
    lines = ["<b>Personality Previews</b>\n"]

    for tone_name in TONES:
        emoji = TONE_EMOJIS.get(tone_name, "")
        engine = PersonalityEngine(tone=tone_name)
        preview = engine.get_preview()
        lines.append(
            f"{emoji} <b>{tone_name.title()}</b>\n"
            f"Warn: <i>{preview['warn'][:80]}</i>\n"
        )

    lines.append("Use /personality <tone> to switch.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


personality_handlers = [
    CommandHandler("personality", cmd_personality),
    CallbackQueryHandler(handle_persona_callback, pattern=r"^persona:"),
]
