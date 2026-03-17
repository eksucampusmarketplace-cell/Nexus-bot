"""
bot/billing/subscriptions.py

Handles plan subscriptions and Telegram Stars payments.

Key functions:
  - create_subscription: Create a paid subscription
  - cancel_subscription: Cancel auto-renewal
  - handle_webhook: Process payment webhook from Telegram
  - start_trial: Start 15-day trial for a clone bot
  - check_trial_expiration: Check and expire trials that ended
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

import asyncpg

from bot.billing.plans import PLANS, get_plan
from bot.billing.billing_helpers import get_bot_plan

logger = logging.getLogger("subscriptions")

TRIAL_DURATION_DAYS = 15


async def create_subscription(
    db_pool: asyncpg.Pool,
    owner_id: int,
    plan_key: str,
    charge_id: str,
    stars_paid: int
) -> Dict:
    """
    Create a new subscription for an owner.

    Args:
        db_pool: Database connection pool
        owner_id: Telegram user ID
        plan_key: Plan identifier ('basic', 'starter', 'pro', 'unlimited')
        charge_id: Telegram payment charge ID
        stars_paid: Amount paid in Stars

    Returns:
        dict with {ok, plan, expires_at, error}
    """
    plan = get_plan(plan_key)
    if not plan:
        return {"ok": False, "error": "Invalid plan"}

    # Calculate expiry (1 month from now)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    try:
        async with db_pool.acquire() as conn:
            # Insert subscription
            await conn.execute(
                """
                INSERT INTO billing_subscriptions
                (owner_id, plan, telegram_charge_id, stars_paid, plan_expires_at, auto_renew)
                VALUES ($1, $2, $3, $4, $5, TRUE)
                ON CONFLICT (telegram_charge_id) DO NOTHING
                """,
                owner_id,
                plan_key,
                charge_id,
                stars_paid,
                expires_at
            )

            # Record payment event
            await conn.execute(
                """
                INSERT INTO payment_events
                (owner_id, event_type, item_type, stars_paid, metadata)
                VALUES ($1, 'subscription', $2, $3, $4)
                """,
                owner_id,
                plan_key,
                stars_paid,
                {"plan_name": plan["name"], "charge_id": charge_id}
            )

        logger.info(
            f"[SUBSCRIPTION] Created | owner={owner_id} plan={plan_key} "
            f"stars={stars_paid} expires={expires_at}"
        )

        return {
            "ok": True,
            "plan": plan_key,
            "expires_at": expires_at.isoformat()
        }

    except Exception as e:
        logger.error(f"[SUBSCRIPTION] Failed to create: {e}")
        return {"ok": False, "error": str(e)}


async def cancel_subscription(db_pool: asyncpg.Pool, owner_id: int) -> Dict:
    """
    Cancel auto-renewal for owner's subscription.

    The plan remains active until plan_expires_at, then reverts to free.
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE billing_subscriptions
                SET auto_renew = FALSE
                WHERE owner_id = $1 AND plan_expires_at > NOW()
                """,
                owner_id
            )

        logger.info(f"[SUBSCRIPTION] Cancelled | owner={owner_id}")
        return {"ok": True}

    except Exception as e:
        logger.error(f"[SUBSCRIPTION] Failed to cancel: {e}")
        return {"ok": False, "error": str(e)}


async def handle_webhook(
    db_pool: asyncpg.Pool,
    webhook_data: dict
) -> Dict:
    """
    Process payment webhook from Telegram Stars API.

    Expected webhook_data structure:
    {
        "id": "charge_id",
        "status": "paid" | "failed" | "refunded",
        "amount": 100,
        "user_id": 123456789,
        "metadata": {"plan": "basic"}
    }

    Returns:
        dict with {ok, message}
    """
    charge_id = webhook_data.get("id")
    status = webhook_data.get("status")
    amount = webhook_data.get("amount", 0)
    user_id = webhook_data.get("user_id")
    metadata = webhook_data.get("metadata", {})

    if status != "paid":
        logger.info(f"[WEBHOOK] Skipping non-paid charge: {charge_id} status={status}")
        return {"ok": True, "message": "Ignored non-paid charge"}

    plan_key = metadata.get("plan")
    if not plan_key:
        logger.error(f"[WEBHOOK] No plan in metadata for charge: {charge_id}")
        return {"ok": False, "message": "Missing plan in metadata"}

    result = await create_subscription(
        db_pool,
        owner_id=user_id,
        plan_key=plan_key,
        charge_id=charge_id,
        stars_paid=amount
    )

    return result


async def start_trial(db_pool: asyncpg.Pool, bot_id: int) -> Dict:
    """
    Start a 15-day trial for a clone bot.

    Args:
        db_pool: Database connection pool
        bot_id: Telegram bot ID

    Returns:
        dict with {ok, trial_ends_at, error}
    """
    trial_ends_at = datetime.now(timezone.utc) + timedelta(days=TRIAL_DURATION_DAYS)

    try:
        async with db_pool.acquire() as conn:
            # Update bot to trial status
            await conn.execute(
                """
                UPDATE bots
                SET plan = 'trial',
                    trial_ends_at = $1,
                    trial_used = TRUE,
                    updated_at = NOW()
                WHERE bot_id = $2
                """,
                trial_ends_at,
                bot_id
            )

        logger.info(
            f"[TRIAL] Started | bot={bot_id} ends={trial_ends_at}"
        )

        return {
            "ok": True,
            "trial_ends_at": trial_ends_at.isoformat()
        }

    except Exception as e:
        logger.error(f"[TRIAL] Failed to start: {e}")
        return {"ok": False, "error": str(e)}


async def check_trial_expiration(db_pool: asyncpg.Pool) -> int:
    """
    Check all trial bots and expire those whose trial period has ended.

    This should be called periodically (e.g., every hour via a scheduled task).

    Returns:
        Number of trials expired
    """
    now = datetime.now(timezone.utc)

    try:
        async with db_pool.acquire() as conn:
            # Expire all trial bots with trial_ends_at < now
            result = await conn.execute(
                """
                UPDATE bots
                SET plan = 'trial_expired',
                    updated_at = NOW()
                WHERE plan = 'trial'
                  AND trial_ends_at < $1
                """,
                now
            )

            # Count affected rows
            count = int(result.split()[-1]) if result else 0

        if count > 0:
            logger.info(f"[TRIAL] Expired {count} trials")

        return count

    except Exception as e:
        logger.error(f"[TRIAL] Failed to check expiration: {e}")
        return 0


async def get_trial_days_remaining(db_pool: asyncpg.Pool, bot_id: int) -> Optional[int]:
    """
    Get the number of days remaining in a trial.

    Returns:
        Days remaining, or None if bot is not on trial
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT trial_ends_at
                FROM bots
                WHERE bot_id = $1 AND plan = 'trial'
                """,
                bot_id
            )

        if not row or not row["trial_ends_at"]:
            return None

        remaining = row["trial_ends_at"] - datetime.now(timezone.utc)
        days = max(0, remaining.days)

        return days

    except Exception as e:
        logger.error(f"[TRIAL] Failed to get days remaining: {e}")
        return None


async def get_active_trials(db_pool: asyncpg.Pool, owner_id: int) -> list:
    """
    Get all active trial bots for an owner.

    Returns:
        List of bot dicts with trial info
    """
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    bot_id,
                    username,
                    display_name,
                    trial_ends_at,
                    plan
                FROM bots
                WHERE owner_user_id = $1
                  AND plan = 'trial'
                  AND trial_ends_at > NOW()
                ORDER BY trial_ends_at ASC
                """,
                owner_id
            )

        return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"[TRIAL] Failed to get active trials: {e}")
        return []
