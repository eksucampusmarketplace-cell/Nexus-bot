import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

from db.client import db

logger = logging.getLogger(__name__)


async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track every message for daily stats - runs after all other handlers."""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    today = date.today()

    try:
        pool = context.bot_data.get("db_pool") or context.bot_data.get("db")
        if not pool:
            return

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO bot_stats_daily (chat_id, day, message_count)
                   VALUES ($1, $2, 1)
                   ON CONFLICT (chat_id, day) DO UPDATE
                   SET message_count = bot_stats_daily.message_count + 1""",
                chat_id,
                today,
            )
    except Exception as e:
        logger.debug(f"[track_message] {e}")
