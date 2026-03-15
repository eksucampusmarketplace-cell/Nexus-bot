import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qs

from fastapi import Depends, HTTPException, Request

from config import settings

logger = logging.getLogger(__name__)


def validate_init_data(init_data: str, bot_token: str) -> dict:
    if settings.SKIP_AUTH:
        return {
            "user": {"id": settings.OWNER_ID or 12345, "first_name": "DevUser"},
            "chat_id": None,
        }

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
            detail={
                "error": "Missing initData — send Authorization: tma <initData>",
                "code": "AUTH_FAILED",
            },
        )

    try:
        data = validate_init_data(init_data, settings.PRIMARY_BOT_TOKEN)
        user = data["user"]
        user["validated_bot_token"] = settings.PRIMARY_BOT_TOKEN
        return user
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
                user = data["user"]
                user["validated_bot_token"] = bot_token
                return user
            except Exception:
                continue

        logger.error(f"Auth validation failed: {e}")
        raise HTTPException(
            status_code=401, detail={"error": "Invalid or expired initData", "code": "AUTH_FAILED"}
        )


async def require_auth(request: Request):
    """
    Enhanced auth that includes user_id and bot_id for engagement routes.
    Returns a dict with user_id, bot_id, and other user info.
    Derives bot_id from validated_bot_token when possible.
    """
    user = await get_current_user(request)

    # Add user_id alias for compatibility with engagement routes
    user["user_id"] = user.get("id")

    # Derive bot_id from validated_bot_token if available
    validated_token = user.get("validated_bot_token")
    if validated_token:
        from bot.registry import get_all
        from bot.utils.crypto import hash_token
        
        token_hash = hash_token(validated_token)
        bots = get_all()
        for bot_id, bot_app in bots.items():
            if bot_app.bot.token == validated_token:
                user["bot_id"] = bot_id
                break
        else:
            # Fallback: use hash prefix as bot_id if no match
            user["bot_id"] = int(token_hash[:10], 16) % (10**10)
    else:
        # Try to get bot_id from request state or default to primary bot
        bot_id = getattr(request.state, "bot_id", None)
        if bot_id:
            user["bot_id"] = bot_id
        else:
            # Default to primary bot id
            from bot.registry import get_all

            bots = get_all()
            if bots:
                # Get first bot's id (typically primary)
                user["bot_id"] = list(bots.keys())[0]
            else:
                user["bot_id"] = 0

    return user
