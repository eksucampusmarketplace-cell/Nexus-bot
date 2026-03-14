import asyncio
import logging
from datetime import datetime

from telegram import ChatPermissions
from telegram.ext import ContextTypes

from db.client import db

log = logging.getLogger("[MOD_SCHEDULER]")


async def process_timed_actions(context: ContextTypes.DEFAULT_TYPE):
    """Find expired mutes and bans, and revert them."""
    if not db.pool:
        return

    now = datetime.utcnow()

    # 1. Expired Bans
    expired_bans = await db.fetch(
        "SELECT chat_id, user_id FROM bans WHERE is_active = TRUE AND unban_at < $1", now
    )
    for row in expired_bans:
        try:
            await context.bot.unban_chat_member(row["chat_id"], row["user_id"])
            await db.execute(
                "UPDATE bans SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
                row["chat_id"],
                row["user_id"],
            )
            log.info(f"Auto-unbanned user {row['user_id']} in chat {row['chat_id']}")
        except Exception as e:
            log.error(f"Failed auto-unban for {row['user_id']} in {row['chat_id']}: {e}")

    # 2. Expired Mutes
    expired_mutes = await db.fetch(
        "SELECT chat_id, user_id FROM mutes WHERE is_active = TRUE AND unmute_at < $1", now
    )
    for row in expired_mutes:
        try:
            await context.bot.restrict_chat_member(
                row["chat_id"],
                row["user_id"],
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            await db.execute(
                "UPDATE mutes SET is_active = FALSE WHERE chat_id = $1 AND user_id = $2",
                row["chat_id"],
                row["user_id"],
            )
            log.info(f"Auto-unmuted user {row['user_id']} in chat {row['chat_id']}")
        except Exception as e:
            log.error(f"Failed auto-unmute for {row['user_id']} in {row['chat_id']}: {e}")


async def check_lockdowns(context: ContextTypes.DEFAULT_TYPE):
    """Deactivate expired lockdowns."""
    now = datetime.utcnow()
    expired = await db.fetch(
        "SELECT chat_id FROM lockdown_state WHERE is_active = TRUE AND auto_unlock_at < $1", now
    )

    # We need the lockdown manager. In a real app we'd get it from bot_data.
    # For now, we'll do it manually here.
    for row in expired:
        chat_id = row["chat_id"]
        try:
            # Restore permissions (default)
            await context.bot.set_chat_permissions(
                chat_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_invite_users=True,
                ),
            )
            await db.execute(
                "UPDATE lockdown_state SET is_active = FALSE WHERE chat_id = $1", chat_id
            )
            await context.bot.send_message(chat_id, "🔓 *Lockdown lifted automatically*.")
        except Exception as e:
            log.error(f"Failed to lift lockdown for {chat_id}: {e}")


def setup_moderation_scheduler(application):
    """Register moderation background tasks."""
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(process_timed_actions, interval=60, first=10)
        job_queue.run_repeating(check_lockdowns, interval=60, first=20)
        log.info("Moderation scheduler tasks registered.")
