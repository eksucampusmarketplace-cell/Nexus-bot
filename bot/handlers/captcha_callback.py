"""
bot/handlers/captcha_callback.py

Handle inline button presses for CAPTCHA verification.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.captcha.engine import verify_button

log = logging.getLogger("captcha_callback")


async def handle_captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if not data.startswith("captcha:"):
        return

    parts = data.split(":")
    if len(parts) < 3:
        return

    challenge_id = parts[1]
    is_correct = parts[2] == "1"

    user = query.from_user
    chat = update.effective_chat
    db = context.bot_data.get("db")

    get_settings = context.bot_data.get("get_settings")
    if not get_settings:
        from db.ops.automod import get_group_settings

        settings = await get_group_settings(db, chat.id)
    else:
        settings = await get_settings(chat.id)

    passed = await verify_button(
        context.bot, chat.id, user.id, challenge_id, is_correct, db, settings
    )

    if passed:
        log.info(f"[CAPTCHA] Button passed | chat={chat.id} user={user.id}")
        await query.answer("✅ Verified!")
    elif not is_correct:
        await query.answer("❌ Wrong! Try again.", show_alert=True)
    else:
        await query.answer()
