"""
bot/antiraid/message_spam.py

Handler for detecting coordinated message spam (multiple accounts sending similar messages).
Monitors first messages from new members for spam patterns and similarity to other recent messages.
"""

import logging
import re
from difflib import SequenceMatcher

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from db.client import db

log = logging.getLogger("antiraid_msg")

# Minimum similarity threshold for flagging similar messages
SIMILARITY_THRESHOLD = 0.8

# Time window to check for similar messages (seconds)
MESSAGE_WINDOW_SECONDS = 300  # 5 minutes


async def handle_message_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Check new messages for spam patterns:
    1. First message from a user (potential spam)
    2. Check similarity to other recent messages in the chat
    3. Check for forwarded messages from same origin
    """
    if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
        return
    
    if not update.effective_message or not update.effective_user:
        return
    
    message = update.effective_message
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Get message text
    text = message.text or message.caption or ""
    if not text or len(text.strip()) < 3:
        return
    
    # Skip if user is admin
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ["administrator", "creator"]:
            return
    except Exception:
        pass
    
    redis = context.bot_data.get("redis")
    if not redis:
        return
    
    try:
        from bot.antiraid.detector import estimate_account_age_from_id
        from bot.antiraid.detector import matches_spam_name_pattern
        
        # 1. Get user's account age
        account_age = estimate_account_age_from_id(user_id)
        
        # 2. Check if this is potentially a coordinated spam message
        # Get recent messages from Redis
        key = f"nexus:spam:messages:{chat_id}"
        
        # Get recent message data
        import time
        now = time.time()
        
        recent_msgs = await redis.zrangebyscore(key, now - MESSAGE_WINDOW_SECONDS, now)
        
        similar_user_ids = []
        spam_origin = None
        
        for msg_data in recent_msgs:
            try:
                # Format: "user_id:message_hash:text_preview"
                parts = msg_data.split(b"|", 2)
                if len(parts) < 2:
                    continue
                
                other_user_id = int(parts[0])
                if other_user_id == user_id:
                    continue
                
                # Compare message similarity
                if len(parts) > 2:
                    other_text = parts[2].decode('utf-8', errors='ignore')
                    similarity = SequenceMatcher(None, text.lower().strip(), other_text.lower().strip()).ratio()
                    
                    if similarity >= SIMILARITY_THRESHOLD:
                        similar_user_ids.append(other_user_id)
                
                # Check forward origin similarity (if this message has forward info)
                if message.forward_date and message.forward_origin:
                    if len(parts) > 1:
                        other_origin = parts[1].decode('utf-8', errors='ignore')
                        current_origin = str(getattr(message.forward_origin, 'identifier', '') or 
                                          getattr(message.forward_origin, 'chat', '') or '')
                        if other_origin == current_origin and other_origin:
                            spam_origin = current_origin
                            
            except Exception as e:
                log.debug(f"Error checking message similarity: {e}")
        
        # 3. Store this message for future comparison
        import json
        
        # Create a preview of the message (first 100 chars)
        text_preview = text[:100].replace("|", " ")
        
        # Get forward origin if present
        forward_origin = ""
        if message.forward_origin:
            forward_origin = str(getattr(message.forward_origin, 'identifier', '') or 
                               getattr(message.forward_origin, 'chat', '') or 
                               getattr(message.forward_origin, 'type', ''))
        
        store_data = f"{user_id}|{forward_origin}|{text_preview}"
        await redis.zadd(key, {store_data: now})
        await redis.zremrangebyscore(key, 0, now - MESSAGE_WINDOW_SECONDS)
        
        # 4. Analyze and take action if spam detected
        if len(similar_user_ids) >= 2:
            # Multiple users sending similar messages - likely coordinated spam
            log.warning(
                f"[ANTIRAID_MSG] Coordinated spam detected in {chat_id}: "
                f"user {user_id} sent similar message to {len(similar_user_ids)} other users"
            )
            
            # Delete the spam message
            try:
                await message.delete()
                log.info(f"[ANTIRAID_MSG] Deleted spam message from {user_id} in {chat_id}")
            except Exception as e:
                log.debug(f"Failed to delete spam message: {e}")
            
            # Warn the user
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Your message was removed as it appears to be spam. "
                         f"If you believe this is an error, contact the admins.",
                )
            except Exception:
                pass
            
            # Record the spam signal
            try:
                from bot.ml.signal_collector import record_spam_signal
                _bg_task = __import__('asyncio').create_task(
                    record_spam_signal(user_id, chat_id, text, "message_similarity", "spam", 0.9)
                )
            except Exception:
                pass
            
        elif spam_origin and len(similar_user_ids) >= 1:
            # Multiple users forwarding from same origin
            log.warning(
                f"[ANTIRAID_MSG] Forward spam detected in {chat_id}: "
                f"user {user_id} forwarded from {spam_origin}"
            )
            
            try:
                await message.delete()
            except Exception:
                pass
            
    except Exception as e:
        log.debug(f"Message spam check failed: {e}")


def register_message_spam_handler(app):
    """Register the message spam handler with the application."""
    GROUP = filters.ChatType.GROUPS
    
    # Only process text messages from regular users (not commands)
    app.add_handler(
        MessageHandler(
            GROUP & filters.TEXT & ~filters.COMMAND,
            handle_message_spam,
        ),
        group=7  # After message_guard (group=6)
    )
