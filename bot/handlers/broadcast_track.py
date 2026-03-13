from telegram import Update
from telegram.ext import ContextTypes
from db.ops.broadcast import upsert_pm

async def track_pm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple handler to record PM interactions."""
    if not update.effective_chat or update.effective_chat.type != "private":
        return
    
    if not update.effective_user or update.effective_user.is_bot:
        return

    db_pool = context.bot_data.get("db_pool")
    if not db_pool:
        return

    await upsert_pm(
        db_pool,
        context.bot.id,
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.first_name
    )
