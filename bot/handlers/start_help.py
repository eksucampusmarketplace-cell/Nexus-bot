"""
bot/handlers/start_help.py

Handles /start and /help for ALL bots (primary + every clone).
These handlers are registered in factory.py for every bot instance.

Key behaviors:
  - /start in private: show welcome + support keyboard
  - /start in group: silently init group, DM the adding admin
  - /help anywhere: show help message + support keyboard
  - "Powered by {bot_name}" always present via get_message()
  - All button URLs come from keyboards.py (never hardcoded here)
"""

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.utils.keyboards import mini_app_keyboard, support_keyboard
from bot.utils.messages import get_message
from config import settings
from db.ops.groups import get_group_miniapp_url, get_or_create_group

log = logging.getLogger("start_help")

# ── Help categories for detailed /help callback navigation ────────────────
HELP_CATEGORIES = {
    "\U0001f6e1\ufe0f Moderation": [
        "/warn [@user|reply] [reason] \u2014 Warn a user",
        "/unwarn [@user|reply] \u2014 Remove a warning",
        "/warns [@user|reply] \u2014 Show user warnings",
        "/mute [@user|reply] [duration] [reason] \u2014 Mute a user",
        "/unmute [@user|reply] \u2014 Unmute a user",
        "/ban [@user|reply] [reason] \u2014 Ban a user",
        "/unban [@user|reply] \u2014 Unban a user",
        "/kick [@user|reply] [reason] \u2014 Kick a user",
        "/purge [count] \u2014 Delete recent messages",
    ],
    "\U0001f46e Admin Tools": [
        "/promote [@user|reply] \u2014 Promote to admin",
        "/demote [@user|reply] \u2014 Demote admin",
        "/admins \u2014 List all admins",
        "/id \u2014 Show user/chat ID",
        "/info \u2014 Show user/group info",
    ],
    "\U0001f510 Locks & Filters": [
        "/lock <type> \u2014 Lock a message type",
        "/unlock <type> \u2014 Unlock a message type",
        "/filter <keyword> <response> \u2014 Add auto-reply",
        "/filters \u2014 List all keyword filters",
        "/blacklist <word> \u2014 Add word to blacklist",
    ],
    "\U0001f44b Greetings": [
        "/setwelcome [text] \u2014 Set welcome message",
        "/setgoodbye [text] \u2014 Set goodbye message",
        "/setrules [text] \u2014 Set group rules",
        "/welcome \u2014 Preview welcome message",
        "/rules \u2014 Show group rules",
    ],
    "\u2699\ufe0f Bot Management": [
        "/panel \u2014 Open Mini App control panel",
        "/export \u2014 Export group settings",
        "/import \u2014 Import group settings",
        "/reset \u2014 Reset all settings",
        "/help \u2014 Show this message",
    ],
}


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start handler. Works in both private and group chats.

    Private chat:
      - Show welcome message with inline clone option
      - Buttons: Open Panel | Create Your Own Bot | Help

    Group chat:
      - Do NOT reply publicly (avoid spam in group)
      - Silently create group record in DB if new
      - DM the admin who sent /start with setup instructions
      - If cannot DM (user never started bot): send brief group reply
        with link to DM the bot for setup
    """
    user = update.effective_user
    chat = update.effective_chat
    db_pool = context.bot_data["db_pool"]

    # Get bot username from cache to avoid API call
    cached_info = context.bot_data.get("cached_bot_info", {})
    bot_username = cached_info.get("username")
    if not bot_username:
        # Fallback to API call if cache miss
        bot_username = (await context.bot.get_me()).username

    is_primary = context.bot_data.get("is_primary", False)

    log.info(f"[START] user={user.id} chat={chat.id} type={chat.type}")

    if chat.type == "private":
        # ── PRIVATE CHAT ──────────────────────────────────────────────
        # Check for start parameter
        start_param = context.args[0] if context.args else None

        if start_param == "clone":
            # Redirect to clone flow - call the clone command handler directly
            from bot.handlers.clone import clone_command_handler

            return await clone_command_handler(update, context)

        msg = await get_message(
            key="start_private",
            group_id=None,
            bot_id=context.bot.id,
            variables={
                "first_name": user.first_name,
                "clone_name": bot_username,
            },
            db=db_pool,
        )

        # Get miniapp URL for this bot if configured
        miniapp_url = settings.mini_app_url

        # Build keyboard — guard against missing miniapp_url
        keyboard = []
        if miniapp_url:
            keyboard.append([InlineKeyboardButton("📱 Open Panel", web_app={"url": miniapp_url})])

        # Add "Create Your Own Bot" button for primary bot only
        if is_primary:
            keyboard.append(
                [InlineKeyboardButton("🤖 Create Your Own Bot", callback_data="start_clone")]
            )

        # Support button — only if we have a valid URL to link to
        support_url = settings.SUPPORT_GROUP_URL or (
            f"https://t.me/{settings.MAIN_BOT_USERNAME}" if settings.MAIN_BOT_USERNAME else None
        )
        help_row = [InlineKeyboardButton("❓ Help", callback_data="help_main")]
        if support_url:
            help_row.append(InlineKeyboardButton("💬 Support", url=support_url))
        keyboard.append(help_row)

        await update.message.reply_text(
            text=msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    else:
        # ── GROUP CHAT ────────────────────────────────────────────────
        miniapp_url = None
        dm_msg = None

        if db_pool:
            _, miniapp_url, dm_msg = await asyncio.gather(
                get_or_create_group(db_pool, chat.id, chat.title),
                get_group_miniapp_url(db_pool, chat.id),
                get_message(
                    key="start_group_dm",
                    group_id=chat.id,
                    bot_id=context.bot.id,
                    variables={
                        "first_name": user.first_name,
                        "clone_name": bot_username,
                        "group_name": chat.title or "your group",
                    },
                    db=db_pool,
                ),
            )
        else:
            dm_msg = await get_message(
                key="start_group_dm",
                group_id=chat.id,
                bot_id=context.bot.id,
                variables={
                    "first_name": user.first_name,
                    "clone_name": bot_username,
                    "group_name": chat.title or "your group",
                },
                db=None,
            )

        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=dm_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=mini_app_keyboard(miniapp_url) if miniapp_url else support_keyboard(),
            )
            # Brief confirmation in group
            await update.message.reply_text(
                f"✅ I've sent you setup instructions in DM, {user.first_name}!"
            )
        except Exception:
            # User hasn't started bot — can't DM
            await update.message.reply_text(
                f"👋 Hi! To set me up, please "
                f"<a href='https://t.me/{bot_username}?start=setup'>start a DM with me</a> first.",
                parse_mode=ParseMode.HTML,
            )

        log.info(f"[START] Group init | chat={chat.id} admin={user.id}")


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help handler. Works in private and group chats.
    Shows comprehensive command list with link to Mini App for full details.
    """
    user = update.effective_user
    chat = update.effective_chat
    db_pool = context.bot_data["db_pool"]

    # Get bot username from cache to avoid API call
    cached_info = context.bot_data.get("cached_bot_info", {})
    bot_username = cached_info.get("username")
    if not bot_username:
        # Fallback to API call if cache miss
        bot_username = (await context.bot.get_me()).username

    log.info(f"[HELP] user={user.id} chat={chat.id}")

    # Get miniapp URL
    miniapp_url = settings.mini_app_url
    if not miniapp_url and chat.type != "private":
        miniapp_url = await get_group_miniapp_url(db_pool, chat.id)

    help_text = await get_message(
        key="help",
        group_id=chat.id if chat.type != "private" else None,
        bot_id=context.bot.id,
        variables={
            "clone_name": bot_username,
            "miniapp_url": miniapp_url or "#",
        },
        db=db_pool,
    )

    await update.message.reply_text(
        text=help_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=support_keyboard(include_docs=True),
    )


