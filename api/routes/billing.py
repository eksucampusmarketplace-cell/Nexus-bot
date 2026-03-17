"""
api/routes/billing.py

Stars economy and billing API routes.
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from config import settings
from bot.billing.stars_economy import (
    get_bonus_balance,
    grant_bonus_stars,
    redeem_promo_code,
    spend_bonus_stars,
    get_referral_link,
    get_referral_stats,
    REFERRAL_BONUS_STARS,
)
from bot.billing.plans import get_all_plans, get_plans_for_display, get_plan
from bot.billing.subscriptions import (
    create_subscription,
    cancel_subscription,
    get_trial_days_remaining,
    get_active_trials,
)
from bot.billing.billing_helpers import (
    get_owner_plan,
    can_owner_add_clone_bot,
    check_owner_total_properties,
)

log = logging.getLogger("billing_api")
router = APIRouter()


class RedeemPromoRequest(BaseModel):
    code: str


class SpendBonusRequest(BaseModel):
    item_type: str


@router.get("/api/billing/bonus-balance")
async def get_bonus_balance_endpoint(request: Request):
    """Get bonus Stars balance for owner."""
    owner_id = request.state.user_id
    db = request.app.state.db
    balance = await get_bonus_balance(db, owner_id)
    return {"balance": balance}


@router.get("/api/billing/referral-stats")
async def get_referral_stats_endpoint(request: Request):
    """Get referral stats for owner."""
    owner_id = request.state.user_id
    db = request.app.state.db
    me = await request.app.state.bot.get_me()
    stats = await get_referral_stats(db, owner_id)
    link = await get_referral_link(me.username, owner_id)
    return {**stats, "link": link}


@router.post("/api/billing/redeem-promo")
async def redeem_promo_endpoint(request: Request, req: RedeemPromoRequest):
    """Redeem a promo code."""
    owner_id = request.state.user_id
    db = request.app.state.db
    bot = request.app.state.bot
    result = await redeem_promo_code(db, bot, owner_id, req.code)
    return result


@router.post("/api/billing/spend-bonus")
async def spend_bonus_endpoint(request: Request, req: SpendBonusRequest):
    """Spend bonus Stars to unlock a feature."""
    owner_id = request.state.user_id
    db = request.app.state.db
    result = await spend_bonus_stars(
        db, owner_id, 0, req.item_type
    )  # Amount checked in spend function
    return result


class GrantBonusRequest(BaseModel):
    user_id: int
    amount: int
    reason: str = "Owner grant"


class CreatePromoRequest(BaseModel):
    code: str
    amount: int
    max_uses: int = 10


@router.post("/api/billing/grant-bonus")
async def grant_bonus_endpoint(request: Request, req: GrantBonusRequest):
    """Grant bonus Stars to a user. Owner only."""
    caller_id = request.state.user_id
    if caller_id != settings.OWNER_ID:
        raise HTTPException(status_code=403, detail="Owner only")
    db_pool = request.app.state.db
    new_balance = await grant_bonus_stars(db_pool, req.user_id, req.amount, req.reason, granted_by=caller_id)
    return {"ok": True, "user_id": req.user_id, "amount": req.amount, "new_balance": new_balance}


@router.post("/api/billing/create-promo")
async def create_promo_endpoint(request: Request, req: CreatePromoRequest):
    """Create a new promo code. Owner only."""
    caller_id = request.state.user_id
    if caller_id != settings.OWNER_ID:
        raise HTTPException(status_code=403, detail="Owner only")
    db_pool = request.app.state.db
    code = req.code.strip().upper()
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO promo_codes
                   (code, reward_type, reward_value, max_uses, current_uses, is_active)
                   VALUES ($1, 'bonus_stars', $2, $3, 0, TRUE)
                   ON CONFLICT (code) DO UPDATE
                     SET reward_value = EXCLUDED.reward_value,
                         max_uses = EXCLUDED.max_uses,
                         is_active = TRUE
                   RETURNING id, code""",
                code, req.amount, req.max_uses,
            )
        return {"ok": True, "id": row["id"], "code": row["code"], "amount": req.amount, "max_uses": req.max_uses}
    except Exception as e:
        log.error(f"[Billing API] create_promo error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── PLAN ENDPOINTS ────────────────────────────────────────────────────────────


@router.get("/api/billing/plans")
async def get_plans_endpoint(request: Request):
    """Get all available plans for display."""
    plans = get_plans_for_display()
    return {"plans": plans}


@router.get("/api/billing/owner-info")
async def get_owner_info_endpoint(request: Request):
    """Get owner's current plan and usage information."""
    owner_id = request.state.user_id
    db_pool = request.app.state.db

    # Get owner's plan
    plan_key = await get_owner_plan(db_pool, owner_id)
    plan_config = get_plan(plan_key)

    # Check if can add more clones
    can_add_clone, clone_error = await can_owner_add_clone_bot(db_pool, owner_id)

    # Check property usage
    within_limit, prop_count, prop_error = await check_owner_total_properties(db_pool, owner_id)

    # Count current bots
    from db.ops.bots import get_bots_by_owner
    bots = await get_bots_by_owner(db_pool, owner_id)
    clone_count = sum(1 for b in bots if not b.get("is_primary", False))

    # Get active trials
    trials = await get_active_trials(db_pool, owner_id)

    return {
        "plan": plan_key,
        "plan_name": plan_config.get("name", "Free"),
        "clone_bots_allowed": plan_config.get("clone_bots", 1),
        "clone_bots_used": clone_count,
        "can_add_clone": can_add_clone,
        "clone_error": clone_error if not can_add_clone else None,
        "total_properties_allowed": plan_config.get("total_properties", 10),
        "total_properties_used": prop_count,
        "properties_within_limit": within_limit,
        "property_error": prop_error if not within_limit else None,
        "active_trials": trials
    }


# ── SUBSCRIPTION ENDPOINTS ───────────────────────────────────────────────────


class SubscribeRequest(BaseModel):
    plan: str  # 'basic', 'starter', 'pro', 'unlimited'


@router.post("/api/billing/subscribe")
async def subscribe_endpoint(request: Request, req: SubscribeRequest):
    """
    Subscribe to a paid plan.

    This endpoint creates a subscription record and returns a payment link.
    The actual payment is processed via Telegram Stars payment API.
    """
    owner_id = request.state.user_id
    db_pool = request.app.state.db
    bot = request.app.state.bot

    # Validate plan
    plan = get_plan(req.plan)
    if not plan or req.plan in ("free", "trial", "primary", "trial_expired"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    # Check if already on this plan
    current_plan = await get_owner_plan(db_pool, owner_id)
    if current_plan == req.plan:
        raise HTTPException(status_code=400, detail="You already have this plan")

    # In a real implementation, you would generate a Telegram Stars payment link here
    # For now, return the plan info
    return {
        "ok": True,
        "plan": req.plan,
        "plan_name": plan["name"],
        "price_stars": plan["price_stars"],
        "price_display": plan["price_display"],
        "message": "Payment integration coming soon"
    }


@router.post("/api/billing/cancel")
async def cancel_subscription_endpoint(request: Request):
    """Cancel auto-renewal of current subscription."""
    owner_id = request.state.user_id
    db_pool = request.app.state.db

    result = await cancel_subscription(db_pool, owner_id)
    return result


# ── TRIAL ENDPOINTS ──────────────────────────────────────────────────────────


@router.get("/api/billing/trials")
async def get_trials_endpoint(request: Request):
    """Get all active trials for the owner."""
    owner_id = request.state.user_id
    db_pool = request.app.state.db

    trials = await get_active_trials(db_pool, owner_id)
    return {"trials": trials}


@router.get("/api/billing/trial-days")
async def get_trial_days_endpoint(request: Request, bot_id: int):
    """Get remaining days for a trial bot."""
    owner_id = request.state.user_id
    db_pool = request.app.state.db

    # Verify ownership
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT owner_user_id FROM bots WHERE bot_id = $1",
            bot_id
        )

    if not row or row["owner_user_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Not your bot")

    days = await get_trial_days_remaining(db_pool, bot_id)
    return {"bot_id": bot_id, "days_remaining": days}
