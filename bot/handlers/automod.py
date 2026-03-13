import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from db.ops.groups import get_group, upsert_group
from db.ops.users import increment_message_count, upsert_user
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Simple in-memory flood tracking
flood_data = {} # {chat_id: {user_id: [timestamps]}}

# Default automod settings (same as in db/ops/groups.py)
DEFAULT_AUTOMOD = {
    "antiflood": {"enabled": True, "limit": 5, "window": 10, "action": "mute", "duration": 600},
    "antispam": {"enabled": True, "threshold": 3, "action": "warn"},
    "antilink": {"enabled": False, "whitelist": ["github.com", "stackoverflow.com"]},
    "captcha": {"enabled": True, "timeout": 120, "action": "kick"},
    "antibot": {"enabled": True, "min_age_days": 7}
}

DEFAULT_SETTINGS = {
    "automod": DEFAULT_AUTOMOD,
    "welcome": {"enabled": True, "text": "👋 Welcome {first_name}!", "delete_after": 60}
}

def get_setting(settings: dict, *keys, default=None):
    """Safely get nested settings value with fallback to defaults."""
    value = settings
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            # Fall back to default settings
            default_value = DEFAULT_SETTINGS
            for k in keys:
                if isinstance(default_value, dict) and k in default_value:
                    default_value = default_value[k]
                else:
                    return default
            return default_value
    return value if value is not None else default

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type == "private":
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    db_pool = context.bot_data.get("db_pool") or context.bot_data.get("db")

    # Track stats
    await upsert_user(user_id, chat_id, update.effective_user.username, update.effective_user.first_name)
    await increment_message_count(user_id, chat_id)

    # ── Trust Score: recalculate on every message ─────────────────────
    if db_pool:
        try:
            from bot.utils.trust_score import calculate_trust_score, apply_trust_consequences
            score = await calculate_trust_score(user_id, chat_id, db_pool)
            await apply_trust_consequences(user_id, chat_id, score, context)
        except Exception as _te:
            logger.debug(f"[AUTOMOD] Trust score update failed: {_te}")

    group = await get_group(chat_id)
    if not group:
        # Auto-register group if not exists
        await upsert_group(chat_id, update.effective_chat.title, "")
        return

    settings = group.get('settings') or {}

    # ── Advanced Automod Engine Check ───────────────────────────────────
    # Call the new advanced automod engine first
    from bot.automod.engine import check_message
    result = await check_message(update, context)
    if result.violated:
        return  # Message handled by engine

    # ── Legacy automod (for backward compatibility) ──────────────
    # 1. Anti-link
    antilink = get_setting(settings, 'automod', 'antilink')
    if antilink['enabled'] and update.message.text:
        import re
        links = re.findall(r'(https?://[^\s]+)', update.message.text)
        for link in links:
            whitelisted = False
            for domain in antilink['whitelist']:
                if domain in link:
                    whitelisted = True
                    break
            if not whitelisted:
                await update.message.delete()
                return

    # 2. Anti-flood
    antiflood = get_setting(settings, 'automod', 'antiflood')
    if antiflood['enabled']:
        now = datetime.now()
        if chat_id not in flood_data: flood_data[chat_id] = {}
        if user_id not in flood_data[chat_id]: flood_data[chat_id][user_id] = []

        timestamps = flood_data[chat_id][user_id]
        window = antiflood['window']
        limit = antiflood['limit']

        # Clean old timestamps
        timestamps = [t for t in timestamps if now - t < timedelta(seconds=window)]
        timestamps.append(now)
        flood_data[chat_id][user_id] = timestamps

        if len(timestamps) > limit:
            action = antiflood['action']
            duration = antiflood['duration']
            until = now + timedelta(seconds=duration)

            if action == "mute":
                await context.bot.restrict_chat_member(chat_id, user_id, permissions={"can_send_messages": False}, until_date=until)
                await update.message.reply_text(f"🔇 {update.effective_user.first_name} muted for flooding.")
            elif action == "kick":
                await context.bot.unban_chat_member(chat_id, user_id)
                await update.message.reply_text(f"👢 {update.effective_user.first_name} kicked for flooding.")
            return


