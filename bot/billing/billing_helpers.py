"""
bot/billing/billing_helpers.py

Helper functions for plan checking, trial enforcement, and limit validation.
These functions are used throughout the bot to enforce plan limits.

Key functions:
  - get_bot_plan: Get the current plan for a bot
  - is_trial_expired: Check if a trial bot has expired
  - check_property_limit: Check if bot can add another group/channel
  - count_bot_properties: Count groups+channels for a bot
  - enforce_trial_limits: Return early if bot is trial_expired
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import asyncpg

from bot.billing.plans import PLANS, get_plan, get_clone_bot_limit, get_primary_bot_limit
from db.client import db

logger = logging.getLogger("billing_helpers")


# ── PLAN LOOKUP ────────────────────────────────────────────────────────────────

async def get_bot_plan(db_pool: asyncpg.Pool, bot_id: int) -> str:
    """
    Get the current plan for a bot.

    Returns one of:
      - 'primary': Primary bot (follows owner's plan)
      - 'free': Free tier
      - 'trial': Active trial
      - 'trial_expired': Trial ended
      - 'basic', 'starter', 'pro', 'unlimited': Paid plans
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT plan, trial_ends_at, is_primary FROM bots WHERE bot_id = $1",
            bot_id
        )

    if not row:
        logger.warning(f"[BILLING] Bot not found: {bot_id}")
        return "free"

    plan = row["plan"]
    is_primary = row["is_primary"]

    # Check trial expiration
    if plan == "trial":
        trial_ends_at = row["trial_ends_at"]
        if trial_ends_at and trial_ends_at.replace(tzinfo=None) < datetime.utcnow():
            # Trial expired - update DB and return trial_expired
            await conn.execute(
                "UPDATE bots SET plan = 'trial_expired' WHERE bot_id = $1",
                bot_id
            )
            return "trial_expired"

    # Primary bot's plan is determined by owner's subscription
    if is_primary:
        async with db_pool.acquire() as conn:
            owner_row = await conn.fetchrow("""
                SELECT plan, plan_expires_at
                FROM billing_subscriptions
                WHERE owner_id = (SELECT owner_user_id FROM bots WHERE bot_id = $1)
                ORDER BY created_at DESC
                LIMIT 1
            """, bot_id)

        if owner_row:
            owner_plan = owner_row["plan"]
            # Check if subscription expired
            if owner_row["plan_expires_at"] and owner_row["plan_expires_at"].replace(tzinfo=None) < datetime.utcnow():
                owner_plan = "free"
            return owner_plan if owner_plan in PLANS else "free"

        return "free"

    return plan if plan in PLANS else "free"


async def is_trial_expired(db_pool: asyncpg.Pool, bot_id: int) -> bool:
    """Check if a trial bot has expired."""
    plan = await get_bot_plan(db_pool, bot_id)
    return plan == "trial_expired"


# ── PROPERTY LIMITS ────────────────────────────────────────────────────────────

async def count_bot_properties(db_pool: asyncpg.Pool, bot_id: int, token_hash: str) -> int:
    """
    Count total properties (groups + channels) for a bot.
    Properties are counted from the groups table using bot_token_hash.
    """
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM groups WHERE bot_token_hash = $1",
            token_hash
        )
    return count


async def get_bot_property_limit(db_pool: asyncpg.Pool, bot_id: int) -> int:
    """
    Get the maximum number of properties allowed for a bot.

    For clone bots: limited by plan's properties_per_clone (1-500)
    For primary bot: limited by owner's plan's total_properties (0 = unlimited)
    """
    plan = await get_bot_plan(db_pool, bot_id)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_primary FROM bots WHERE bot_id = $1", bot_id)
        is_primary = row["is_primary"] if row else False

    if is_primary:
        return get_primary_bot_limit(plan)
    else:
        return get_clone_bot_limit(plan)


async def check_property_limit(
    db_pool: asyncpg.Pool,
    bot_id: int,
    token_hash: str,
    adding: int = 1
) -> Tuple[bool, str]:
    """
    Check if bot can add more properties (groups/channels).

    Args:
        db_pool: Database connection pool
        bot_id: Bot ID
        token_hash: Bot token hash for counting properties
        adding: Number of properties being added (default 1)

    Returns:
        (can_add: bool, error_message: str)
    """
    # Check if bot is trial expired
    plan = await get_bot_plan(db_pool, bot_id)
    if plan == "trial_expired":
        return False, "This bot's trial has expired. Upgrade to add more groups."

    # Get limit
    limit = await get_bot_property_limit(db_pool, bot_id)

    # Primary bot with unlimited (0)
    if limit == 0:
        return True, ""

    # Count current properties
    current = await count_bot_properties(db_pool, bot_id, token_hash)

    # Check if adding would exceed limit
    if current + adding > limit:
        return False, f"This bot has reached its limit of {limit} properties. Upgrade your plan to add more."

    return True, ""


