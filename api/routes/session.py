"""
api/routes/session.py

Session string conversion endpoint.
Converts GramJS browser session to Telethon or Pyrogram format.
STATELESS — session content is never logged or stored.
"""

import base64
import logging
import struct

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from config import settings

router = APIRouter(tags=["session"])
log = logging.getLogger(__name__)


@router.post("/api/session/convert")
async def convert_session(body: dict, user: dict = Depends(get_current_user)):
    """
    Convert GramJS browser session to Telethon or Pyrogram format.
    Neither is compatible with GramJS directly.
    STATELESS — session string is never logged or stored anywhere.
    Processed in memory and immediately discarded.
    """
    gramjs_session = body.get("gramjs_session", "")
    target = body.get("target", "pyrogram")  # "telethon" or "pyrogram"

    if not gramjs_session:
        raise HTTPException(400, "Missing gramjs_session")

    try:
        decoded = base64.urlsafe_b64decode(gramjs_session + "==")

        if len(decoded) < 267:
            raise ValueError("Session string too short")

        # GramJS StringSession format: version(1) + dc_id(4) + ip_bytes(4) + port(2) + auth_key(256)
        # version is extracted but not used for conversion (format is compatible)
        dc_id = struct.unpack_from(">I", decoded, 1)[0]
        ip_bytes = decoded[5:9]
        port = struct.unpack_from(">H", decoded, 9)[0]
        auth_key = decoded[11:267]

        if target == "telethon":
            # Telethon StringSession format: version(1) + dc_id(4) + ip_bytes(4) + port(2) + auth_key(256)
            # Same layout as GramJS but different base64 encoding (standard vs urlsafe)
            telethon_bytes = bytes([1]) + struct.pack(">I", dc_id) + ip_bytes + struct.pack(">H", port) + auth_key
            result = base64.b64encode(telethon_bytes).decode()  # standard base64 for Telethon
            log.info(f"[SESSION] Converted to Telethon for user {user.get('id')} (content not logged)")
            return {"telethon_session": result, "session": result, "format": "telethon"}

        elif target == "pyrogram":
            # Pyrogram StringSession format: version(1) + dc_id(4) + ip_bytes(4) + port(2) + auth_key(256)
            pyrogram_bytes = struct.pack(">BI4sH", 1, dc_id, ip_bytes, port) + auth_key
            result = base64.urlsafe_b64encode(pyrogram_bytes).decode().rstrip("=")
            log.info(f"[SESSION] Converted to Pyrogram for user {user.get('id')} (content not logged)")
            return {"pyrogram_session": result, "session": result, "format": "pyrogram"}

        else:
            raise HTTPException(400, f"Unknown target format: {target}")

    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"[SESSION] Conversion failed: {type(e).__name__}: {e}")
        raise HTTPException(400, f"Invalid session format: {str(e)}")


@router.get("/api/session/config")
async def get_session_config():
    """Public config for MTProto client. api_id is not secret."""
    return {
        "api_id": int(settings.TG_API_ID or 0),
        "api_hash": settings.TG_API_HASH or "",
    }


@router.get("/api/session/status")
async def get_session_status():
    """Check if session conversion is configured (TG_API_ID and TG_API_HASH set)."""
    configured = bool(settings.TG_API_ID and settings.TG_API_HASH)
    return {"configured": configured}
