"""
bot/utils/access_control.py

Enhanced access control system for Nexus Bot.

ROLE HIERARCHY (highest to lowest):
1. OVERLORD (main bot owner) - unrestricted access
2. CLONE OWNER - can manage their bot, but needs Telegram admin for group operations
3. TELEGRAM ADMIN - can use bot commands in their groups
4. MEMBER - basic usage only

KEY CONCEPT:
- Bot Management (Mini App "My Bots") = Based on bot ownership
- Group Operations (Telegram commands) = Based on Telegram admin status + bot ownership

Example:
- Alice owns a clone bot. She can see all groups where her bot is in "My Bots".
- But to ban someone in Group X, she must ALSO be a Telegram admin in Group X.

Features:
- Main bot owner (overlord) has unrestricted access
- Clone owners have restricted access to their bot groups
- Strict permission checks for sensitive operations
- Rate limiting for clone owners
- Admin-only enforcement for group-affecting operations
"""

import asyncio
import logging
from functools import wraps
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from config import settings

logger = logging.getLogger(__name__)

# Rate limiting for clone owners
_clone_owner_calls: dict = {}  # {user_id: [timestamps]}
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX_CALLS = 10  # 10 calls per minute for clone owners

# Operations that require admin privileges
ADMIN_ONLY_OPERATIONS = {
    "ban",
    "unban",
    "mute",
    "unmute",
    "kick",
    "purge",
    "delete",
    "warn",
    "unwarn",
    "lock",
    "unlock",
    "settings",
    "automod",
    "filters",
    "notes",
    "rules",
    "welcome",
    "goodbye",
}

# Operations clone owners can do WITHOUT being admin (read-only)
CLONE_OWNER_READ_OPS = {
    "info",
    "id",
    "admins",
    "stats",
    "ping",
    "help",
}


async def check_main_bot_owner(user_id: int) -> bool:
    """Check if user is the main bot owner (overlord)."""
    return user_id == settings.OWNER_ID


async def check_clone_owner(user_id: int, bot_id: int) -> bool:
    """Check if user is the owner of a specific clone bot."""
    try:
        from db.client import db
        from bot.registry import get_all
        
        if not db.pool:
            return False
            
        # Get bot token
        bots = get_all()
        if bot_id not in bots:
            return False
            
        token = bots[bot_id].bot.token
        from bot.utils.crypto import hash_token
        token_hash = hash_token(token)
        
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT owner_user_id FROM bots WHERE token_hash = $1",
                token_hash
            )
            if row and row["owner_user_id"] == user_id:
                return True
    except Exception as e:
        logger.error(f"[ACCESS] Error checking clone owner: {e}")
    return False


