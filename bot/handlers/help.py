import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

HELP_CATEGORIES = {
    "🛡️ Moderation": [
        "/warn - Warn a user",
        "/unwarn - Remove a warning",
        "/mute - Mute a user",
        "/unmute - Unmute a user",
        "/ban - Ban a user",
        "/unban - Unban a user",
        "/kick - Kick a user",
        "/purge - Delete recent messages",
        "/pin - Pin a message",
        "/unpin - Unpin the pinned message",
    ],
    "🚫 Anti-Spam": [
        "!antispam - Enable anti-spam",
        "!!antispam - Disable anti-spam",
        "!antiflood - Enable anti-flood",
        "!antilink - Enable anti-link",
    ],
    "👋 Greetings": [
        "/setwelcome - Set welcome message",
        "/setgoodbye - Set goodbye message",
        "/welcome - Preview welcome message",
        "/goodbye - Preview goodbye message",
        "/rules - Show group rules",
        "/setrules - Set group rules",
    ],
    "🔒 Security": [
        "!captcha - Enable captcha",
        "!antiraid - Enable anti-raid mode",
        "/slowmode - Set slow mode delay",
        "/setflood - Set flood limit",
        "/addfilter - Add word filter",
        "/delfilter - Remove word filter",
    ],
    "📢 Channel": [
        "/channelpost - Post to linked channel",
        "/schedulepost - Schedule a channel post",
        "/announce - Send announcement",
        "/pinmessage - Pin custom message",
    ],
    "📊 Analytics": [
        "/stats - Show group statistics",
        "/admininfo - Show detailed group info",
        "/exportsettings - Export settings",
    ],
    "📝 Content": [
        "/filters - List word filters",
        "/poll - Create a poll",
    ],
    "🎮 Fun": [
        "/afk - Set AFK status",
        "/back - Clear AFK status",
        "/dice - Roll a dice",
        "/coin - Flip a coin",
        "/choose - Randomly choose",
        "/8ball - Magic 8-ball",
        "/roll - Roll random number",
        "/joke - Get a joke",
        "/quote - Get a quote",
        "/roast - Playful roast",
        "/compliment - Give compliment",
        "/calc - Calculator",
    ],
    "🔧 Utilities": [
        "/panel - Open mini app panel",
        "/help - Show this help",
        "/id - Get chat/user ID",
        "/info - Show group info",
        "/admins - List admins",
        "/report - Report a message",
        "/privacy - View privacy policy",
    ],
    "📢 Admin Requests": [
        "@admins - Mention to request admin help",
        "/admin_requests - View open requests (admin)",
        "/admin_req_stats - Request statistics (admin)",
        "/set_admin_requests - Configure @admins (admin)",
    ],
}


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import settings

    # Get miniapp URL
    miniapp_url = settings.mini_app_url

    if context.args:
        arg = context.args[0].lower()
        if arg == "modules":
            await help_modules(update, context)
            return

        # Check if it is a category
        for cat, cmds in HELP_CATEGORIES.items():
            if arg in cat.lower():
                text = f"⚡ *Nexus Help: {cat}*\n\n" + "\n".join(cmds)
                text += (
                    f'\n\n📱 <a href="{miniapp_url}">Open Mini App for detailed configuration</a>'
                    if miniapp_url
                    else ""
                )
                await update.message.reply_text(
                    text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
                )
                return

        # Check if it is a command
        await update.message.reply_text(
            f"Detailed help for `{arg}` is coming soon. Use the Mini App for complete command documentation.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    keyboard = [
        [InlineKeyboardButton("📱 Open Mini App", url=miniapp_url)] if miniapp_url else [],
        [
            InlineKeyboardButton("🛡️ Moderation", callback_data="help_mod"),
            InlineKeyboardButton("🚫 Anti-Spam", callback_data="help_spam"),
        ],
        [
            InlineKeyboardButton("👋 Greetings", callback_data="help_greet"),
            InlineKeyboardButton("🔒 Security", callback_data="help_sec"),
        ],
        [
            InlineKeyboardButton("📢 Channel", callback_data="help_chan"),
            InlineKeyboardButton("📊 Analytics", callback_data="help_ana"),
        ],
        [
            InlineKeyboardButton("📝 Content", callback_data="help_cont"),
            InlineKeyboardButton("🎮 Fun", callback_data="help_fun"),
        ],
        [
            InlineKeyboardButton("🔧 Utilities", callback_data="help_util"),
            InlineKeyboardButton("📢 Admin Requests", callback_data="help_areq"),
        ],
        [InlineKeyboardButton("⌨️ All Commands", callback_data="help_all")],
    ]

    # Filter out empty rows
    keyboard = [row for row in keyboard if row]

    reply_markup = InlineKeyboardMarkup(keyboard)

    help_text = (
        "⚡ *Nexus Help System*\n\nChoose a category or open the Mini App for detailed configuration:\n\n"
        + (
            f"📱 Full command documentation with descriptions and examples available in the [Mini App]({miniapp_url})"
            if miniapp_url
            else ""
        )
    )

    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def help_modules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data["db_pool"]
    chat_id = update.effective_chat.id

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT modules FROM groups WHERE chat_id = $1", chat_id)
        modules = {}
        if row and row["modules"]:
            modules = row["modules"]
            if isinstance(modules, str):
                modules = json.loads(modules)

    text = "📦 *Nexus Modules Status*\n\n"
    for mod, enabled in modules.items():
        status = "✅ ON" if enabled else "❌ OFF"
        text += f"• `{mod}`: {status}\n"

    if not modules:
        text += "No modules configured yet."

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cat_map = {
        "help_mod": "🛡️ Moderation",
        "help_spam": "🚫 Anti-Spam",
        "help_greet": "👋 Greetings",
        "help_sec": "🔒 Security",
        "help_chan": "📢 Channel",
        "help_ana": "📊 Analytics",
        "help_cont": "📝 Content",
        "help_fun": "🎮 Fun",
        "help_util": "🔧 Utilities",
        "help_areq": "📢 Admin Requests",
    }

    cat = cat_map.get(query.data)
    if cat:
        cmds = HELP_CATEGORIES[cat]
        text = f"⚡ *Nexus Help: {cat}*\n\n" + "\n".join(cmds)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=query.message.reply_markup
        )
    elif query.data == "help_all":
        text = "⚡ *Nexus All Commands*\n\n"
        for cat, cmds in HELP_CATEGORIES.items():
            text += f"*{cat}*:\n" + "\n".join(cmds) + "\n\n"
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=query.message.reply_markup
        )