# ── TRIAL ENFORCEMENT ─────────────────────────────────────────────────────────

def should_ignore_message(bot_plan: str, is_private_chat_with_owner: bool = False) -> bool:
    """
    Determine if a message should be ignored based on bot's plan.

    trial_expired bots ignore ALL messages except /start and /help
    in private chat with the owner.

    Args:
        bot_plan: The bot's plan (from get_bot_plan)
        is_private_chat_with_owner: True if this is a private chat with the bot owner

    Returns:
        True if message should be ignored, False otherwise
    """
    if bot_plan != "trial_expired":
        return False

    # Allow /start and /help in private chat with owner
    if is_private_chat_with_owner:
        return False

    # Ignore everything else
    return True


async def enforce_trial_limits(db_pool: asyncpg.Pool, bot_id: int, context) -> bool:
    """
    Check if bot should skip processing due to trial expiration.

    Call this at the TOP of every message handler.

    Returns:
        True if processing should continue, False if should ignore

    Usage in handlers:
        if not await enforce_trial_limits(db_pool, bot_id, context):
            return
    """
    plan = await get_bot_plan(db_pool, bot_id)

    # Check if should ignore
    if plan == "trial_expired":
        # Check if this is private chat with owner
        is_private = context.chat and context.chat.type == "private"

        if is_private:
            # Check if this is the owner
            async with db_pool.acquire() as conn:
                owner_id = await conn.fetchval(
                    "SELECT owner_user_id FROM bots WHERE bot_id = $1",
                    bot_id
                )

            if context.effective_user_id == owner_id:
                # Allow /start and /help commands only
                message_text = context.message and context.message.text
                if message_text and message_text in ("/start", "/help"):
                    return True

        # Ignore all other messages
        return False

    return True


# ── OWNER PLAN CHECKS ─────────────────────────────────────────────────────────

async def get_owner_plan(db_pool: asyncpg.Pool, owner_id: int) -> str:
    """
    Get the owner's current plan.

    Returns the plan key (free, basic, starter, pro, unlimited).
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT plan, plan_expires_at
            FROM billing_subscriptions
            WHERE owner_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """, owner_id)

    if not row:
        return "free"

    plan = row["plan"]

    # Check if expired
    if row["plan_expires_at"] and row["plan_expires_at"].replace(tzinfo=None) < datetime.utcnow():
        return "free"

    return plan if plan in PLANS else "free"


async def can_owner_add_clone_bot(db_pool: asyncpg.Pool, owner_id: int) -> Tuple[bool, str]:
    """
    Check if owner can add another clone bot based on their plan.

    Returns (can_add, error_message).
    """
    from db.ops.bots import get_bots_by_owner

    owner_plan = await get_owner_plan(db_pool, owner_id)
    plan_config = get_plan(owner_plan)

    # Count current clone bots
    bots = await get_bots_by_owner(db_pool, owner_id)
    clone_count = sum(1 for b in bots if not b.get("is_primary", False))

    max_clones = plan_config["clone_bots"]

    if clone_count >= max_clones:
        return False, f"You've reached your plan limit of {max_clones} clone bots. Upgrade to add more."

    return True, ""


async def check_owner_total_properties(db_pool: asyncpg.Pool, owner_id: int) -> Tuple[bool, int, str]:
    """
    Check if owner has reached their total properties limit across all bots.

    Returns:
        (within_limit, current_count, error_message)
    """
    owner_plan = await get_owner_plan(db_pool, owner_id)
    plan_config = get_plan(owner_plan)

    limit = plan_config["total_properties"]

    # Unlimited for Unlimited plan (total_properties = 0)
    if limit == 0:
        return True, 0, ""

    # Count total properties across all owner's bots
    async with db_pool.acquire() as conn:
        bot_ids = await conn.fetch(
            "SELECT bot_id, token_hash FROM bots WHERE owner_user_id = $1",
            owner_id
        )

    total_count = 0
    for bot in bot_ids:
        count = await count_bot_properties(db_pool, bot["bot_id"], bot["token_hash"])
        total_count += count

    if total_count >= limit:
        return False, total_count, f"You've reached your plan limit of {limit} total properties across all bots."

    return True, total_count, ""
