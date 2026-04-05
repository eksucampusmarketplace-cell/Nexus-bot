"""
bot/billing/plans.py

Defines all plan tiers for Nexus Bot billing system.

Plan structure:
  - price_stars: Cost in Telegram Stars per month
  - clone_bots: Number of clone bots allowed
  - properties_per_clone: Max groups+channels per clone bot
  - total_properties: Total groups+channels across ALL bots (0 = unlimited for primary only)
  - features: List of feature descriptions

Hard rules:
  1. Clone bots NEVER get unlimited properties (min 1, max 500)
  2. Primary bot follows total_properties from owner's plan
  3. total_properties=0 means unlimited for PRIMARY BOT only
  4. Properties = groups + channels combined
"""

from typing import Dict, List

PLANS: Dict[str, dict] = {
    "free": {
        "name": "Free",
        "price_stars": 0,
        "price_display": "Free forever",
        "clone_bots": 1,
        "properties_per_clone": 5,
        "total_properties": 10,
        "features": [
            "Basic moderation (warn/mute/kick/ban)",
            "Keyword filters & blacklist",
            "Welcome & goodbye messages",
            "Basic automod (flood/spam/links)",
            "5 properties total"
        ]
    },

    "basic": {
        "name": "Basic",
        "price_stars": 300,
        "price_display": "300 ⭐ / month",
        "clone_bots": 2,
        "properties_per_clone": 15,
        "total_properties": 25,
        "features": [
            "Everything in Free",
            "2 clone bots",
            "25 properties total",
            "Anti-raid protection",
            "Log channel",
            "Custom messages",
            "Join password gate"
        ]
    },

    "starter": {
        "name": "Starter",
        "price_stars": 700,
        "price_display": "700 ⭐ / month",
        "clone_bots": 5,
        "properties_per_clone": 30,
        "total_properties": 75,
        "features": [
            "Everything in Basic",
            "5 clone bots",
            "75 properties total",
            "Analytics dashboard",
            "Webhooks",
            "Advanced automod (regex/captcha)",
            "Federation support",
            "Scheduled broadcasts"
        ]
    },

    "pro": {
        "name": "Pro",
        "price_stars": 2000,
        "price_display": "2,000 ⭐ / month",
        "clone_bots": 20,
        "properties_per_clone": 100,
        "total_properties": 500,
        "features": [
            "Everything in Starter",
            "20 clone bots",
            "500 properties total",
            "Priority support",
            "Custom bot persona",
            "ML spam classifier",
            "Community voting",
            "Full engagement system (XP/badges)"
        ]
    },

    "unlimited": {
        "name": "Unlimited",
        "price_stars": 8000,
        "price_display": "8,000 ⭐ / month",
        "clone_bots": 9999,
        "properties_per_clone": 500,
        "total_properties": 0,
        "features": [
            "Everything in Pro",
            "Unlimited clone bots",
            "Unlimited properties on primary bot",
            "Clone bots max 500 properties each",
            "White-label support",
            "All future features"
        ]
    },

    "trial": {
        "name": "Trial",
        "price_stars": 0,
        "price_display": "Free trial",
        "clone_bots": 5,
        "properties_per_clone": 30,
        "total_properties": 75,
        "features": [
            "Starter plan features for 15 days",
            "5 clone bots",
            "75 properties total",
            "Full feature access during trial"
        ]
    },

    "primary": {
        "name": "Primary",
        "price_stars": 0,
        "price_display": "Included",
        "clone_bots": 0,
        "properties_per_clone": 0,
        "total_properties": 0,
        "features": [
            "Primary bot follows owner's plan",
            "Unlimited properties if owner has Unlimited plan",
            "Otherwise follows owner's total_properties limit"
        ]
    },

    "trial_expired": {
        "name": "Trial Expired",
        "price_stars": 0,
        "price_display": "Inactive",
        "clone_bots": 0,
        "properties_per_clone": 0,
        "total_properties": 0,
        "features": [
            "Bot is inactive",
            "No functions work",
            "Upgrade to reactivate"
        ]
    }
}


def get_plan(plan_key: str) -> dict:
    """Get plan configuration by key. Returns None if not found."""
    return PLANS.get(plan_key)


def get_all_plans() -> Dict[str, dict]:
    """Get all plan configurations."""
    return PLANS.copy()


def get_plans_for_display() -> List[dict]:
    """
    Get plans for display in upgrade modal.
    Excludes 'primary', 'trial', 'trial_expired' as these are internal.
    """
    display_plans = []
    for key, plan in PLANS.items():
        if key not in ("primary", "trial", "trial_expired"):
            display_plans.append({
                "key": key,
                **plan
            })
    return display_plans


async def can_add_clone_bot(db_pool, owner_id: int) -> tuple[bool, str]:
    """
    Check if owner can add another clone bot based on their plan.

    Returns (can_add, error_message)
    """
    from datetime import datetime, timezone
    from db.ops.bots import get_bots_by_owner

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT plan, plan_expires_at
            FROM billing_subscriptions
            WHERE owner_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """, owner_id)

    if not row:
        plan_config = PLANS["free"]
    else:
        plan_key = row["plan"]
        plan_config = PLANS.get(plan_key, PLANS["free"])

        if row["plan_expires_at"]:
            exp = row["plan_expires_at"]
            exp_dt = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
            if exp_dt < datetime.now(timezone.utc):
                plan_config = PLANS["free"]

    bots = await get_bots_by_owner(db_pool, owner_id)
    clone_count = sum(1 for b in bots if not b.get("is_primary", False))

    max_clones = plan_config["clone_bots"]

    if clone_count >= max_clones:
        return False, f"You've reached your plan limit of {max_clones} clone bots. Upgrade to add more."

    return True, ""


def get_clone_bot_limit(bot_plan: str) -> int:
    """
    Get the group/channel limit for a clone bot based on its plan.
    Enforces hard rules: clone bots NEVER get unlimited (0).
    """
    plan = PLANS.get(bot_plan, PLANS["free"])

    # Hard rule: Clone bots never get unlimited
    limit = plan["properties_per_clone"]
    if limit == 0:
        # Even Unlimited plan caps clone bots at 500
        limit = 500

    # Ensure minimum 1 and maximum 500
    return max(1, min(limit, 500))


def get_primary_bot_limit(owner_plan: str) -> int:
    """
    Get the group/channel limit for the primary bot based on owner's plan.
    Returns 0 for unlimited (allowed for primary only).
    """
    plan = PLANS.get(owner_plan, PLANS["free"])
    return plan["total_properties"]
