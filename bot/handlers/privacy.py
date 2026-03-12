"""
bot/handlers/privacy.py

Handles /privacy command to display the Telegram Standard Bot Privacy Policy.
This handler is registered in factory.py for every bot instance.

The policy is required by Telegram for all third-party bots and mini apps.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

log = logging.getLogger("privacy")

# Telegram Standard Bot Privacy Policy
# Source: https://telegram.org/privacy-tpa
PRIVACY_POLICY_TEXT = """<b>📜 Standard Bot Privacy Policy</b>

This privacy policy governs the relationship between Third-Party Service and User.

<b>1. Terms and Definitions</b>
• <b>Telegram</b> – Telegram Messenger Inc
• <b>Platform</b> – The Telegram Bot Platform
• <b>Developer</b> – The person or entity who operates the bot/mini app
• <b>Third-Party Service</b> – The bot or mini app made available on Platform
• <b>User</b> – The person accessing Third-Party Service via their Telegram account
• <b>Policy</b> – This document

<b>2. General Provisions</b>
• This Policy applies to all third-party bots and mini apps on Platform by default
• It governs the collection, storage, distribution, usage and protection of User information
• Your continued use of this bot constitutes acceptance of this Policy

<b>3. Disclaimers</b>
• This bot is an independent third-party application, not maintained or affiliated with Telegram
• This Policy may be amended at any time — your continued use means you accept the changes

<b>4. Collection of Personal Data</b>
• We may access limited information as described in Telegram's Privacy Policy
• Additional data is collected only when you send messages, upload files, or choose to share information
• Anonymous diagnostic data may be collected for service improvement

<b>5. Processing of Personal Data</b>
• We only collect data necessary for the bot's features to function
• Your data is processed on the legal ground of legitimate interest (providing services)
• We do not monetize user data for purposes outside this service

<b>6. Data Protection</b>
• We employ security measures to protect your data
• User information is handled in compliance with applicable laws
• We will never share your data with third parties unless required by law or explicitly authorized by you

<b>7. Your Rights</b>
You may:
• Request a copy of all personal data we collected about you
• Request deletion of your personal data (except where required by law)
• Amend, restrict, or object to processing of your data
• Withdraw consent at any time
• Lodge a complaint with data protection authorities

To exercise these rights, contact the bot developer.

<b>8. Changes to Privacy Policy</b>
We may update this Policy from time to time. Please check for updates.

<i>This is Telegram's Standard Bot Privacy Policy. The bot developer may have published a separate, custom privacy policy.</i>"""


async def handle_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /privacy handler. Shows the Telegram Standard Bot Privacy Policy.
    Works in both private and group chats.
    """
    user = update.effective_user
    chat = update.effective_chat

    log.info(f"[PRIVACY] user={user.id} chat={chat.id}")

    await update.message.reply_text(
        text=PRIVACY_POLICY_TEXT,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


# Handler object to register in factory.py
privacy_handler = CommandHandler("privacy", handle_privacy)
