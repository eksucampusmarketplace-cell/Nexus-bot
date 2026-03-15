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
