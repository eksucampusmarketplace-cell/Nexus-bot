"""
bot/utils/bot_info.py

Utilities for getting bot information with caching to reduce API calls.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def get_bot_info_cached(bot, bot_data: dict) -> dict:
    """
    Get bot info with caching to avoid excessive getMe() API calls.
    
    The bot info is cached in bot_data['cached_bot_info'].
    """
    cached = bot_data.get("cached_bot_info")
    if cached:
        return cached
    
    # Not cached, fetch from API
    try:
        me = await bot.get_me()
        bot_info = {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "is_bot": me.is_bot,
        }
        bot_data["cached_bot_info"] = bot_info
        return bot_info
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        # Return minimal info to prevent crashes
        return {"id": 0, "username": "unknown", "first_name": "Unknown Bot"}


async def get_bot_username_cached(bot, bot_data: dict) -> str:
    """Get bot username with caching."""
    info = await get_bot_info_cached(bot, bot_data)
    return info.get("username", "unknown")


def init_bot_info_cache(context: ContextTypes.DEFAULT_TYPE, bot, is_primary: bool = False):
    """
    Initialize the bot info cache. Call this during bot startup.
    """
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't await in sync context, will be cached on first use
            pass
        else:
            me = bot.get_me()
            context.bot_data["cached_bot_info"] = {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "is_bot": me.is_bot,
            }
    except Exception as e:
        logger.warning(f"Failed to initialize bot cache: {e}")
