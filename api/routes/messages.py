from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from db.ops.groups import get_custom_messages, get_custom_message, set_custom_message, delete_custom_message
from bot.utils.messages import DEFAULTS

router = APIRouter(prefix="/api/groups/{chat_id}/messages")

# Valid message keys
VALID_MESSAGE_KEYS = set(DEFAULTS.keys())
MAX_BODY_LENGTH = 1000


@router.get("")
async def list_messages(chat_id: int, user: dict = Depends(get_current_user)):
    """
    Get all messages for a group.
    Returns dict of {key: {body, isCustom}} for each message.
    """
    custom_messages = await get_custom_messages(chat_id)
    
    result = {}
    for key in DEFAULTS:
        body = custom_messages.get(key)
        result[key] = {
            "body": body if body else DEFAULTS[key],
            "isCustom": key in custom_messages
        }
    
    return result


@router.get("/{key}")
async def get_message(chat_id: int, key: str, user: dict = Depends(get_current_user)):
    """Get a specific message for a group."""
    if key not in VALID_MESSAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown message key: {key}")
    
    custom_body = await get_custom_message(chat_id, key)
    
    return {
        "key": key,
        "body": custom_body if custom_body else DEFAULTS[key],
        "isCustom": custom_body is not None
    }


@router.put("/{key}")
async def update_message(
    chat_id: int,
    key: str,
    payload: dict,
    user: dict = Depends(get_current_user)
):
    """Update a custom message for a group."""
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
    from config import settings
    footer_text = POWERED_BY_FOOTER.format(bot_name=settings.BOT_DISPLAY_NAME).strip()
    body = body.replace(footer_text, "").strip()
    
    await set_custom_message(chat_id, key, body, user["id"])
    
    return {
        "key": key,
        "body": body,
        "isCustom": True
    }


@router.delete("/{key}")
async def reset_message(chat_id: int, key: str, user: dict = Depends(get_current_user)):
    """Reset a message to default."""
    if key not in VALID_MESSAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown message key: {key}")
    
    await delete_custom_message(chat_id, key)
    
    return {
        "key": key,
        "body": DEFAULTS[key],
        "isCustom": False
    }
