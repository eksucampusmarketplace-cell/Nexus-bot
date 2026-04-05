"""
api/utils/bot_helper.py

Utility functions for working with bots in API routes.
Handles the logic of finding the correct bot for a group.
"""

import logging
from telegram.ext import Application
from db.client import db

logger = logging.getLogger(__name__)


async def get_bot_for_group(chat_id: int) -> Application | None:
    """
    Get the bot application that manages a specific group.
    
    This function:
    1. First tries to find the bot that manages this group via bot_token_hash in the groups table
    2. Falls back to any available bot if no specific match is found
    
    Returns None if no suitable bot is found.
    
    Args:
        chat_id: The Telegram chat ID of the group
        
    Returns:
        The PTB Application instance or None
    """
    from bot.registry import get_all
    from bot.utils.crypto import hash_token

    bots = get_all()
    if not bots:
        return None

    # First, try to find the bot that manages this group via bot_token_hash
    try:
        async with db.pool.acquire() as conn:
            group_row = await conn.fetchrow(
                "SELECT bot_token_hash FROM groups WHERE chat_id = $1", chat_id
            )
            if group_row and group_row["bot_token_hash"]:
                # Find the bot with this token hash
                for bid, app in bots.items():
                    try:
                        token_hash = hash_token(app.bot.token)
                        if token_hash == group_row["bot_token_hash"]:
                            logger.debug(
                                f"[BotHelper] Found bot {bid} managing group {chat_id} via bot_token_hash"
                            )
                            return app
                    except Exception:
                        continue
    except Exception as e:
        logger.debug(f"[BotHelper] Could not determine bot for group {chat_id}: {e}")

    # Fallback: use any available bot
    for bid, app in bots.items():
        logger.debug(f"[BotHelper] Using fallback bot {bid} for group {chat_id}")
        return app

    return None
