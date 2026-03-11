import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from db.ops.groups import get_group, upsert_group
from db.ops.users import increment_message_count, upsert_user
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Simple in-memory flood tracking
flood_data = {} # {chat_id: {user_id: [timestamps]}}

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type == "private":
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Track stats
    await upsert_user(user_id, chat_id, update.effective_user.username, update.effective_user.first_name)
    await increment_message_count(user_id, chat_id)
    
    group = await get_group(chat_id)
    if not group:
        # Auto-register group if not exists
        await upsert_group(chat_id, update.effective_chat.title, "")
        return

    automod = group['settings']['automod']
    
    # 1. Anti-link
    if automod['antilink']['enabled'] and update.message.text:
        import re
        links = re.findall(r'(https?://[^\s]+)', update.message.text)
        for link in links:
            whitelisted = False
            for domain in automod['antilink']['whitelist']:
                if domain in link:
                    whitelisted = True
                    break
            if not whitelisted:
                await update.message.delete()
                return

    # 2. Anti-flood
    if automod['antiflood']['enabled']:
        now = datetime.now()
        if chat_id not in flood_data: flood_data[chat_id] = {}
        if user_id not in flood_data[chat_id]: flood_data[chat_id][user_id] = []
        
        timestamps = flood_data[chat_id][user_id]
        window = automod['antiflood']['window']
        limit = automod['antiflood']['limit']
        
        # Clean old timestamps
        timestamps = [t for t in timestamps if now - t < timedelta(seconds=window)]
        timestamps.append(now)
        flood_data[chat_id][user_id] = timestamps
        
        if len(timestamps) > limit:
            action = automod['antiflood']['action']
            duration = automod['antiflood']['duration']
            until = now + timedelta(seconds=duration)
            
            if action == "mute":
                await context.bot.restrict_chat_member(chat_id, user_id, permissions={"can_send_messages": False}, until_date=until)
                await update.message.reply_text(f"🔇 {update.effective_user.first_name} muted for flooding.")
            elif action == "kick":
                await context.bot.unban_chat_member(chat_id, user_id)
                await update.message.reply_text(f"👢 {update.effective_user.first_name} kicked for flooding.")
            return

async def member_join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = await get_group(chat_id)
    if not group: return
    
    settings = group['settings']
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        
        # Anti-bot
        if settings['automod']['antibot']['enabled']:
            # min_age_days check is hard via TG API directly without extra info
            # but we can check for username
            if not member.username:
                await context.bot.unban_chat_member(chat_id, member.id)
                return

        # Captcha
        if settings['automod']['captcha']['enabled']:
            from bot.handlers.captcha import send_captcha
            await send_captcha(update, context, member)
        
        # Welcome message
        elif settings['welcome']['enabled']:
            text = settings['welcome']['text'].format(first_name=member.first_name, last_name=member.last_name or "", username=member.username or "")
            msg = await update.message.reply_text(text)
            if settings['welcome']['delete_after'] > 0:
                context.job_queue.run_once(delete_msg, settings['welcome']['delete_after'], data=(chat_id, msg.message_id))

async def delete_msg(context: ContextTypes.DEFAULT_TYPE):
    chat_id, msg_id = context.job.data
    try:
        await context.bot.delete_message(chat_id, msg_id)
    except:
        pass
