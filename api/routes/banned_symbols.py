"""
api/routes/banned_symbols.py

API routes for managing banned symbols (UltraPro feature).
Allows Mini App to manage banned symbols for username filtering.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import get_current_user
from bot.billing.billing_helpers import get_owner_plan
from db.ops.banned_symbols import (
    get_banned_symbols,
    add_banned_symbol,
    remove_banned_symbol,
    clear_banned_symbols,
)
from db.client import db

log = logging.getLogger("banned_symbols_api")
router = APIRouter()

VALID_ACTIONS = ["ban", "kick", "mute"]
MIN_PLAN_FOR_SYMBOLS = ["pro", "unlimited"]


class AddSymbolRequest(BaseModel):
    symbol: str
    action: str = "ban"


class SetActionRequest(BaseModel):
    action: str
    symbol: str | None = None


async def _check_ultrapro_access(request: Request, chat_id: int):
    """Check if user has UltraPro access for banned symbols feature."""
    user = request.state.user
    owner_id = user.get("id")

    plan = await get_owner_plan(request.app.state.db, owner_id)

    if plan not in MIN_PLAN_FOR_SYMBOLS:
        raise HTTPException(
            status_code=403,
            detail=f"UltraPro feature. Current plan: {plan}. Upgrade to Pro or Unlimited."
        )

    return True


@router.get("/api/groups/{chat_id}/banned-symbols")
async def get_banned_symbols_endpoint(
    request: Request,
    chat_id: int,
    user: dict = Depends(get_current_user)
):
    """Get all banned symbols for a group."""
    # Check UltraPro access
    await _check_ultrapro_access(request, chat_id)

    try:
        symbols = await get_banned_symbols(chat_id)
        return {
            "symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        log.error(f"Failed to get banned symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/groups/{chat_id}/banned-symbols")
async def add_banned_symbol_endpoint(
    request: Request,
    chat_id: int,
    req: AddSymbolRequest,
    user: dict = Depends(get_current_user)
):
    """Add a banned symbol to a group."""
    # Check UltraPro access
    await _check_ultrapro_access(request, chat_id)

    # Validate action
    if req.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Valid actions: {', '.join(VALID_ACTIONS)}"
        )

    symbol = req.symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol cannot be empty")

    try:
        owner_id = user.get("id")
        await add_banned_symbol(chat_id, symbol, owner_id, req.action)
        return {
            "ok": True,
            "symbol": symbol,
            "action": req.action,
            "message": f"Added '{symbol}' with action '{req.action}'"
        }
    except Exception as e:
        log.error(f"Failed to add banned symbol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/groups/{chat_id}/banned-symbols/{symbol}")
async def remove_banned_symbol_endpoint(
    request: Request,
    chat_id: int,
    symbol: str,
    user: dict = Depends(get_current_user)
):
    """Remove a banned symbol from a group."""
    # Check UltraPro access
    await _check_ultrapro_access(request, chat_id)

    try:
        removed = await remove_banned_symbol(chat_id, symbol)
        if not removed:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol '{symbol}' not found in banned symbols list"
            )
        return {
            "ok": True,
            "symbol": symbol,
            "message": f"Removed '{symbol}' from banned symbols"
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to remove banned symbol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/groups/{chat_id}/banned-symbols")
async def clear_banned_symbols_endpoint(
    request: Request,
    chat_id: int,
    user: dict = Depends(get_current_user)
):
    """Clear all banned symbols from a group."""
    # Check UltraPro access
    await _check_ultrapro_access(request, chat_id)

    try:
        await clear_banned_symbols(chat_id)
        return {
            "ok": True,
            "message": "All banned symbols cleared"
        }
    except Exception as e:
        log.error(f"Failed to clear banned symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/groups/{chat_id}/banned-symbols/matches")
async def get_banned_symbol_matches_endpoint(
    request: Request,
    chat_id: int,
    limit: int = 50,
    user: dict = Depends(get_current_user)
):
    """Get recent banned symbol matches for a group (audit log)."""
    # Check UltraPro access
    await _check_ultrapro_access(request, chat_id)

    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, username, matched_symbol, action_taken, matched_at
                FROM banned_symbol_matches
                WHERE chat_id = $1
                ORDER BY matched_at DESC
                LIMIT $2
                """,
                chat_id, limit
            )

        matches = [
            {
                "user_id": row["user_id"],
                "username": row["username"],
                "matched_symbol": row["matched_symbol"],
                "action_taken": row["action_taken"],
                "matched_at": row["matched_at"].isoformat() if row["matched_at"] else None
            }
            for row in rows
        ]

        return {
            "matches": matches,
            "count": len(matches)
        }
    except Exception as e:
        log.error(f"Failed to get banned symbol matches: {e}")
        raise HTTPException(status_code=500, detail=str(e))
