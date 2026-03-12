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
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
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
      - Show welcome message
      - Buttons: Main bot | Support group | Mini App (if bot has webapp)

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

    log.info(f"[START] user={user.id} chat={chat.id} type={chat.type}")

    if chat.type == "private":
        # ── PRIVATE CHAT ──────────────────────────────────────────────
        msg = await get_message(
            key="start_private",
            group_id=None,
            variables={
                "first_name": user.first_name,
                "clone_name": bot_username,
            },
            db=db_pool
        )

        # Get miniapp URL for this bot if configured
        miniapp_url = settings.mini_app_url  # auto-constructed from RENDER_EXTERNAL_URL or MINI_APP_URL

        await update.message.reply_text(
            text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=support_keyboard(
                include_miniapp=bool(miniapp_url),
                miniapp_url=miniapp_url,
                include_docs=bool(settings.DOCS_URL)
            )
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
    Always redirects to main bot + support group.
    Shows docs link if DOCS_URL is configured.
    """
    user = update.effective_user
    chat = update.effective_chat
    db_pool = context.bot_data["db_pool"]
    bot_username = (await context.bot.get_me()).username

    log.info(f"[HELP] user={user.id} chat={chat.id}")

    msg = await get_message(
        key="help",
        group_id=chat.id if chat.type != "private" else None,
        variables={
            "clone_name": bot_username,
            "first_name": user.first_name,
        },
        db=db_pool
    )

    await update.message.reply_text(
        text=msg,
        parse_mode=ParseMode.HTML,
        reply_markup=support_keyboard(include_docs=True)
    )


# ── Handler objects to register in factory.py ────────────────────────────
start_handler = CommandHandler("start", handle_start)
help_handler  = CommandHandler("help",  handle_help)
