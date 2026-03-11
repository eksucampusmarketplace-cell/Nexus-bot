import logging
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.handlers.commands import start, help_handler, panel, warn_handler, ban_handler, mute_handler, purge_handler, id_handler, rules_handler
from bot.handlers.automod import message_handler, member_join_handler
from bot.handlers.captcha import captcha_callback
from bot.handlers.errors import error_handler

logger = logging.getLogger(__name__)

def create_bot_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("warn", warn_handler))
    app.add_handler(CommandHandler("ban", ban_handler))
    app.add_handler(CommandHandler("mute", mute_handler))
    app.add_handler(CommandHandler("purge", purge_handler))
    app.add_handler(CommandHandler("id", id_handler))
    app.add_handler(CommandHandler("rules", rules_handler))
    
    app.add_handler(CallbackQueryHandler(captcha_callback, pattern="^captcha_verify_"))
    
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, member_join_handler))
    app.add_handler(MessageHandler(filters.TEXT, message_handler))
    
    app.add_error_handler(error_handler)
    
    return app
