"""
bot/handlers/lang_setting.py

Language settings handler - v21
Per-user /lang preference, per-group /grouplang default.
"""

import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from bot.utils.localization import (
    SUPPORTED_LANGUAGES, 
    DEFAULT_LANG, 
    set_user_language,
    get_user_language,
    get_user_lang,
    get_locale
)
from bot.utils.permissions import is_admin
from bot.utils.lang_detect import set_user_lang_manual

log = logging.getLogger("lang_setting")


def build_language_keyboard(prefix: str, current_lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    """Build language selection keyboard."""
    buttons = []
    row = []
    
    for code, name in SUPPORTED_LANGUAGES.items():
        marker = "✅ " if code == current_lang else ""
        row.append(InlineKeyboardButton(
            f"{marker}{name}",
            callback_data=f"{prefix}:{code}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    return InlineKeyboardMarkup(buttons)


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /lang - Set your personal language preference.
    Works in private chat.
    """
    user = update.effective_user
    chat = update.effective_chat
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    # Use user's language for DM, or group language if in group
    lang = await get_user_lang(db, user.id, chat_id=chat.id if chat.type != "private" else None)
    locale = get_locale(lang)

    if chat.type != "private":
        # In groups, just show current and redirect to PM
        current_lang = await get_user_language(db, user.id)
        lang_name = SUPPORTED_LANGUAGES.get(current_lang, current_lang)
        
        # We need a new key for this or use a generic one. 
        # For now let's just use the current logic but with resolved locale if we had keys.
        # Since I don't want to add too many keys, I'll use what I have.
        await update.message.reply_text(
            f"🌍 <b>Your Language</b>: {lang_name}\n\n"
            f"To change your language, message me in private:\n"
            f"<code>/lang</code>",
            parse_mode="HTML"
        )
        return
    
    current_lang = await get_user_language(db, user.id)
    
    await update.message.reply_text(
        f"🌍 <b>Select Your Language</b>\n\n"
        f"Current: <b>{SUPPORTED_LANGUAGES.get(current_lang, current_lang)}</b>\n\n"
        f"Choose your preferred language:",
        reply_markup=build_language_keyboard("setlang", current_lang),
        parse_mode="HTML"
    )


async def cmd_grouplang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /grouplang - Set the default language for this group (admin only).
    """
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Use this command in a group.")
        return
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    # Get current group language
    current_lang = DEFAULT_LANG
    if db:
        try:
            import json
            async with db.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT settings FROM groups WHERE chat_id = $1",
                    chat.id
                )
                if row and row["settings"]:
                    settings = row["settings"]
                    if isinstance(settings, str):
                        settings = json.loads(settings)
                    current_lang = settings.get("default_language", DEFAULT_LANG)
        except Exception as e:
            log.debug(f"Failed to get group language: {e}")
    
    await update.message.reply_text(
        f"🌍 <b>Group Language</b>\n\n"
        f"Current: <b>{SUPPORTED_LANGUAGES.get(current_lang, current_lang)}</b>\n\n"
        f"Select the default language for this group:",
        reply_markup=build_language_keyboard("setgrouplang", current_lang),
        parse_mode="HTML"
    )


async def handle_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    parts = data.split(":")
    if len(parts) != 2:
        return
    
    action, lang_code = parts
    
    if lang_code not in SUPPORTED_LANGUAGES:
        await query.edit_message_text("❌ Invalid language selected.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    if action == "setlang":
        # Set user language manually - this sets auto_detected=FALSE
        # so it will NEVER be overridden by auto-detection
        if db:
            success = await set_user_lang_manual(db, user.id, lang_code)
            if not success:
                await query.edit_message_text("❌ Failed to set language.")
                return
        
        await query.edit_message_text(
            f"✅ <b>Language Updated</b>\n\n"
            f"Your language is now set to: <b>{SUPPORTED_LANGUAGES[lang_code]}</b>\n\n"
            f"This will be used for all bot messages to you.\n"
            f"<i>Your preference is saved and won't change automatically.</i>",
            parse_mode="HTML"
        )
        log.info(f"[LANG] User {user.id} set manual language to {lang_code} (auto_detected=FALSE)")
        
    elif action == "setgrouplang":
        # Set group language
        chat = query.message.chat
        
        if db:
            try:
                import json
                async with db.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT settings FROM groups WHERE chat_id = $1",
                        chat.id
                    )
                    
                    settings = row["settings"] or {} if row else {}
                    if isinstance(settings, str):
                        settings = json.loads(settings)
                    
                    settings["default_language"] = lang_code
                    
                    await conn.execute(
                        "UPDATE groups SET settings = $1 WHERE chat_id = $2",
                        settings, chat.id
                    )
            except Exception as e:
                log.error(f"[LANG] Failed to set group language: {e}")
                await query.edit_message_text("❌ Failed to set group language.")
                return
        
        await query.edit_message_text(
            f"✅ <b>Group Language Updated</b>\n\n"
            f"Default language for this group: <b>{SUPPORTED_LANGUAGES[lang_code]}</b>\n\n"
            f"This will be used for automated messages in this group.",
            parse_mode="HTML"
        )
        log.info(f"[LANG] Group {chat.id} set language to {lang_code}")


async def cmd_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /languages - List all available languages.
    """
    lines = ["🌍 <b>Supported Languages</b>\n"]
    
    for code, name in SUPPORTED_LANGUAGES.items():
        lines.append(f"• <code>{code}</code> — {name}")
    
    lines.append("\nUse <code>/lang</code> to set your language.")
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML"
    )


# Handler registration
lang_setting_handlers = [
    CommandHandler("lang", cmd_lang),
    CommandHandler("grouplang", cmd_grouplang),
    CommandHandler("languages", cmd_languages),
    CallbackQueryHandler(handle_lang_callback, pattern=r"^set(lang|grouplang):[a-z]{2}$"),
]
