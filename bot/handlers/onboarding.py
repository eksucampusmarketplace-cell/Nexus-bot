"""
Onboarding flow for new groups
Guides admins through initial bot setup
"""

import logging
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import db.ops.groups as db_groups

logger = logging.getLogger(__name__)

# Conversation states
LANGUAGE, MODULES, WELCOME, COMPLETE = range(4)


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start onboarding when bot is added to a group"""
    chat = update.effective_chat
    user = update.effective_user

    # Only start for admins
    try:
        member = await chat.get_member(user.id)
        if member.status not in ("administrator", "creator"):
            return
    except Exception:
        return

    logger.info(f"[ONBOARDING] Starting for chat {chat.id}")

    keyboard = [
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang:en")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang:es")],
        [InlineKeyboardButton("Skip Setup", callback_data="skip")],
    ]

    await update.message.reply_text(
        f"👋 Welcome! I'm {context.bot.bot.username}, your group management bot.\n\n"
        "Let's get you set up. First, choose your language:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return LANGUAGE


async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection"""
    query = update.callback_query
    await query.answer()

    if query.data == "skip":
        await query.edit_message_text("Setup skipped. You can run /setup anytime to configure.")
        return ConversationHandler.END

    lang = query.data.split(":")[1]
    context.user_data["onboarding_lang"] = lang

    keyboard = [
        [InlineKeyboardButton("✅ Enable All", callback_data="modules:all")],
        [InlineKeyboardButton("🛡️ Moderation Only", callback_data="modules:mod")],
        [InlineKeyboardButton("🎵 Music Only", callback_data="modules:music")],
        [InlineKeyboardButton("🎮 Games Only", callback_data="modules:games")],
        [InlineKeyboardButton("⏭️ Skip", callback_data="skip")],
    ]

    await query.edit_message_text(
        "🛠️ Which features would you like to enable?\n\n" "You can change these later in settings.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return MODULES


async def handle_modules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle module selection"""
    query = update.callback_query
    await query.answer()

    if query.data == "skip":
        await query.edit_message_text("Setup skipped. You can run /setup anytime to configure.")
        return ConversationHandler.END

    modules = query.data.split(":")[1]
    context.user_data["onboarding_modules"] = modules

    keyboard = [
        [InlineKeyboardButton("Set Welcome Message", callback_data="welcome:set")],
        [InlineKeyboardButton("Use Default", callback_data="welcome:default")],
        [InlineKeyboardButton("Skip", callback_data="skip")],
    ]

    await query.edit_message_text(
        "💬 Would you like to set a custom welcome message for new members?\n\n"
        "You can also send a photo/gif/video to include media!",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return WELCOME


async def handle_welcome_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle welcome message choice"""
    query = update.callback_query
    await query.answer()

    if query.data == "skip":
        await complete_onboarding(update, context, skipped=True)
        return ConversationHandler.END

    if query.data == "welcome:default":
        # Save default welcome
        chat_id = update.effective_chat.id
        pool = context.bot_data.get("db_pool")
        if pool:
            await db_groups.set_group_setting(
                pool,
                chat_id,
                welcome_message="Welcome {mention}! 👋\nPlease read the rules and enjoy your stay!",
            )
        await complete_onboarding(update, context)
        return ConversationHandler.END

    await query.edit_message_text(
        "Please send your welcome message now.\n\n"
        "You can use:\n"
        "• {mention} - mentions the user\n"
        "• {username} - user's name\n"
        "• {group} - group name\n\n"
        "Send /cancel to skip."
    )

    return WELCOME


async def handle_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom welcome message"""
    chat_id = update.effective_chat.id
    pool = context.bot_data.get("db_pool")

    if not pool:
        await update.message.reply_text("⚠️ Database error. Please try again later.")
        return ConversationHandler.END

    # Check for media
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        await db_groups.set_group_setting(
            pool, chat_id, welcome_media_file_id=file_id, welcome_media_type="photo"
        )
        text = update.message.caption or "Welcome {mention}! 👋"
    elif update.message.video:
        await db_groups.set_group_setting(
            pool,
            chat_id,
            welcome_media_file_id=update.message.video.file_id,
            welcome_media_type="video",
        )
        text = update.message.caption or "Welcome {mention}! 👋"
    elif update.message.animation:
        await db_groups.set_group_setting(
            pool,
            chat_id,
            welcome_media_file_id=update.message.animation.file_id,
            welcome_media_type="animation",
        )
        text = update.message.caption or "Welcome {mention}! 👋"
    elif update.message.sticker:
        await db_groups.set_group_setting(
            pool,
            chat_id,
            welcome_media_file_id=update.message.sticker.file_id,
            welcome_media_type="sticker",
        )
        text = "Welcome {mention}! 👋"
    else:
        text = update.message.text

    await db_groups.set_group_setting(pool, chat_id, welcome_message=text, onboarding_complete=True)

    await complete_onboarding(update, context)
    return ConversationHandler.END


async def complete_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE, skipped=False):
    """Complete onboarding flow"""
    chat_id = update.effective_chat.id
    pool = context.bot_data.get("db_pool")

    if pool:
        await db_groups.set_group_setting(pool, chat_id, onboarding_complete=True)

    msg = "✅ Setup complete!" if not skipped else "⏭️ Setup skipped."
    msg += "\n\nYour bot is ready to use!\n\n"
    msg += "📚 Quick commands:\n"
    msg += "• /help - Show all commands\n"
    msg += "• /settings - Configure bot\n"
    msg += "• /setup - Run setup again\n\n"
    msg += "Need help? Contact support."

    if update.callback_query:
        await update.callback_query.edit_message_text(msg)
    else:
        await update.message.reply_text(msg)

    logger.info(f"[ONBOARDING] Completed for chat {chat_id}")


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-trigger onboarding with /setup command"""
    return await start_onboarding(update, context)


# Export conversation handler
from telegram.ext import CallbackQueryHandler, CommandHandler, ConversationHandler, MessageHandler, filters

onboarding_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, start_onboarding),
    ],
    states={
        LANGUAGE: [CallbackQueryHandler(handle_language, pattern="^(lang:|skip)")],
        MODULES: [CallbackQueryHandler(handle_modules, pattern="^(modules:|skip)")],
        WELCOME: [
            CallbackQueryHandler(handle_welcome_choice, pattern="^(welcome:|skip)"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_welcome_message),
            MessageHandler(
                filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Sticker.ALL,
                handle_welcome_message,
            ),
        ],
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    name="onboarding",
    persistent=False,
)

setup_command = CommandHandler("setup", cmd_setup)
