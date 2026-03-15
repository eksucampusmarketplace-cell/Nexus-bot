"""
api/routes/admin.py

Admin routes for memory management and system stats.
"""

import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from config import settings
from api.auth import get_current_user

log = logging.getLogger("admin_api")
router = APIRouter()


@router.get("/api/admin/memory")
async def memory_stats(request: Request):
    """Superadmin only — process memory stats."""
    if request.state.user_id != settings.OWNER_ID:
        raise HTTPException(status_code=403)
    lazy = request.app.state.lazy_manager
    return lazy.get_memory_usage() if lazy else {}


@router.get("/api/admin/stats")
async def admin_stats(request: Request, user: dict = Depends(get_current_user)):
    """Owner-only — system-wide stats for the owner dashboard."""
    if user.get("id") != settings.OWNER_ID:
        raise HTTPException(status_code=403)
    pool = request.app.state.db
    if not pool:
        raise HTTPException(status_code=503, detail="Database not available")
    bots = await pool.fetchval(
        "SELECT COUNT(*) FROM bots WHERE status='active' AND is_primary=FALSE"
    )
    groups = await pool.fetchval("SELECT COUNT(*) FROM groups")
    users = await pool.fetchval("SELECT COUNT(DISTINCT user_id) FROM users")
    return {"bots": bots or 0, "groups": groups or 0, "users": users or 0}
