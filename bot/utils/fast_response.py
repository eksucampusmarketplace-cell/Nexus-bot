"""
bot/utils/fast_response.py

Ultra-fast response optimization for bot commands.

Features:
- Pre-initialized handlers for instant response
- Async task prioritization
- Response time monitoring and optimization
- Priority queue for critical commands
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.utils.bot_coordinator import FastResponse, get_bot_priority, record_response, should_respond

logger = logging.getLogger(__name__)

# Command categories by priority
CRITICAL_COMMANDS = {"start", "help", "panel", "menu", "ping"}
MODERATION_COMMANDS = {"ban", "unban", "mute", "unmute", "kick", "warn", "unwarn"}
INFO_COMMANDS = {"id", "info", "admins", "stats"}
ADMIN_COMMANDS = {"settings", "automod", "filters", "notes", "rules"}

# Pre-warmed handler cache
_handler_cache: dict = {}


class ResponseMetrics:
    """Track response time metrics."""
    
    def __init__(self):
        self.total_calls = 0
        self.total_time = 0.0
        self.slow_calls = 0
        self.slow_threshold = 0.5  # 500ms is considered slow
    
    def record(self, elapsed: float):
        self.total_calls += 1
        self.total_time += elapsed
        if elapsed > self.slow_threshold:
            self.slow_calls += 1
    
    @property
    def avg_time(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_time / self.total_calls
    
    @property
    def slow_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.slow_calls / self.total_calls


_metrics: dict = {}


def get_metrics(command: str) -> ResponseMetrics:
    """Get or create metrics for a command."""
    if command not in _metrics:
        _metrics[command] = ResponseMetrics()
    return _metrics[command]


def fast_command(command_name: str, priority: int = 2, check_other_bots: bool = True):
    """
    Decorator for ultra-fast command handlers.
    
    Args:
        command_name: Name of the command (for metrics and coordination)
        priority: Bot priority (1=main, 2=clone, 3=other)
        check_other_bots: Whether to check for other bot responses
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not update.effective_chat or not update.message:
                return
            
            start_time = time.time()
            chat_id = update.effective_chat.id
            
            try:
                # Check if we should respond (bot coordination)
                if check_other_bots:
                    is_primary = context.bot_data.get("is_primary", False)
                    bot_priority = 1 if is_primary else priority
                    
                    if not await should_respond(update, context, bot_priority):
                        logger.debug(f"[FAST_RESPONSE] Bot {context.bot.id} skipping {command_name} due to coordination")
                        return
                
                # Execute with fast response tracking
                async with FastResponse(update, context, timeout=0.5):
                    result = await func(update, context)
                
                # Record response for coordination
                if check_other_bots:
                    await record_response(update, context, bot_priority)
                
                return result
                
            except Exception as e:
                logger.error(f"[FAST_RESPONSE] Error in {command_name}: {e}")
                raise
            finally:
                elapsed = time.time() - start_time
                metrics = get_metrics(command_name)
                metrics.record(elapsed)
                
                # Log slow responses
                if elapsed > 1.0:
                    logger.warning(f"[FAST_RESPONSE] Slow {command_name}: {elapsed:.2f}s in chat {chat_id}")
        
        # Cache the handler
        _handler_cache[command_name] = wrapper
        return wrapper
    return decorator


def critical_command(command_name: str):
    """
    Decorator for critical commands that must respond fastest.
    These have highest priority and skip some checks.
    """
    return fast_command(command_name, priority=1, check_other_bots=True)


def moderation_command(command_name: str):
    """
    Decorator for moderation commands.
    High priority but still checks for conflicts.
    """
    return fast_command(command_name, priority=1, check_other_bots=True)


class CommandPrioritizer:
    """
    Prioritizes command execution for better responsiveness.
    """
    
    def __init__(self):
        self._high_priority = asyncio.PriorityQueue()
        self._normal_priority = asyncio.Queue()
        self._processing = False
    
    async def add_command(self, coro, priority: int = 5):
        """
        Add a command to be executed.
        Lower priority numbers = higher priority.
        """
        if priority <= 2:
            await self._high_priority.put((priority, time.time(), coro))
        else:
            await self._normal_priority.put(coro)
    
    async def process(self):
        """Process queued commands."""
        self._processing = True
        
        while self._processing:
            # Process high priority first
            while not self._high_priority.empty():
                _, _, coro = await self._high_priority.get()
                try:
                    await coro
                except Exception as e:
                    logger.error(f"[PRIORITIZER] Error in high priority command: {e}")
            
            # Then normal priority
            if not self._normal_priority.empty():
                coro = await self._normal_priority.get()
                try:
                    await coro
                except Exception as e:
                    logger.error(f"[PRIORITIZER] Error in normal command: {e}")
            
            await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
    
    def stop(self):
        """Stop processing."""
        self._processing = False


# Global prioritizer instance
_prioritizer: Optional[CommandPrioritizer] = None


def get_prioritizer() -> CommandPrioritizer:
    """Get or create the global command prioritizer."""
    global _prioritizer
    if _prioritizer is None:
        _prioritizer = CommandPrioritizer()
    return _prioritizer


async def quick_reply(update: Update, text: str, parse_mode: Optional[str] = None, 
                     reply_markup=None, delete_after: Optional[int] = None):
    """
    Send a quick reply with minimal overhead.
    
    Args:
        update: The update object
        text: Text to send
        parse_mode: Parse mode for the message
        reply_markup: Reply markup
        delete_after: Seconds after which to delete the message
    """
    if not update.message:
        return None
    
    try:
        msg = await update.message.reply_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        
        if delete_after and msg:
            # Schedule deletion without waiting
            asyncio.create_task(_delete_after(update, msg.message_id, delete_after))
        
        return msg
    except Exception as e:
        logger.error(f"[QUICK_REPLY] Failed to send: {e}")
        return None


async def _delete_after(update: Update, message_id: int, delay: int):
    """Delete a message after a delay."""
    await asyncio.sleep(delay)
    try:
        await update.message.chat.delete_message(message_id)
    except Exception:
        pass


def get_performance_report() -> dict:
    """Get a performance report for all tracked commands."""
    return {
        command: {
            "avg_time": metrics.avg_time,
            "total_calls": metrics.total_calls,
            "slow_rate": metrics.slow_rate,
        }
        for command, metrics in _metrics.items()
    }


# Pre-warm common handlers to reduce first-call latency
async def prewarm_handlers():
    """
    Pre-warm command handlers to reduce cold-start latency.
    This should be called during bot startup.
    """
    logger.info("[FAST_RESPONSE] Pre-warming command handlers...")
    
    # Import common handlers to warm them up
    try:
        from bot.handlers import moderation, commands, start_help
        logger.info("[FAST_RESPONSE] Handlers pre-warmed")
    except ImportError as e:
        logger.warning(f"[FAST_RESPONSE] Could not pre-warm some handlers: {e}")
