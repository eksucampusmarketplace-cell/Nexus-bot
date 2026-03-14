"""
bot/utils/alerts.py

Posts internal alerts to the support group.
Used for: errors on clone bots, new clone registrations, dead clone tokens.
Only the Nexus owner sees these — they go to SUPPORT_GROUP_ID.
Silently skips if SUPPORT_GROUP_ID is 0 or posting fails.
Never raises exceptions — alerts must never crash the bot.
"""

import logging
from datetime import datetime
from telegram import Bot
from config import settings

log = logging.getLogger("alerts")


async def _post(bot: Bot, text: str):
    """Internal: post text to support group. Silently fails."""
    if not settings.SUPPORT_GROUP_ID:
        return
    try:
        await bot.send_message(chat_id=settings.SUPPORT_GROUP_ID, text=text, parse_mode="HTML")
    except Exception as e:
        log.warning(f"[ALERTS] Failed to post alert | error={e}")


async def alert_error(bot: Bot, clone_username: str, chat_id: int, error: str):
    """Post an error alert. Called from global error handler."""
    if not settings.ALERT_ON_ERRORS:
        return
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    await _post(
        bot,
        f"🔴 <b>Error on @{clone_username}</b>\n"
        f"Chat: <code>{chat_id}</code>\n"
        f"Error: <code>{error[:300]}</code>\n"
        f"Time: {ts}",
    )


async def alert_new_clone(bot: Bot, clone_username: str, owner_id: int, owner_name: str):
    """Post when a new clone is registered."""
    if not settings.ALERT_ON_NEW_CLONES:
        return
    await _post(
        bot,
        f"🆕 <b>New clone registered</b>\n"
        f"Bot: @{clone_username}\n"
        f"Owner: <a href='tg://user?id={owner_id}'>{owner_name}</a> "
        f"(<code>{owner_id}</code>)",
    )


async def alert_dead_clone(bot: Bot, clone_username: str, owner_id: int, bot_id: int):
    """Post when a clone token becomes invalid."""
    if not settings.ALERT_ON_DEAD_CLONES:
        return
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    await _post(
        bot,
        f"⚠️ <b>Dead clone detected</b>\n"
        f"Bot: @{clone_username}\n"
        f"Bot ID: <code>{bot_id}</code>\n"
        f"Owner: <code>{owner_id}</code>\n"
        f"Detected: {ts}",
    )
