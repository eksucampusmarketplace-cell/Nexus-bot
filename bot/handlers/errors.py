import logging
import traceback
from telegram import Update
from telegram.ext import ContextTypes
from config import settings

logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    
    logger.error(f"Traceback:\n{tb_string}")

    if settings.OWNER_ID:
        try:
            await context.bot.send_message(
                chat_id=settings.OWNER_ID,
                text=f"An error occurred:\n<code>{tb_string[:4000]}</code>",
                parse_mode="HTML"
            )
        except Exception:
            logger.error("Failed to send error message to owner")
