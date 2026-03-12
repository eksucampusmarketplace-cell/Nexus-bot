"""
bot/handlers/privacy.py

Handles /privacy command to display the Privacy Policy.
This handler is registered in factory.py for every bot instance.
"""

import logging
import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

log = logging.getLogger("privacy")


async def handle_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /privacy handler. Displays the Privacy Policy to users.
    """
    user = update.effective_user
    chat = update.effective_chat

    log.info(f"[PRIVACY] user={user.id} chat={chat.id}")

    # Try to load the privacy policy from file
    privacy_policy_path = os.path.join(os.path.dirname(__file__), '..', '..', 'PRIVACY_POLICY.md')

    if os.path.exists(privacy_policy_path):
        with open(privacy_policy_path, 'r', encoding='utf-8') as f:
            privacy_text = f.read()

        # Convert markdown-style headers to HTML for better Telegram formatting
        privacy_html = _markdown_to_html(privacy_text)

        # The policy is too long for a single message, so we send it in chunks
        chunk_size = 4000  # Telegram message limit is 4096
        chunks = [privacy_html[i:i+chunk_size] for i in range(0, len(privacy_html), chunk_size)]

        for i, chunk in enumerate(chunks):
            try:
                # Add a "Continue..." indicator for all but the last chunk
                if i < len(chunks) - 1:
                    chunk += "\n\n<i>...Continued in next message...</i>"

                await update.message.reply_text(
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                log.error(f"[PRIVACY] Failed to send chunk {i+1}/{len(chunks)}: {e}")

    else:
        # Fallback if file doesn't exist
        fallback_message = (
            "📋 <b>Privacy Policy</b>\n\n"
            "Our detailed Privacy Policy is available at:\n"
            "https://github.com/yourusername/nexus/blob/main/PRIVACY_POLICY.md\n\n"
            "Or contact support@nexus-bot.com for a copy.\n\n"
            "Key points:\n"
            "• We collect minimal data necessary for group management\n"
            "• Your data is stored securely in the EU\n"
            "• You have GDPR rights to access, correct, and delete your data\n"
            "• We never sell your personal data\n"
            "• Group admins can only see data about members in their own groups\n\n"
            "For questions, use /support or email privacy@nexus-bot.com"
        )
        await update.message.reply_text(
            text=fallback_message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )


def _markdown_to_html(text: str) -> str:
    """
    Convert basic markdown to HTML for better Telegram formatting.
    This is a simple converter - doesn't handle all markdown features.
    """
    html = text

    # Headers (# ### etc)
    html = html.replace('###', '<h3>').replace('# ', '<b>')
    html = html.replace('###', '</h3>')

    # Bold (**text**)
    html = html.replace('**', '<b>').replace('**', '</b>')

    # Italic (*text*)
    html = html.replace('* ', '<i>').replace('*', '</i>')

    # Links [text](url) - basic handling
    # Note: This is simplified; full markdown link parsing would be more complex
    import re
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)

    # Clean up multiple newlines
    html = html.replace('\n\n\n', '\n\n')

    # Convert horizontal rules
    html = html.replace('---', '—')

    return html


# ── Handler object to register in factory.py ───────────────────────────────
privacy_handler = CommandHandler("privacy", handle_privacy)
