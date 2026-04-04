"""
api/routes/insurance.py

API endpoints for Group Insurance system.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from db.client import db

router = APIRouter(prefix="/api/insurance", tags=["insurance"])


class InsuranceStatusResponse(BaseModel):
    tier: str
    active: bool
    auto_lockdown: bool
    auto_cleanup: bool
    max_claims_per_month: int
    claims_used: int
    expires_at: str | None


class IncidentResponse(BaseModel):
    id: int
    type: str
    severity: str
    details: str
    auto_action: bool
    at: str


@router.get("/status/{chat_id}/{bot_id}", response_model=InsuranceStatusResponse)
async def get_insurance_status(chat_id: int, bot_id: int):
    """Get insurance status for a group."""
    from bot.billing.group_insurance import get_group_insurance

    status = await get_group_insurance(db.pool, chat_id, bot_id)
    return {
        "tier": status["tier"],
        "active": status["active"],
        "auto_lockdown": status["auto_lockdown"],
        "auto_cleanup": status["auto_cleanup"],
        "max_claims_per_month": status["max_claims_per_month"],
        "claims_used": status["claims_used"],
        "expires_at": status.get("expires_at") if status.get("expires_at") else None,
    }


@router.get("/incidents/{chat_id}/{bot_id}")
async def get_incidents(chat_id: int, bot_id: int, days: int = 30):
    """Get recent incidents for a group."""
    from bot.billing.group_insurance import get_incidents

    incidents = await get_incidents(db.pool, chat_id, bot_id, days)
    return {"incidents": incidents}


@router.get("/tiers")
async def get_insurance_tiers():
    """Get available insurance tiers."""
    from bot.billing.group_insurance import get_tiers

    tiers = await get_tiers()
    return {"tiers": tiers}


@router.post("/enable/{chat_id}/{bot_id}")
async def enable_insurance(
    chat_id: int,
    bot_id: int,
    tier: str = "basic",
    protection_types: list[str] = None,
):
    """Enable insurance for a group (called after payment)."""
    from bot.billing.group_insurance import enable_group_insurance

    if protection_types is None:
        protection_types = ["raid", "spam"]

    result = await enable_group_insurance(db.pool, chat_id, bot_id, tier, protection_types)
    return result


@router.post("/disable/{chat_id}/{bot_id}")
async def disable_insurance(chat_id: int, bot_id: int):
    """Disable insurance for a group."""
    from bot.billing.group_insurance import disable_group_insurance

    result = await disable_group_insurance(db.pool, chat_id, bot_id)
    return result