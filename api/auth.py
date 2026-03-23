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

    # Bug #20 fix: Copy vals before mutating to avoid corrupting the input dict
    received_hash = vals["hash"][0]
    check_vals = {k: v for k, v in vals.items() if k != "hash"}
    data_check_string = "\n".join(f"{k}={v[0]}" for k, v in sorted(check_vals.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid hash")

    user_data = json.loads(check_vals.get("user", ["{}"])[0])
    # Bug #21 fix: Return chat_id consistently with SKIP_AUTH path
    chat_id = check_vals.get("chat_instance", [None])[0]
    return {"user": user_data, "chat_id": chat_id}


def _extract_init_data(request: Request) -> str | None:
    """
    Extract initData from either:
      - Authorization: tma <initData>   (new standard)
      - X-Telegram-Init-Data: <initData>  (legacy header)
      - x-init-data: <initData>           (legacy header variant)
      - Query param ?token=               (for EventSource/SSE which cannot send headers)
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

    # Query param fallback for EventSource (browsers can't set custom headers on SSE)
    init_data = request.query_params.get("token")
    if init_data:
        return init_data.strip()

    return None


async def get_current_user(request: Request):
    if settings.SKIP_AUTH:
        user = {"id": settings.OWNER_ID or 12345, "first_name": "DevUser", "role": "owner"}
        return user

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
        
        # Inject role based on bot ownership
        user_id = user.get('id')
        if user_id == settings.OWNER_ID:
            user['role'] = 'owner'
        else:
            user['role'] = 'admin'
        
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
                
                # Determine role: check if this user owns this bot
                user_id = user.get('id')
                try:
                    from db.client import db as _db
                    from bot.utils.crypto import hash_token
                    if _db and _db.pool:
                        token_hash = hash_token(bot_token)
                        async with _db.pool.acquire() as conn:
                            bot_row = await conn.fetchrow(
                                'SELECT owner_user_id FROM bots WHERE token_hash=$1',
                                token_hash
                            )
                            if bot_row and bot_row['owner_user_id'] == user_id:
                                user['role'] = 'owner'
                            else:
                                user['role'] = 'admin'
                except Exception as role_err:
                    logger.debug(f'[auth] Role lookup failed: {role_err}')
                    user['role'] = 'admin'
                
                return user
            except Exception:
                continue
        else:
            logger.error(f"Auth validation failed: {e}")
            raise HTTPException(
                status_code=401, detail={"error": "Invalid or expired initData", "code": "AUTH_FAILED"}
            )

    # Bug #4 fix: Removed unreachable dead code block.
    # Role injection is already handled above in both the primary and clone bot paths.


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
            # Bug #23/#27 fix: Fallback to primary bot id instead of nonsensical hash-derived number
            from bot.registry import get_all as _get_all_bots
            _all_bots = _get_all_bots()
            if _all_bots:
                user["bot_id"] = list(_all_bots.keys())[0]
            else:
                user["bot_id"] = 0
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
