"""
api/routes/billing.py

Stars economy and billing API routes.
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from config import settings
from bot.billing.stars_economy import (
    get_bonus_balance, redeem_promo_code, spend_bonus_stars,
    get_referral_link, get_referral_stats, REFERRAL_BONUS_STARS
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
    result = await spend_bonus_stars(db, owner_id, 0, req.item_type)  # Amount checked in spend function
    return result
