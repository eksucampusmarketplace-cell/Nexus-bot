"""
api/routes/trust.py

API endpoints for Global Trust Score system.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from db.client import db

router = APIRouter(prefix="/api/trust", tags=["trust"])


class TrustScoreResponse(BaseModel):
    user_id: int
    trust_score: int
    tier: str


class TrustCheckRequest(BaseModel):
    user_id: int
    required_tier: str


class TrustCheckResponse(BaseModel):
    meets_requirement: bool
    current_tier: str


@router.get("/score/{user_id}", response_model=TrustScoreResponse)
async def get_trust_score(user_id: int):
    """Get a user's global trust score."""
    from bot.engagement.global_trust import get_global_trust_score, get_trust_tier

    score = await get_global_trust_score(db.pool, user_id)
    tier = await get_trust_tier(db.pool, user_id)

    return {"user_id": user_id, "trust_score": score, "tier": tier}


@router.get("/leaderboard", response_model=list[TrustScoreResponse])
async def get_trust_leaderboard(limit: int = 20):
    """Get top users by global trust score."""
    from bot.engagement.global_trust import get_global_leaderboard

    rows = await get_global_leaderboard(db.pool, limit)
    return rows


@router.post("/check", response_model=TrustCheckResponse)
async def check_trust_requirement(req: TrustCheckRequest):
    """Check if a user meets a trust requirement."""
    from bot.engagement.global_trust import check_trust_requirement

    meets, current_tier = await check_trust_requirement(
        db.pool, req.user_id, req.required_tier
    )

    return {"meets_requirement": meets, "current_tier": current_tier}


@router.get("/history/{user_id}")
async def get_trust_history(user_id: int, limit: int = 10):
    """Get a user's trust score history."""
    from bot.engagement.global_trust import get_trust_history

    history = await get_trust_history(db.pool, user_id, limit)
    return {"history": history}
