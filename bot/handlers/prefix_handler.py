import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

"""
Triple prefix system:
  !command  → ENABLE/ACTIVATE a module or feature
  !!command → DISABLE/DEACTIVATE a module or feature
  /command  → EXECUTE a one-time action (standard Telegram commands)

The prefix handler runs at handler group 0 — highest priority.
It intercepts ! and !! prefixed messages, maps them to module names,
and calls the same enable/disable logic as the Mini App toggle.
"""

# Map of prefix command names to module names
PREFIX_COMMAND_MAP = {
    "welcome":    "welcome_message",
    "goodbye":    "goodbye_message",
    "antiflood":  "antiflood",
    "antispam":   "antispam",
    "antilink":   "antilink",
    "captcha":    "captcha",
    "warn":       "warn_system",
    "trust":      "trust_score",
    "ai":         "ai_moderation",
    "analytics":  "activity_tracking",
    "sentiment":  "sentiment_analysis",
    "notes":      "notes_system",
    "afk":        "afk_system",
    "polls":      "poll_manager",
    "pins":       "pin_manager",
    "autoban":    "auto_ban",
    "timedmute":  "timed_mute",
    "timedban":   "timed_ban",
    "silent":     "silent_mode",
    "require_reason": "require_reason",
    "reputation": "reputation_system",
    "antiraid":   "anti_raid",
    "globalban":  "global_ban_sync",
    "newaccount": "new_account_filter",
    "suspicious": "suspicious_activity_alert",
    "welcomedm":  "welcome_dm",
    "muteonjoin": "mute_on_join",
    "deleteoldwelcome": "delete_old_welcome",
    "autodeletewelcome": "auto_delete_welcome",
    "wordfilter": "word_filter",
    "linkwhitelist": "link_whitelist",
    "mediawhitelist": "media_whitelist",
    "spoilerfilter": "spoiler_filter",
    "translationfilter": "translation_filter",
    "autopost": "auto_post",
    "scheduledposts": "scheduled_posts",
    "posttochannel": "post_to_channel",
    "channelcomments": "channel_comments_mod",
    "linkedchannelsync": "linked_channel_sync",
    "postapproval": "post_approval",
    "activitytracking": "activity_tracking",
    "sentimentanalysis": "sentiment_analysis",
    "growthtracking": "growth_tracking",
    "memberheatmap": "member_heatmap",
    "rulescommand": "rules_command",
    "afksystem": "afk_system",
    "pollmanager": "poll_manager",
    "notessystem": "notes_system",
    "pinmanager": "pin_manager"
}

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == 'private':
        return True
    member = await chat.get_member(user.id)
    return member.status in ['creator', 'administrator']

async def prefix_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text or ""

    if text.startswith("!!"):
        command = text[2:].split()[0].lower()
        action = "disable"
    elif text.startswith("!"):
        command = text[1:].split()[0].lower()
        action = "enable"
    else:
        return  # not a prefix command, let other handlers process it

    module_name = PREFIX_COMMAND_MAP.get(command)

    if not module_name:
        await update.message.reply_text(
            f"⚠️ `{command}` is not a toggleable module.\n"
            f"Use `/help modules` to see all toggleable features.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Check admin permission
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ Only admins can toggle modules.")
        return

    enabled = action == "enable"
    db_pool = context.bot_data["db_pool"]
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT modules FROM groups WHERE chat_id = $1", update.effective_chat.id)
        import json
        modules = {}
        if row and row['modules']:
            modules = row['modules']
            if isinstance(modules, str):
                modules = json.loads(modules)
        
        modules[module_name] = enabled
        
        await conn.execute(
            "UPDATE groups SET modules = $1 WHERE chat_id = $2",
            json.dumps(modules), update.effective_chat.id
        )

    status = "✅ Enabled" if enabled else "❌ Disabled"
    await update.message.reply_text(
        f"{status}: `{module_name}`",
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(
        f"[PREFIX] Module toggled | "
        f"chat_id={update.effective_chat.id} | "
        f"module={module_name} | "
        f"enabled={enabled} | "
        f"by=user_id={update.effective_user.id}"
    )
    # Stop other handlers
    from telegram.ext import Application
    # raise ApplicationHandlerStop() - Wait, this is for MessageHandler, but PTB does not have ApplicationHandlerStop() like this. 
    # Actually, the group 0 prefix_handler will not block other handlers unless it is intended.
    # But since it's a command like action, we might want to stop here.
