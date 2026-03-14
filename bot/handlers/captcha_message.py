"""
bot/handlers/captcha_message.py

Handle text/math CAPTCHA answers from user messages.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.captcha.engine import verify_text_answer

log = logging.getLogger("captcha_message")


async def handle_captcha_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Check if a message is a CAPTCHA answer.
    Returns True if it was a CAPTCHA attempt (even if wrong).
    """
    msg = update.effective_message
    if not msg or not msg.text:
        return False

    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data.get("db")

    # Fast check: does this user have a pending challenge in this chat?
    # We use a DB check here. In high-traffic bots, this might be cached.
    from db.ops.captcha import get_pending_challenge

    challenge = await get_pending_challenge(db, chat.id, user.id)
    if not challenge:
        return False

    if challenge["mode"] not in ("math", "text"):
        return False

    get_settings = context.bot_data.get("get_settings")
    if not get_settings:
        from db.ops.automod import get_group_settings

        settings = await get_group_settings(db, chat.id)
    else:
        settings = await get_settings(chat.id)

    passed = await verify_text_answer(context.bot, chat.id, user.id, msg.text, db, settings)

    # Always return True because we handled/swallowed the CAPTCHA attempt
    return True
