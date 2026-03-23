"""
bot/handlers/privacy.py

Handles /privacy command to display the Privacy Policy.
This handler is registered in factory.py for every bot instance.
"""

import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode
from config import settings

log = logging.getLogger("privacy")


async def handle_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /privacy handler. Displays the Privacy Policy to users.
    Provides a link to the Mini App privacy page for full details.
    """
    user = update.effective_user
    chat = update.effective_chat

    log.info(f"[PRIVACY] user={user.id} chat={chat.id}")

    miniapp_url = settings.mini_app_url
    privacy_url = f"{miniapp_url}privacy.html" if miniapp_url else None

    # Build privacy summary with link to full policy
    privacy_summary = f"""📋 <b>Privacy Policy</b>

<b>Data We Collect:</b>
• User ID and username (for bot functionality)
• Group membership and message metadata
• Moderation actions and logs
• XP and game statistics

<b>How We Use Your Data:</b>
• Group management and moderation
• Trust score calculation
• Analytics and insights
• Improving bot features

<b>Your Rights (GDPR):</b>
• Right to access your data
• Right to delete your data
• Right to export your data
• Right to correction

<b>Data Security:</b>
• Encrypted storage
• Access limited to group admins
• No data sold to third parties

<b>Full Privacy Policy:</b>
View the complete policy with detailed information."""

    keyboard = []
    if privacy_url:
        keyboard.append(
            [InlineKeyboardButton("📄 View Full Privacy Policy", web_app={"url": privacy_url})]
        )
    # Bug #23 fix: Guard against empty MAIN_BOT_USERNAME
    support_username = settings.MAIN_BOT_USERNAME or settings.BOT_DISPLAY_NAME
    if support_username:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "📧 Contact Support", url=f"https://t.me/{support_username}"
                )
            ]
        )

    await update.message.reply_text(
        privacy_summary, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Handler object to register in factory.py ───────────────────────────────
privacy_handler = CommandHandler("privacy", handle_privacy)
