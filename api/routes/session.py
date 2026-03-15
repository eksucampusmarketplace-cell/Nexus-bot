"""
api/routes/session.py

Session string conversion endpoint.
Converts GramJS/Telethon session strings to Pyrogram format.
STATELESS — session content is never logged or stored.
"""

import base64
import logging
import struct

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user

router = APIRouter(tags=["session"])
log = logging.getLogger(__name__)


@router.post("/api/session/convert")
async def convert_session(body: dict, user: dict = Depends(get_current_user)):
    """
    Convert GramJS/Telethon session string to Pyrogram format.
    STATELESS — session string is never logged or stored anywhere.
    Processed in memory and immediately discarded.
    """
    gramjs_session = body.get("gramjs_session", "")
    if not gramjs_session:
        raise HTTPException(400, "Missing gramjs_session")

    try:
        decoded = base64.urlsafe_b64decode(gramjs_session + "==")

        if len(decoded) < 267:
            raise ValueError("Session string too short")

        dc_id = struct.unpack_from(">I", decoded, 1)[0]
        ip_bytes = decoded[5:9]
        port = struct.unpack_from(">H", decoded, 9)[0]
        auth_key = decoded[11:267]

        pyrogram_bytes = struct.pack(">BI4sH", 1, dc_id, ip_bytes, port) + auth_key
        pyrogram_session = base64.urlsafe_b64encode(pyrogram_bytes).decode().rstrip("=")

        log.info(f"[SESSION] Converted session for user {user.get('id')} (content not logged)")

        return {"pyrogram_session": pyrogram_session}
    except Exception as e:
        log.warning(f"[SESSION] Conversion failed: {type(e).__name__}")
        raise HTTPException(400, f"Invalid session format: {str(e)}")
