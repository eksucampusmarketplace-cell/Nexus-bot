import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

HELP_CATEGORIES = {
    "🛡️ Moderation": [
        "/warn [@user|reply] [reason] — Warn a user",
        "/unwarn [@user|reply] — Remove a warning",
        "/warns [@user|reply] — Show user warnings",
        "/resetwarns [@user|reply] — Clear all warnings",
        "/warnlimit <1-10> — Set max warnings before action",
        "/warnmode <mute|kick|ban> — Set action at max warns",
        "/mute [@user|reply] [duration] [reason] — Mute a user",
        "/unmute [@user|reply] — Unmute a user",
        "/tmute [@user|reply] <duration> — Temp mute",
        "/smute [@user|reply] [reason] — Silent mute",
        "/ban [@user|reply] [reason] — Ban a user",
        "/unban [@user|reply] — Unban a user",
        "/tban [@user|reply] <duration> — Temp ban",
        "/sban [@user|reply] [reason] — Silent ban",
        "/kick [@user|reply] [reason] — Kick a user",
        "/skick [@user|reply] [reason] — Silent kick",
        "/purge [count] — Delete recent messages",
        "/del — Delete replied message",
        "/delall [@user|reply] — Delete user's recent messages",
        "/purgeme <count> — Delete your own messages",
        "/restrict [@user|reply] — Restrict user (no media)",
        "/unrestrict [@user|reply] — Remove restrictions",
    ],
    "👮 Admin Tools": [
        "/promote [@user|reply] — Promote to admin",
        "/demote [@user|reply] — Demote admin",
        "/title [@user|reply] <title> — Set admin title",
        "/admins — List all admins",
        "/pinmsg — Pin replied message",
        "/unpinmsg — Unpin pinned message",
        "/unpinall — Unpin all messages",
        "/id — Show user/chat ID",
        "/info — Show user/group info",
        "/groupinfo — Detailed group info",
        "/stats — Group statistics",
        "/invitelink — Get invite link",
        "/revoke — Revoke and regenerate invite link",
    ],
    "🔒 Locks & Filters": [
        "/lock <type> — Lock a message type",
        "/unlock <type> — Unlock a message type",
        "/locks — Show all lock states",
        "/filter <keyword> <response> — Add keyword auto-reply",
        "/filters — List all keyword filters",
        "/stop <keyword> — Remove a keyword filter",
        "/stopall — Remove all filters (owner only)",
        "/blacklist <word> — Add word to blacklist",
        "/unblacklist <word> — Remove word from blacklist",
        "/blacklistmode <action> — Set blacklist action",
    ],
    "👋 Greetings": [
        "/setwelcome [text] — Set welcome message",
        "/setgoodbye [text] — Set goodbye message",
        "/setrules [text] — Set group rules",
        "/welcome — Preview welcome message",
        "/goodbye — Preview goodbye message",
        "/rules — Show group rules",
        "/resetwelcome — Reset to default welcome",
        "/resetgoodbye — Reset to default goodbye",
        "/resetrules — Reset to default rules",
    ],
    "🛡️ Security": [
        "!captcha on/off — Enable/disable captcha",
        "!antiraid on/off — Enable/disable anti-raid",
        "!antispam on/off — Enable/disable anti-spam",
        "!antiflood on/off — Enable/disable anti-flood",
        "!antilink on/off — Enable/disable anti-link",
        "/setpassword <pass> — Set group entry password",
        "/clearpassword — Remove entry password",
        "/antiraid — Manage anti-raid settings",
        "/captcha — Configure captcha",
    ],
    "📝 Notes": [
        "/savenote <name> [text] — Save a note (reply to save media)",
        "/note <name> — Retrieve a saved note",
        "/notes — List all saved notes",
        "/delnote <name> — Delete a note",
    ],
    "📢 Channel & Schedule": [
        "/channelpost — Post to linked channel",
        "/schedulepost — Schedule a channel post",
        "/approvepost — Approve pending post",
        "/cancelpost — Cancel scheduled post",
        "/editpost — Edit a scheduled post",
        "/deletepost — Delete a scheduled post",
        "/setlog <channel> — Set log channel",
        "/unsetlog — Remove log channel",
    ],
    "📊 Stats & Info": [
        "/stats — Group statistics",
        "/info [@user|reply] — Show user info",
        "/id — Show chat/user ID",
        "/groupinfo — Group info",
        "/adminlist — List all admins",
        "/staff — Same as /adminlist",
        "/time — Show current time",
    ],
    "⚙️ Bot Management": [
        "/panel — Open Mini App control panel",
        "/setup — Re-run setup wizard",
        "/copysettings — Copy settings to another group",
        "/export — Export group settings",
        "/import — Import group settings",
        "/reset — Reset all settings",
        "/help — Show this message",
        "/privacy — View privacy policy",
    ],
}


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import settings

    miniapp_url = settings.mini_app_url
    bot_username = context.bot.bot.username

    keyboard = []
    row = []
    for i, category in enumerate(HELP_CATEGORIES.keys()):
        row.append(InlineKeyboardButton(category, callback_data=f"help:{i}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("📱 Open Panel", web_app=WebAppInfo(url=miniapp_url))])

    await update.message.reply_text(
        f"⚡ <b>{bot_username} Help</b>\n\nChoose a category:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("help:"):
        parts = data.split(":")
        if len(parts) == 2:
            idx = parts[1]
            if idx == "back":
                await help_handler(update, context)
                return
            try:
                idx = int(idx)
                categories = list(HELP_CATEGORIES.items())
                if 0 <= idx < len(categories):
                    name, cmds = categories[idx]
                    text = f"<b>{name}</b>\n\n" + "\n".join(f"• {c}" for c in cmds)
                    back_btn = InlineKeyboardButton("← Back", callback_data="help:back")
                    await query.edit_message_text(
                        text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup([[back_btn]]),
                    )
            except (ValueError, IndexError):
                pass


# Export handlers
help_command = CommandHandler("help", help_handler)
help_callback = CallbackQueryHandler(help_callback_handler, pattern="^help:")