async def is_telegram_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is a Telegram admin in the current chat."""
    if not update.effective_chat or not update.effective_user:
        return False
        
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception as e:
        logger.error(f"[ACCESS] Error checking admin status: {e}")
        return False


async def check_rate_limit_clone_owner(user_id: int) -> tuple[bool, str]:
    """
    Check if clone owner has exceeded rate limit.
    
    Returns:
        (allowed: bool, message: str)
    """
    import time
    
    now = time.time()
    
    if user_id not in _clone_owner_calls:
        _clone_owner_calls[user_id] = []
    
    # Clean old calls
    _clone_owner_calls[user_id] = [
        t for t in _clone_owner_calls[user_id] 
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(_clone_owner_calls[user_id]) >= RATE_LIMIT_MAX_CALLS:
        remaining = RATE_LIMIT_WINDOW - (now - _clone_owner_calls[user_id][0])
        return False, f"⏳ Rate limit exceeded. Please wait {int(remaining)} seconds."
    
    _clone_owner_calls[user_id].append(now)
    return True, ""


def require_admin_or_owner(operation: str = None):
    """
    Decorator for handlers that require admin privileges.
    
    Main bot owner (overlord) bypasses all checks.
    Clone owners must be Telegram admins to affect groups.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not update.effective_user or not update.effective_chat:
                return
                
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            # Main bot owner always allowed
            if await check_main_bot_owner(user_id):
                return await func(update, context)
            
            # Check if it's a clone bot
            is_clone = context.bot_data.get("is_primary", False) is False
            
            if is_clone:
                # Check if user is clone owner
                is_owner = await check_clone_owner(user_id, context.bot.id)
                
                if is_owner:
                    # Check rate limiting for clone owners
                    allowed, msg = await check_rate_limit_clone_owner(user_id)
                    if not allowed:
                        await update.message.reply_text(msg)
                        return
                    
                    # For admin-only operations, clone owner must also be Telegram admin
                    if operation in ADMIN_ONLY_OPERATIONS:
                        if not await is_telegram_admin(update, context):
                            await update.message.reply_text(
                                "⛔ You need to be a Telegram admin to perform this action in this group.\n\n"
                                "Clone owners can manage their bot's settings globally, "
                                "but group-affecting operations require admin privileges."
                            )
                            return
                else:
                    # Not clone owner - check regular permissions
                    if not await is_telegram_admin(update, context):
                        await update.message.reply_text("⛔ This command requires admin privileges.")
                        return
            else:
                # Main bot - require admin
                if not await is_telegram_admin(update, context):
                    await update.message.reply_text("⛔ This command requires admin privileges.")
                    return
            
            return await func(update, context)
        return wrapper
    return decorator


def require_main_bot_owner():
    """Decorator for handlers that only the main bot owner can use."""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not update.effective_user:
                return
                
            user_id = update.effective_user.id
            
            if not await check_main_bot_owner(user_id):
                await update.message.reply_text("⛔ This command is restricted to the bot owner.")
                return
                
            return await func(update, context)
        return wrapper
    return decorator


def require_clone_owner():
    """Decorator for handlers that require clone ownership."""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not update.effective_user:
                return
                
            user_id = update.effective_user.id
            
            # Main bot owner also allowed
            if await check_main_bot_owner(user_id):
                return await func(update, context)
            
            # Check clone ownership
            if not await check_clone_owner(user_id, context.bot.id):
                await update.message.reply_text("⛔ This command requires bot ownership.")
                return
            
            # Check rate limit
            allowed, msg = await check_rate_limit_clone_owner(user_id)
            if not allowed:
                await update.message.reply_text(msg)
                return
                
            return await func(update, context)
        return wrapper
    return decorator


async def can_affect_group(user_id: int, chat_id: int, bot_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if user can perform actions that affect a group.
    
    Clone owners must be Telegram admins in the group.
    """
    # Main bot owner can do anything
    if await check_main_bot_owner(user_id):
        return True
    
    # Check if user is Telegram admin
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ["administrator", "creator"]:
            return True
    except Exception:
        pass
    
    # Clone owners without admin status cannot affect groups
    if await check_clone_owner(user_id, bot_id):
        return False
    
    return False


class AccessLevel:
    """Access level constants."""
    OVERLORD = "overlord"  # Main bot owner
    CLONE_OWNER_ADMIN = "clone_owner_admin"  # Clone owner + Telegram admin
    CLONE_OWNER = "clone_owner"  # Clone owner only
    ADMIN = "admin"  # Telegram admin
    MEMBER = "member"  # Regular member
    

async def get_access_level(user_id: int, chat_id: int, bot_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Get the access level of a user."""
    
    # Check overlord
    if await check_main_bot_owner(user_id):
        return AccessLevel.OVERLORD
    
    is_clone_owner = await check_clone_owner(user_id, bot_id)
    is_admin = False
    
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        is_admin = member.status in ["administrator", "creator"]
    except Exception:
        pass
    
    if is_clone_owner and is_admin:
        return AccessLevel.CLONE_OWNER_ADMIN
    elif is_clone_owner:
        return AccessLevel.CLONE_OWNER
    elif is_admin:
        return AccessLevel.ADMIN
    else:
        return AccessLevel.MEMBER
