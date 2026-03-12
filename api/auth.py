import hashlib
import hmac
import json
from urllib.parse import parse_qs
from fastapi import Request, HTTPException, Depends
from config import settings
import logging

logger = logging.getLogger(__name__)

def validate_init_data(init_data: str, bot_token: str) -> dict:
    if settings.SKIP_AUTH:
        # Mock data for local testing
        return {"user": {"id": settings.OWNER_ID or 12345, "first_name": "DevUser"}, "chat_id": None}

    vals = parse_qs(init_data)
    if "hash" not in vals:
        raise ValueError("Missing hash")

    received_hash = vals.pop("hash")[0]
    data_check_string = "\n".join(f"{k}={v[0]}" for k, v in sorted(vals.items()))
    
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if calculated_hash != received_hash:
        raise ValueError("Invalid hash")
    
    user_data = json.loads(vals.get("user", ["{}"])[0])
    return {"user": user_data}

async def get_current_user(request: Request):
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.headers.get("x-init-data")
    )
    if not init_data:
        if settings.SKIP_AUTH:
             return {"id": settings.OWNER_ID or 12345}
        raise HTTPException(status_code=401, detail={"error": "Missing initData", "code": "AUTH_FAILED"})
    
    try:
        # We check against the primary bot token
        data = validate_init_data(init_data, settings.PRIMARY_BOT_TOKEN)
        return data["user"]
    except Exception as e:
        logger.error(f"Auth validation failed: {e}")
        raise HTTPException(status_code=401, detail={"error": "Invalid initData", "code": "AUTH_FAILED"})
