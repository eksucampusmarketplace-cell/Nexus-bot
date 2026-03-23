import time

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from config import settings
from db.client import db

router = APIRouter(prefix="/debug")


# Bug #10 fix: Add authentication to debug endpoints
@router.get("/db-ping")
async def db_ping(user: dict = Depends(get_current_user)):
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    start = time.time()
    async with db.pool.acquire() as conn:
        await conn.execute("SELECT 1")
    return {"latency_ms": (time.time() - start) * 1000}


# Bug #11 fix: Return 404 instead of soft error when DEBUG is off
@router.get("/info")
async def debug_info(user: dict = Depends(get_current_user)):
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "webhook_url": settings.webhook_url,
    }
