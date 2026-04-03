"""
bot/utils/bot_coordinator.py

Coordinates bot responses to prevent conflicts with other bots in groups.
Implements:
- Response priority system (main bot > clone bots > other bots)
- Anti-overwhelm detection (cease function if another bot floods)
- Fast response optimization
- Command deduplication
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Track recent bot responses per chat
_bot_responses: Dict[int, List[dict]] = defaultdict(list)
_last_pruned = 0

# Configuration
RESPONSE_WINDOW = 3  # seconds to check for other bot responses
OVERWHELM_THRESHOLD = 5  # responses from other bots in window to trigger cease
COOLDOWN_PERIOD = 30  # seconds to cease responses after overwhelm detected

# Track active cooldowns per chat
_cooldowns: Dict[int, float] = {}


async def should_respond(update: Update, context: ContextTypes.DEFAULT_TYPE, priority: int = 1) -> bool:
    """
    Determine if this bot should respond to a command/message.
    
    Args:
        update: The Telegram update
        context: PTB context
        priority: Response priority (1=main bot, 2=clone, 3=other)
        
    Returns:
        True if bot should respond, False otherwise
    """
    if not update.effective_chat:
        return True
        
    chat_id = update.effective_chat.id
    now = time.time()
    
    # Check if we're in cooldown mode (another bot is overwhelming)
    if chat_id in _cooldowns:
        if now < _cooldowns[chat_id]:
            logger.debug(f"[BOT_COORD] Bot {context.bot.id} in cooldown for chat {chat_id}")
            return False
        else:
            del _cooldowns[chat_id]
    
    # Clean old response data
    _prune_old_responses(chat_id, now)
    
    # Check for recent responses from other bots
    recent_responses = _bot_responses[chat_id]
    
    # Count responses from other bots in the window
    other_bot_count = sum(
        1 for r in recent_responses 
        if r["bot_id"] != context.bot.id and r["timestamp"] > now - RESPONSE_WINDOW
    )
    
    # If another bot is overwhelming, enter cooldown
    if other_bot_count >= OVERWHELM_THRESHOLD:
        logger.warning(f"[BOT_COORD] Overwhelm detected in chat {chat_id} ({other_bot_count} responses). Ceasing for {COOLDOWN_PERIOD}s")
        _cooldowns[chat_id] = now + COOLDOWN_PERIOD
        return False
    
    # Check if another bot already responded to this specific message/command
    if update.message and update.message.message_id:
        for r in recent_responses:
            if (r.get("reply_to_message_id") == update.message.message_id and 
                r["bot_id"] != context.bot.id and
                r["timestamp"] > now - RESPONSE_WINDOW):
                # Another bot already responded to this message
                if r.get("priority", 99) <= priority:
                    logger.debug(f"[BOT_COORD] Another bot already responded to msg {update.message.message_id}")
                    return False
    
    return True


async def record_response(update: Update, context: ContextTypes.DEFAULT_TYPE, priority: int = 1):
    """
    Record that this bot responded to a message.
    
    Args:
        update: The Telegram update
        context: PTB context
        priority: Response priority (1=main bot, 2=clone, 3=other)
    """
    if not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    now = time.time()
    
    response_data = {
        "bot_id": context.bot.id,
        "timestamp": now,
        "priority": priority,
        "reply_to_message_id": update.message.message_id if update.message else None,
    }
    
    _bot_responses[chat_id].append(response_data)
    
    # Prune old data periodically
    _prune_old_responses(chat_id, now)


def _prune_old_responses(chat_id: int, now: float):
    """Remove old response data to prevent memory bloat."""
    global _last_pruned
    
    # Only prune every 30 seconds globally
    if now - _last_pruned < 30:
        return
    _last_pruned = now
    
    cutoff = now - 60  # Keep 60 seconds of history
    
    for cid in list(_bot_responses.keys()):
        _bot_responses[cid] = [
            r for r in _bot_responses[cid] 
            if r["timestamp"] > cutoff
        ]
        if not _bot_responses[cid]:
            del _bot_responses[cid]
    
    # Also clean expired cooldowns
    for cid in list(_cooldowns.keys()):
        if _cooldowns[cid] <= now:
            del _cooldowns[cid]


async def is_chat_overwhelmed(chat_id: int) -> bool:
    """Check if a chat is currently in overwhelm cooldown."""
    if chat_id not in _cooldowns:
        return False
    if time.time() >= _cooldowns[chat_id]:
        del _cooldowns[chat_id]
        return False
    return True


class FastResponse:
    """Context manager for ensuring fast bot responses."""
    
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE, timeout: float = 0.5):
        self.update = update
        self.context = context
        self.timeout = timeout
        self.start_time = None
        
    async def __aenter__(self):
        self.start_time = time.time()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        if elapsed > self.timeout:
            logger.warning(f"[BOT_COORD] Slow response: {elapsed:.2f}s for chat {self.update.effective_chat.id if self.update.effective_chat else 'N/A'}")
        return False


def get_bot_priority(bot_id: int, is_primary: bool = False) -> int:
    """
    Get priority level for a bot.
    
    Returns:
        1: Main bot (primary)
        2: Clone bot
        3: Other bots
    """
    if is_primary:
        return 1
    # Check if it's a known clone
    from bot.registry import get_all
    registered = get_all()
    if bot_id in registered:
        return 2
    return 3
