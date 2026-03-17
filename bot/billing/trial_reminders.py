"""
bot/billing/trial_reminders.py

Handles sending trial reminder messages to bot owners.

Reminders are sent on:
  - Day 1 (on creation): Welcome message
  - Day 8 (halfway): 7 days left
  - Day 12 (3 days left): Final warning
  - Day 14 (1 day left): Last chance
  - Day 15 (on expiry): Trial ended

All reminders are sent via the primary bot to the owner's private chat.
"""

import logging
from datetime import datetime, timezone, timedelta

import asyncpg

from bot.billing.subscriptions import get_trial_days_remaining, get_active_trials
from bot.billing.billing_helpers import count_bot_properties
from config import settings

logger = logging.getLogger("trial_reminders")


async def check_and_send_reminders(db_pool: asyncpg.Pool, primary_bot):
    """
    Check all active trials and send reminders if needed.

    This should be called periodically (e.g., every 6 hours).
    """
    try:
        # Get all owners with active trials
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT owner_user_id
                FROM bots
                WHERE plan = 'trial'
                  AND trial_ends_at > NOW()
            """)

        for row in rows:
            owner_id = row["owner_user_id"]
            await _send_reminders_for_owner(db_pool, primary_bot, owner_id)

    except Exception as e:
        logger.error(f"[TRIAL_REMINDERS] Failed to check: {e}")


async def _send_reminders_for_owner(db_pool: asyncpg.Pool, primary_bot, owner_id: int):
    """Check and send reminders for a specific owner."""
    try:
        trials = await get_active_trials(db_pool, owner_id)

        for trial in trials:
            bot_id = trial["bot_id"]
            bot_username = trial["username"]
            trial_ends_at = trial["trial_ends_at"]
            days_remaining = await get_trial_days_remaining(db_pool, bot_id)

            if days_remaining is None:
                continue

            # Check if reminder was already sent
            reminder_key = f"trial_reminder_{bot_id}_{days_remaining}_days"
            if await _reminder_already_sent(db_pool, owner_id, reminder_key):
                continue

            # Count properties for context
            async with db_pool.acquire() as conn:
                token_hash = await conn.fetchval(
                    "SELECT token_hash FROM bots WHERE bot_id = $1",
                    bot_id
                )
            property_count = await count_bot_properties(db_pool, bot_id, token_hash)

            # Send appropriate reminder
            message = None
            if days_remaining == 14:
                message = _get_day_1_message(bot_username, property_count, trial_ends_at)
            elif days_remaining == 7:
                message = _get_day_8_message(bot_username, trial_ends_at)
            elif days_remaining == 3:
                message = _get_day_12_message(bot_username, trial_ends_at)
            elif days_remaining == 1:
                message = _get_day_14_message(bot_username, property_count, trial_ends_at)
            elif days_remaining == 0:
                message = _get_day_15_message(bot_username, property_count)

            if message:
                await _send_reminder(primary_bot, owner_id, message)
                await _mark_reminder_sent(db_pool, owner_id, reminder_key)
                logger.info(f"[TRIAL_REMINDERS] Sent reminder | bot={bot_id} days={days_remaining}")

    except Exception as e:
        logger.error(f"[TRIAL_REMINDERS] Failed for owner {owner_id}: {e}")


async def _send_creation_reminder(db_pool: asyncpg.Pool, primary_bot, bot_id: int, bot_username: str):
    """Send Day 1 creation reminder immediately after trial starts."""
    try:
        owner_id = await _get_bot_owner(db_pool, bot_id)
        if not owner_id:
            return

        # Count properties
        async with db_pool.acquire() as conn:
            token_hash = await conn.fetchval(
                "SELECT token_hash FROM bots WHERE bot_id = $1",
                bot_id
            )
        property_count = await count_bot_properties(db_pool, bot_id, token_hash)

        # Get trial end date
        async with db_pool.acquire() as conn:
            trial_ends_at = await conn.fetchval(
                "SELECT trial_ends_at FROM bots WHERE bot_id = $1",
                bot_id
            )

        message = _get_day_1_message(bot_username, property_count, trial_ends_at)
        await _send_reminder(primary_bot, owner_id, message)

        # Mark as sent
        reminder_key = f"trial_reminder_{bot_id}_14_days"
        await _mark_reminder_sent(db_pool, owner_id, reminder_key)

    except Exception as e:
        logger.error(f"[TRIAL_REMINDERS] Failed to send creation reminder: {e}")


def _get_day_1_message(bot_username: str, property_count: int, trial_ends_at) -> str:
    """Day 1 (creation) message."""
    ends_text = trial_ends_at.strftime("%B %d, %Y") if trial_ends_at else "15 days from now"
    return (
        f"🚀 @{bot_username} is live!\n\n"
        f"You have 15 days of Starter features free.\n"
        f"It manages {property_count} properties.\n\n"
        f"After trial: bot goes inactive unless you upgrade.\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
    )


def _get_day_8_message(bot_username: str, trial_ends_at) -> str:
    """Day 8 (halfway) message."""
    ends_text = trial_ends_at.strftime("%B %d, %Y") if trial_ends_at else "7 days"
    return (
        f"⏳ 7 days left on @{bot_username}'s trial.\n\n"
        f"Upgrade now to keep it running after {ends_text}.\n\n"
        f"Open the Mini App to upgrade your plan.\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
    )


def _get_day_12_message(bot_username: str, trial_ends_at) -> str:
    """Day 12 (3 days left) message."""
    ends_text = trial_ends_at.strftime("%B %d, %Y") if trial_ends_at else "3 days"
    return (
        f"⚠️ 3 days left for @{bot_username}.\n\n"
        f"After {ends_text} this bot will stop working completely.\n"
        f"Upgrade to keep it active.\n\n"
        f"Open the Mini App to upgrade your plan.\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
    )


def _get_day_14_message(bot_username: str, property_count: int, trial_ends_at) -> str:
    """Day 14 (1 day left) message."""
    ends_text = trial_ends_at.strftime("%B %d, %Y") if trial_ends_at else "tomorrow"
    return (
        f"🚨 FINAL WARNING: @{bot_username} stops working TOMORROW ({ends_text}).\n\n"
        f"Upgrade now or lose all automation in its {property_count} properties.\n\n"
        f"Open the Mini App to upgrade your plan.\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
    )


def _get_day_15_message(bot_username: str, property_count: int) -> str:
    """Day 15 (expiry) message."""
    return (
        f"⛔ @{bot_username} has expired and is now inactive.\n\n"
        f"It is still in {property_count} properties but doing nothing.\n"
        f"Upgrade to reactivate it.\n\n"
        f"To remove it cleanly: use /remove in any of its groups.\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
    )


async def _send_reminder(primary_bot, owner_id: int, message: str):
    """Send reminder message to owner via primary bot."""
    try:
        await primary_bot.send_message(
            chat_id=owner_id,
            text=message,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"[TRIAL_REMINDERS] Failed to send DM to {owner_id}: {e}")


async def _reminder_already_sent(db_pool: asyncpg.Pool, owner_id: int, reminder_key: str) -> bool:
    """Check if a reminder was already sent."""
    try:
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM payment_events
                WHERE owner_id = $1
                  AND event_type = 'trial_reminder'
                  AND metadata->>'reminder_key' = $2
                """,
                owner_id,
                reminder_key
            )
        return count > 0
    except Exception:
        return False


async def _mark_reminder_sent(db_pool: asyncpg.Pool, owner_id: int, reminder_key: str):
    """Mark a reminder as sent."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO payment_events (owner_id, event_type, metadata)
                VALUES ($1, 'trial_reminder', $2)
                """,
                owner_id,
                {"reminder_key": reminder_key, "sent_at": datetime.now(timezone.utc).isoformat()}
            )
    except Exception as e:
        logger.warning(f"[TRIAL_REMINDERS] Failed to mark reminder sent: {e}")


async def _get_bot_owner(db_pool: asyncpg.Pool, bot_id: int) -> int:
    """Get the owner of a bot."""
    try:
        async with db_pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT owner_user_id FROM bots WHERE bot_id = $1",
                bot_id
            )
    except Exception:
        return None