# ── Callback handlers for /start buttons ─────────────────────────────────
async def handle_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle callback queries from /start buttons.
    - help_main: Show help message
    """
    query = update.callback_query
    await query.answer()

    if query.data == "help_main":
        # Show help message
        await handle_help(update, context)


async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help category navigation callbacks (help_0, help_1, etc.)."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("help_"):
        return

    suffix = data[5:]  # strip 'help_'
    if suffix == "back":
        # Re-show the category list
        keyboard = []
        row = []
        for i, category in enumerate(HELP_CATEGORIES.keys()):
            row.append(InlineKeyboardButton(category, callback_data=f"help_{i}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        await query.edit_message_text(
            "\u2753 <b>Help Categories</b>\n\nChoose a category:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    try:
        idx = int(suffix)
        categories = list(HELP_CATEGORIES.items())
        if 0 <= idx < len(categories):
            name, cmds = categories[idx]
            text = f"<b>{name}</b>\n\n" + "\n".join(f"\u2022 {c}" for c in cmds)
            back_btn = InlineKeyboardButton("\u2190 Back", callback_data="help_back")
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[back_btn]]),
            )
    except (ValueError, IndexError):
        pass


# ── Handler objects to register in factory.py ────────────────────────────
start_handler = CommandHandler("start", handle_start)
help_handler = CommandHandler("help", handle_help)
start_callback_handler = CallbackQueryHandler(
    handle_start_callback, pattern=r"^help_main$"
)