# Anti-flood handler (for priority group 1)
async def antiflood_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for anti-flood checks - registered at priority group 1."""
    if not update.effective_chat or update.effective_chat.type == "private":
        return
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    group = await get_group(chat_id)
    if not group:
        return
    
    settings = group.get('settings') or {}
    # Ensure automod settings exist with defaults
    if 'automod' not in settings:
        settings = dict(settings)
        settings['automod'] = DEFAULT_AUTOMOD
    antiflood = get_setting(settings, 'automod', 'antiflood')
    
    if antiflood['enabled']:
        now = datetime.now()
        if chat_id not in flood_data:
            flood_data[chat_id] = {}
        if user_id not in flood_data[chat_id]:
            flood_data[chat_id][user_id] = []
        
        timestamps = flood_data[chat_id][user_id]
        window = antiflood['window']
        limit = antiflood['limit']
        
        # Clean old timestamps
        timestamps = [t for t in timestamps if now - t < timedelta(seconds=window)]
        timestamps.append(now)
        flood_data[chat_id][user_id] = timestamps
        
        if len(timestamps) > limit:
            action = antiflood['action']
            duration = antiflood['duration']
            until = now + timedelta(seconds=duration)
            
            if action == "mute":
                await context.bot.restrict_chat_member(chat_id, user_id, permissions={"can_send_messages": False}, until_date=until)
            elif action == "kick":
                await context.bot.unban_chat_member(chat_id, user_id)
            elif action == "ban":
                await context.bot.ban_chat_member(chat_id, user_id)


# Anti-spam handler (for priority group 2)
async def antispam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for anti-spam checks - registered at priority group 2."""
    if not update.effective_chat or update.effective_chat.type == "private":
        return
    if not update.message or not update.message.text:
        return
    
    # Simple spam detection - check for repeated messages
    # This is a placeholder - real implementation would check against spam databases
    pass


# Anti-link handler (for priority group 3)
async def antilink_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for anti-link checks - registered at priority group 3."""
    if not update.effective_chat or update.effective_chat.type == "private":
        return
    if not update.message or not update.message.text:
        return
    
    chat_id = update.effective_chat.id
    
    group = await get_group(chat_id)
    if not group:
        return
    
    settings = group.get('settings') or {}
    # Ensure automod settings exist with defaults
    if 'automod' not in settings:
        settings = dict(settings)
        settings['automod'] = DEFAULT_AUTOMOD
    antilink = get_setting(settings, 'automod', 'antilink')
    
    if antilink['enabled']:
        import re
        links = re.findall(r'(https?://[^\s]+)', update.message.text)
        for link in links:
            whitelisted = False
            for domain in antilink['whitelist']:
                if domain in link:
                    whitelisted = True
                    break
            if not whitelisted:
                try:
                    await update.message.delete()
                except:
                    pass
                return

async def member_join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = await get_group(chat_id)
    if not group: return
    
    settings = group.get('settings') or {}
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        
        # Anti-bot
        antibot = get_setting(settings, 'automod', 'antibot')
        if antibot['enabled']:
            # min_age_days check is hard via TG API directly without extra info
            # but we can check for username
            if not member.username:
                await context.bot.unban_chat_member(chat_id, member.id)
                return

        # Captcha
        captcha = get_setting(settings, 'automod', 'captcha')
        if captcha['enabled']:
            from bot.handlers.captcha import send_captcha
            await send_captcha(update, context, member)
        
        # Welcome message
        else:
            welcome = get_setting(settings, 'welcome')
            if welcome['enabled']:
                text = welcome['text'].format(first_name=member.first_name, last_name=member.last_name or "", username=member.username or "")
                msg = await update.message.reply_text(text)
                if welcome['delete_after'] > 0:
                    context.job_queue.run_once(delete_msg, welcome['delete_after'], data=(chat_id, msg.message_id))

async def delete_msg(context: ContextTypes.DEFAULT_TYPE):
    chat_id, msg_id = context.job.data
    try:
        await context.bot.delete_message(chat_id, msg_id)
    except:
        pass
