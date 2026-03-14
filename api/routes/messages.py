from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from db.ops.groups import (
    get_custom_messages,
    get_custom_message,
    set_custom_message,
    delete_custom_message,
)
from bot.utils.messages import DEFAULTS

router = APIRouter(prefix="/api/groups/{chat_id}/messages")

# Valid message keys
VALID_MESSAGE_KEYS = set(DEFAULTS.keys())
# Keys that only bot owners can edit (start_private, help, etc.)
BOT_OWNER_ONLY_KEYS = {"start_private", "help"}
# Keys that group owners/admins can edit
GROUP_EDITABLE_KEYS = VALID_MESSAGE_KEYS - BOT_OWNER_ONLY_KEYS
MAX_BODY_LENGTH = 1000


async def _get_user_group_role(chat_id: int, user_id: int, bot) -> str:
    """
    Check user's role in a group via Telegram API.
    Returns: 'owner', 'admin', 'member', or 'none'
    """
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        status = member.status
        if status == "creator":
            return "owner"
        elif status == "administrator":
            return "admin"
        elif status in ["member", "restricted"]:
            return "member"
        else:
            return "none"
    except Exception:
        return "none"


async def _check_message_edit_permission(chat_id: int, user: dict, key: str, bot=None):
    """
    Check if user can edit a message key.
    - Bot owner can edit any message
    - Group owner/admin can edit group-level messages (except bot owner only keys)
    """
    user_id = user.get("id")
    user_role = user.get("role")

    # Bot owner can edit anything
    if user_role == "owner":
        return True

    # Check if it's a group-editable key
    if key not in GROUP_EDITABLE_KEYS:
        # Group owners can't edit these - only bot owner
        return False

    # For group-level editing, check if user is group owner or admin
    # If we have bot available, check Telegram status
    if bot:
        role = await _get_user_group_role(chat_id, user_id, bot)
        if role in ("owner", "admin"):
            return True

    # Also check if user has is_group_owner or is_admin in user context
    return user.get("is_group_owner") or user.get("is_admin")


@router.get("")
async def list_messages(chat_id: int, user: dict = Depends(get_current_user)):
    """
    Get all messages for a group.
    Returns dict of {key: {body, isCustom, canEdit}} for each message.
    """
    custom_messages = await get_custom_messages(chat_id)
    user_role = user.get("role")

    # Get bot for checking Telegram admin status
    from bot.registry import get_all

    bots = get_all()
    bot = None
    if bots:
        # Use primary bot
        for bid, b in bots.items():
            if b.bot_data.get("is_primary"):
                bot = b.bot
                break
        if not bot and bots:
            bot = list(bots.values())[0].bot

    result = {}
    for key in DEFAULTS:
        body = custom_messages.get(key)
        can_edit = await _check_message_edit_permission(chat_id, user, key, bot)
        result[key] = {
            "body": body if body else DEFAULTS[key],
            "isCustom": key in custom_messages,
            "canEdit": can_edit,
        }

    return result


@router.get("/{key}")
async def get_message(chat_id: int, key: str, user: dict = Depends(get_current_user)):
    """Get a specific message for a group."""
    if key not in VALID_MESSAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown message key: {key}")

    custom_body = await get_custom_message(chat_id, key)

    # Get bot for checking Telegram admin status
    from bot.registry import get_all

    bots = get_all()
    bot = None
    if bots:
        for bid, b in bots.items():
            if b.bot_data.get("is_primary"):
                bot = b.bot
                break
        if not bot and bots:
            bot = list(bots.values())[0].bot

    can_edit = await _check_message_edit_permission(chat_id, user, key, bot)

    return {
        "key": key,
        "body": custom_body if custom_body else DEFAULTS[key],
        "isCustom": custom_body is not None,
        "canEdit": can_edit,
    }


@router.put("/{key}")
async def update_message(
    chat_id: int, key: str, payload: dict, user: dict = Depends(get_current_user)
):
    """Update a custom message for a group."""
    if key not in VALID_MESSAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown message key: {key}")

    # Get bot for checking Telegram admin status
    from bot.registry import get_all

    bots = get_all()
    bot = None
    if bots:
        for bid, b in bots.items():
            if b.bot_data.get("is_primary"):
                bot = b.bot
                break
        if not bot and bots:
            bot = list(bots.values())[0].bot

    # Check permission
    if not await _check_message_edit_permission(chat_id, user, key, bot):
        raise HTTPException(
            status_code=403,
            detail=f"You don't have permission to edit this message. Only bot owners can edit /start and /help messages.",
        )

    body = payload.get("body", "").strip()

    if len(body) > MAX_BODY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long ({len(body)} chars). Maximum is {MAX_BODY_LENGTH}.",
        )

    # Strip any footer that might have been accidentally included
    from bot.utils.messages import POWERED_BY_FOOTER
    from config import settings

    footer_text = POWERED_BY_FOOTER.format(bot_name=settings.BOT_DISPLAY_NAME).strip()
    body = body.replace(footer_text, "").strip()

    await set_custom_message(chat_id, key, body, user["id"])

    return {"key": key, "body": body, "isCustom": True}


@router.delete("/{key}")
async def reset_message(chat_id: int, key: str, user: dict = Depends(get_current_user)):
    """Reset a message to default."""
    if key not in VALID_MESSAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown message key: {key}")

    # Get bot for checking Telegram admin status
    from bot.registry import get_all

    bots = get_all()
    bot = None
    if bots:
        for bid, b in bots.items():
            if b.bot_data.get("is_primary"):
                bot = b.bot
                break
        if not bot and bots:
            bot = list(bots.values())[0].bot

    # Check permission
    if not await _check_message_edit_permission(chat_id, user, key, bot):
        raise HTTPException(
            status_code=403, detail=f"You don't have permission to reset this message."
        )

    await delete_custom_message(chat_id, key)

    return {"key": key, "body": DEFAULTS[key], "isCustom": False}
