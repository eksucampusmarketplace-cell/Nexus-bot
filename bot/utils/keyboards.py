"""
bot/utils/keyboards.py

All inline keyboards used across the bot (primary + clones).
These keyboards are used in messages from every bot instance.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import settings


def support_keyboard(
    include_miniapp: bool = False,
    miniapp_url: str | None = None,
    include_docs: bool = False
) -> InlineKeyboardMarkup:
    """
    Standard support keyboard shown in help/start messages.

    Args:
        include_miniapp: Show Mini App button
        miniapp_url: URL to open Mini App (falls back to settings.MINI_APP_URL)
        include_docs: Show documentation button

    Returns:
        InlineKeyboardMarkup with support buttons
    """
    buttons = []

    # Mini App button (if configured) - shown first as primary action
    if include_miniapp:
        url = miniapp_url or settings.MINI_APP_URL
        if url:
            buttons.append([InlineKeyboardButton(
                "⚡ Open Mini App",
                web_app=WebAppInfo(url=url)
            )])

    # Main bot support button
    buttons.append([InlineKeyboardButton(
        "💬 Support Group",
        url=settings.SUPPORT_GROUP_URL or f"https://t.me/{settings.MAIN_BOT_USERNAME}"
    )])

    # Documentation button (if configured)
    if include_docs and settings.DOCS_URL:
        buttons.append([InlineKeyboardButton(
            "📚 Documentation",
            url=settings.DOCS_URL
        )])

    return InlineKeyboardMarkup(buttons)


def mini_app_keyboard(miniapp_url: str | None = None) -> InlineKeyboardMarkup:
    """
    Simple Mini App keyboard - single button to open the settings webapp.

    Args:
        miniapp_url: URL to open Mini App (falls back to settings.MINI_APP_URL)

    Returns:
        InlineKeyboardMarkup with single Mini App button
    """
    url = miniapp_url or settings.MINI_APP_URL
    if not url:
        # Fall back to support keyboard if no miniapp URL
        return support_keyboard()

    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⚡ Open Settings", web_app=WebAppInfo(url=url))
    ]])


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel button for conversations."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]])
