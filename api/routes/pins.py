"""
api/routes/pins.py

REST API for pinned message management.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from db.client import db
import db.ops.pins as pins_db

router = APIRouter(prefix="/api/groups/{chat_id}/pins", tags=["pins"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_pins(chat_id: int, user: dict = Depends(get_current_user)):
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, chat_id, message_id, pinned_by, pinned_at, is_current
                   FROM pinned_messages
                   WHERE chat_id = $1
                   ORDER BY pinned_at DESC
                   LIMIT 50""",
                chat_id,
            )
        return {"ok": True, "pins": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"[Pins API] list_pins error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current")
async def get_current_pin(chat_id: int, user: dict = Depends(get_current_user)):
    try:
        pin = await pins_db.get_current_pin(db.pool, chat_id)
        return {"ok": True, "pin": pin}
    except Exception as e:
        logger.error(f"[Pins API] get_current_pin error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{pin_id}")
async def delete_pin(chat_id: int, pin_id: int, user: dict = Depends(get_current_user)):
    try:
        async with db.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM pinned_messages WHERE id = $1 AND chat_id = $2",
                pin_id, chat_id,
            )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Pin not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Pins API] delete_pin error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
