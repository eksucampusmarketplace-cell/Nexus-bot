"""
api/routes/auth.py

Authentication-related API routes.
"""

import logging
from fastapi import APIRouter, Request, HTTPException

log = logging.getLogger("auth_api")
router = APIRouter()


@router.post("/api/auth/validate-session")
async def validate_session(request: Request):
    """Validate a session — music/userbot feature removed."""
    raise HTTPException(410, "Music/userbot feature has been removed.")
