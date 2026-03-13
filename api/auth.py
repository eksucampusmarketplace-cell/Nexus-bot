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
        return {"user": {"id": settings.OWNER_ID or 12345, "first_name": "DevUser"}, "chat_id": None}

    vals = parse_qs(init_data)
    if "hash" not in vals:
        raise ValueError("Missing hash")

    received_hash = vals.pop("hash")[0]
    data_check_string = "\n".join(f"{k}={v[0]}" for k, v in sorted(vals.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid hash")

    user_data = json.loads(vals.get("user", ["{}"])[0])
    return {"user": user_data}


def _extract_init_data(request: Request) -> str | None:
    """
    Extract initData from either:
      - Authorization: tma <initData>   (new standard)
      - X-Telegram-Init-Data: <initData>  (legacy header)
      - x-init-data: <initData>           (legacy header variant)
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("tma "):
        return auth_header[4:].strip()

    init_data = request.headers.get("X-Telegram-Init-Data")
    if init_data:
        return init_data.strip()

    init_data = request.headers.get("x-init-data")
    if init_data:
        return init_data.strip()

    return None


async def get_current_user(request: Request):
    if settings.SKIP_AUTH:
        return {"id": settings.OWNER_ID or 12345, "first_name": "DevUser"}

    init_data = _extract_init_data(request)
    if not init_data:
        raise HTTPException(
            status_code=401,
            detail={"error": "Missing initData — send Authorization: tma <initData>", "code": "AUTH_FAILED"}
        )

    try:
        data = validate_init_data(init_data, settings.PRIMARY_BOT_TOKEN)
        return data["user"]
    except Exception as e:
        # If primary bot token fails, try all registered clone bots
        from bot.registry import get_all
        registered_bots = get_all()
        
        for bot_id, bot_app in registered_bots.items():
            try:
                # Get token from the bot instance
                bot_token = bot_app.bot.token
                if bot_token == settings.PRIMARY_BOT_TOKEN:
                    continue
                data = validate_init_data(init_data, bot_token)
                return data["user"]
            except Exception:
                continue
        
        logger.error(f"Auth validation failed: {e}")
        raise HTTPException(
            status_code=401, 
            detail={"error": "Invalid or expired initData", "code": "AUTH_FAILED"}
        )
