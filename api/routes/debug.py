from fastapi import APIRouter
from config import settings
from db.client import db
import time

router = APIRouter(prefix="/debug")

@router.get("/db-ping")
async def db_ping():
    start = time.time()
    async with db.pool.acquire() as conn:
        await conn.execute("SELECT 1")
    return {"latency_ms": (time.time() - start) * 1000}

@router.get("/info")
async def debug_info():
    if not settings.DEBUG:
        return {"error": "Debug mode disabled"}
    return {
        "primary_token_hash": settings.PRIMARY_BOT_TOKEN[:10] + "...",
        "webhook_url": settings.webhook_url
    }
