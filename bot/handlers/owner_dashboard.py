"""
bot/handlers/owner_dashboard.py

Owner-only dashboard command. Only responds to OWNER_ID.
"""

import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from config import settings

logger = logging.getLogger(__name__)


async def owner_dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not settings.OWNER_ID or user.id != settings.OWNER_ID:
        return

    pool = context.bot_data.get("db_pool")
    stats = {"bots": 0, "groups": 0, "users": 0}
    if pool:
        async with pool.acquire() as conn:
            stats["bots"] = (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM bots WHERE status='active' AND is_primary=FALSE"
                )
            ) or 0
            stats["groups"] = (await conn.fetchval("SELECT COUNT(*) FROM groups")) or 0
            stats["users"] = (
                await conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM users")
            ) or 0

    msg = (
        "👑 Owner Dashboard\n\n"
        f"🤖 Active clones: {stats['bots']}\n"
        f"👥 Total groups: {stats['groups']}\n"
        f"👤 Total users: {stats['users']}\n\n"
        "Commands:\n"
        "/myclones — manage your clone bots\n"
        "/grantbonus <user_id> <amount> — grant bonus stars\n"
        "/createpromo <code> <amount> <uses> — create promo\n"
        "/promoinfo <code> — check promo\n"
        "/disablepromo <code> — disable promo\n"
        "/cloneset limit|policy|notify — update clone settings\n"
    )
    await update.message.reply_text(msg)


owner_dashboard_handler = CommandHandler("owner", owner_dashboard_command)
