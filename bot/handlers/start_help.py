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

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from config import settings
from bot.utils.keyboards import support_keyboard, mini_app_keyboard
from bot.utils.messages import get_message
from db.ops.groups import get_or_create_group, get_group_miniapp_url

log = logging.getLogger("start_help")


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
    bot_username = (await context.bot.get_me()).username
    is_primary = context.bot_data.get("is_primary", False)

    log.info(f"[START] user={user.id} chat={chat.id} type={chat.type}")

    if chat.type == "private":
        # ── PRIVATE CHAT ──────────────────────────────────────────────
        # Check for start parameter
        start_param = context.args[0] if context.args else None
        
        if start_param == "clone":
            # Redirect to clone flow
            from bot.handlers.clone import clone_conversation
            await update.message.reply_text(
                "🤖 <b>Create Your Own Bot</b>\n\n"
                "Let's create your own branded Nexus bot! Follow the steps below:",
                parse_mode=ParseMode.HTML
            )
            # Let the clone handler take over
            return
        
        msg = await get_message(
            key="start_private",
            group_id=None,
            bot_id=context.bot.id,
            variables={
                "first_name": user.first_name,
                "clone_name": bot_username,
            },
            db=db_pool
        )

        # Get miniapp URL for this bot if configured
        miniapp_url = settings.mini_app_url

        # Build keyboard with clone option
        keyboard = [[InlineKeyboardButton("📱 Open Panel", web_app={"url": miniapp_url})]]
        
        # Add "Create Your Own Bot" button for primary bot
        if is_primary:
            keyboard.append([InlineKeyboardButton("🤖 Create Your Own Bot", callback_data="start_clone")])
        
        keyboard.append([
            InlineKeyboardButton("❓ Help", callback_data="help_main"),
            InlineKeyboardButton("💬 Support", url=f"https://t.me/{settings.MAIN_BOT_USERNAME}")
        ])

        await update.message.reply_text(
            text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    else:
        # ── GROUP CHAT ────────────────────────────────────────────────
        # Create group record silently
        if db_pool:
            await get_or_create_group(db_pool, chat.id, chat.title)

        # Try to DM the admin
        miniapp_url = None
        if db_pool:
            miniapp_url = await get_group_miniapp_url(db_pool, chat.id)

        dm_msg = await get_message(
            key="start_group_dm",
            group_id=chat.id,
            bot_id=context.bot.id,
            variables={
                "first_name": user.first_name,
                "clone_name": bot_username,
                "group_name": chat.title or "your group",
            },
            db=db_pool
        )

        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=dm_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=mini_app_keyboard(miniapp_url) if miniapp_url else support_keyboard()
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
                parse_mode=ParseMode.HTML
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
        db=db_pool
    )

    await update.message.reply_text(
        text=help_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=support_keyboard(include_docs=True)
    )


# ── Callback handlers for /start buttons ─────────────────────────────────
async def handle_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle callback queries from /start buttons.
    - start_clone: Start the clone conversation flow
    - help_main: Show help message
    """
    query = update.callback_query
    await query.answer()
    
    bot_username = (await context.bot.get_me()).username
    is_primary = context.bot_data.get("is_primary", False)
    
    if query.data == "start_clone":
        # Only allow clone creation on primary bot
        if not is_primary:
            await query.edit_message_text(
                "⛔ Clone creation is only available on the main Nexus bot.\n\n"
                f"Please use the main bot to create your own instance.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Import and trigger clone flow
        from bot.handlers.clone import clone_command_handler
        await clone_command_handler(update, context)
        
    elif query.data == "help_main":
        # Show help message
        await handle_help(update, context)


# ── Handler objects to register in factory.py ────────────────────────────
start_handler = CommandHandler("start", handle_start)
help_handler  = CommandHandler("help",  handle_help)
start_callback_handler = CallbackQueryHandler(handle_start_callback, pattern=r"^start_clone$|^help_main$")
