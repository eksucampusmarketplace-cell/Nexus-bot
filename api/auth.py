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

    # Always try primary token first
    from bot.registry import get_all

    all_tokens = [(None, settings.PRIMARY_BOT_TOKEN)]

    # Add all registered clone tokens
    registered_bots = get_all()
    for bot_id, bot_app in registered_bots.items():
        try:
            token = bot_app.bot.token
            if token != settings.PRIMARY_BOT_TOKEN:
                all_tokens.append((bot_id, token))
        except Exception:
            continue

    last_error = None
    for bot_id, token in all_tokens:
        try:
            data = validate_init_data(init_data, token)
            user = data["user"]
            user["validated_bot_token"] = token
            user["validated_bot_id"] = bot_id

            # Inject role based on bot ownership
            user_id = user.get("id")
            if bot_id is None:
                # Primary bot
                if user_id == settings.OWNER_ID:
                    user["role"] = "overlord"  # Main bot owner - highest privilege
                    user["is_overlord"] = True
                else:
                    user["role"] = "admin"
                    user["is_overlord"] = False
                logger.info(f"[AUTH] Validated via primary bot token | user_id={user_id} | role={user['role']}")
            else:
                # Clone bot — check if this user owns the clone
                user["role"] = "admin"
                user["is_overlord"] = False
                try:
                    from db.client import db as _db
                    from bot.utils.crypto import hash_token

                    if _db and _db.pool:
                        token_hash = hash_token(token)
                        async with _db.pool.acquire() as conn:
                            bot_row = await conn.fetchrow(
                                "SELECT owner_user_id FROM bots WHERE token_hash=$1",
                                token_hash,
                            )
                            if bot_row and bot_row["owner_user_id"] == user_id:
                                user["role"] = "owner"  # Clone owner
                                user["is_clone_owner"] = True
                except Exception as role_err:
                    logger.debug(f"[AUTH] Role lookup failed: {role_err}")

                logger.info(
                    f"[AUTH] Validated via clone token bot_id={bot_id} | user_id={user_id} | role={user['role']}"
                )

            return user
        except Exception as e:
            last_error = e
            continue

    logger.error(f"[AUTH] Validation failed for all tokens: {last_error}")
    raise HTTPException(
        status_code=401,
        detail={"error": "Invalid or expired initData", "code": "AUTH_FAILED"},
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


async def require_overlord(request: Request):
    """
    Require main bot owner (overlord) access.
    Used for sensitive operations that only the bot owner should access.
    """
    user = await get_current_user(request)
    
    if not user.get("is_overlord"):
        raise HTTPException(
            status_code=403,
            detail={"error": "This operation requires bot owner privileges", "code": "FORBIDDEN"}
        )
    
    return user


async def require_clone_owner_or_overlord(request: Request):
    """
    Require either clone owner or overlord access.
    Used for bot management operations.
    """
    user = await get_current_user(request)
    
    if user.get("is_overlord") or user.get("is_clone_owner"):
        return user
    
    raise HTTPException(
        status_code=403,
        detail={"error": "This operation requires bot ownership", "code": "FORBIDDEN"}
    )
