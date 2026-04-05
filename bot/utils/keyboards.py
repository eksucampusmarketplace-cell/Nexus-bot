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
    include_docs: bool = False,
    include_privacy: bool = True,
) -> InlineKeyboardMarkup:
    """
    Standard support keyboard shown in help/start messages.

    Args:
        include_miniapp: Show Mini App button
        miniapp_url: URL to open Mini App (falls back to settings.MINI_APP_URL)
        include_docs: Show documentation button
        include_privacy: Show Privacy Policy button

    Returns:
        InlineKeyboardMarkup with support buttons
    """
    buttons = []

    # Mini App button (if configured) - shown first as primary action
    if include_miniapp:
        url = miniapp_url or settings.mini_app_url
        if url:
            buttons.append([InlineKeyboardButton("⚡ Open Mini App", web_app=WebAppInfo(url=url))])

    # Main bot support button — only if we have a valid URL
    support_url = settings.SUPPORT_GROUP_URL or (
        f"https://t.me/{settings.MAIN_BOT_USERNAME}" if settings.MAIN_BOT_USERNAME else None
    )
    if support_url:
        buttons.append(
            [InlineKeyboardButton("💬 Support Group", url=support_url)]
        )

    # Documentation button (if configured)
    if include_docs:
        docs_url = settings.DOCS_URL or (
            f"https://t.me/{settings.MAIN_BOT_USERNAME}" if settings.MAIN_BOT_USERNAME else None
        )
        if docs_url:
            buttons.append([InlineKeyboardButton("📚 Help & Docs", url=docs_url)])

    # Privacy Policy button — fall back to /privacy redirect
    if include_privacy:
        privacy_url = settings.PRIVACY_POLICY_URL or (
            f"{settings.webhook_url}/privacy" if settings.RENDER_EXTERNAL_URL else None
        )
        if privacy_url:
            buttons.append([InlineKeyboardButton("🔒 Privacy Policy", url=privacy_url)])

    return InlineKeyboardMarkup(buttons)


def mini_app_keyboard(miniapp_url: str | None = None) -> InlineKeyboardMarkup:
    """
    Simple Mini App keyboard - single button to open the settings webapp.

    Args:
        miniapp_url: URL to open Mini App (falls back to settings.mini_app_url)

    Returns:
        InlineKeyboardMarkup with single Mini App button
    """
    url = miniapp_url or settings.mini_app_url
    if not url:
        # Fall back to support keyboard if no miniapp URL
        return support_keyboard()

    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⚡ Open Settings", web_app=WebAppInfo(url=url))]]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel button for conversations."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
