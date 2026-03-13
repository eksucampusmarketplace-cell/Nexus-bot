
from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from db.ops.bots_messages import get_bot_custom_messages, get_bot_custom_message, set_bot_custom_message, delete_bot_custom_message
from bot.utils.messages import DEFAULTS
from config import settings

router = APIRouter(prefix="/api/bots/{bot_id}/messages", tags=["bot-messages"])

# Valid message keys
VALID_MESSAGE_KEYS = set(DEFAULTS.keys())
MAX_BODY_LENGTH = 1000

@router.get("")
async def list_bot_messages(bot_id: int, user: dict = Depends(get_current_user)):
    """Get all custom messages for a bot."""
    custom_messages = await get_bot_custom_messages(bot_id)
    
    result = {}
    for key in DEFAULTS:
        body = custom_messages.get(key)
        result[key] = {
            "body": body if body else DEFAULTS[key],
            "isCustom": key in custom_messages
        }
    
    return result

@router.put("/{key}")
async def update_bot_message(
    bot_id: int,
    key: str,
    payload: dict,
    user: dict = Depends(get_current_user)
):
    """Update a custom message for a bot."""
    if key not in VALID_MESSAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown message key: {key}")
    
    body = payload.get("body", "").strip()
    
    if len(body) > MAX_BODY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long ({len(body)} chars). Maximum is {MAX_BODY_LENGTH}."
        )
    
    # Strip any footer that might have been accidentally included
    from bot.utils.messages import POWERED_BY_FOOTER
    footer_text = POWERED_BY_FOOTER.format(bot_name=settings.BOT_DISPLAY_NAME).strip()
    body = body.replace(footer_text, "").strip()
    
    await set_bot_custom_message(bot_id, key, body, user["id"])
    
    return {
        "key": key,
        "body": body,
        "isCustom": True
    }

@router.delete("/{key}")
async def reset_bot_message(bot_id: int, key: str, user: dict = Depends(get_current_user)):
    """Reset a bot message to default."""
    if key not in VALID_MESSAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown message key: {key}")
    
    await delete_bot_custom_message(bot_id, key)
    
    return {
        "key": key,
        "body": DEFAULTS[key],
        "isCustom": False
    }
