"""
api/routes/admin.py

Admin routes for memory management and system stats.
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from config import settings

log = logging.getLogger("admin_api")
router = APIRouter()


@router.get("/api/admin/memory")
async def memory_stats(request: Request):
    """Superadmin only — process memory stats."""
    if request.state.user_id != settings.OWNER_ID:
        raise HTTPException(status_code=403)
    lazy = request.app.state.lazy_manager
    return lazy.get_memory_usage() if lazy else {}
