from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from api.utils.bot_helper import get_bot_for_group
from db.ops.booster import (
    get_channel_gate_config,
    save_channel_gate_config,
    get_channel_stats,
    get_channel_record,
    create_channel_record,
    set_channel_verified,
    set_channel_restricted,
    get_unverified_channel_users,
    delete_channel_record,
    delete_all_channel_records,
)

router = APIRouter(prefix="/api/groups/{chat_id}/channel-gate", tags=["channel-gate"])


# ==================== Config ====================


class ChannelGateConfigUpdate(BaseModel):
    force_channel_enabled: Optional[bool] = None
    force_channel_id: Optional[int] = None
    force_channel_username: Optional[str] = None
    force_channel_action: Optional[str] = None
    force_channel_message: Optional[str] = None
    force_channel_kick_after: Optional[int] = None
    recheck_interval_secs: Optional[int] = None
    exempt_admins: Optional[bool] = None
    exempt_specific_users: Optional[List[int]] = None


@router.get("/config")
async def get_channel_gate_config_route(chat_id: int):
    """Get channel gate configuration for a group."""
    return await get_channel_gate_config(chat_id)


@router.put("/config")
async def update_channel_gate_config(chat_id: int, config: ChannelGateConfigUpdate):
    """Update channel gate configuration."""
    current = await get_channel_gate_config(chat_id)
    update_data = config.model_dump(exclude_unset=True)
    current.update(update_data)
    await save_channel_gate_config(chat_id, current)
    return {"success": True, "config": current}


# ==================== Stats ====================


@router.get("/stats")
async def get_channel_gate_stats(chat_id: int):
    """Get channel gate statistics."""
    return await get_channel_stats(chat_id)


# ==================== Records ====================


@router.get("/records/{user_id}")
async def get_channel_record_route(chat_id: int, user_id: int):
    """Get a user's channel verification record."""
    record = await get_channel_record(chat_id, user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("/pending")
async def get_pending_users(chat_id: int):
    """Get all users pending channel verification."""
    return await get_unverified_channel_users(chat_id)


# ==================== Actions ====================


class ChannelLinkRequest(BaseModel):
    channel_id: Optional[int] = None
    channel_username: Optional[str] = None


class VerifyRequest(BaseModel):
    channel_id: int


@router.post("/link")
async def link_channel(chat_id: int, data: ChannelLinkRequest):
    """Link a required channel to a group."""
    config = await get_channel_gate_config(chat_id)
    config["force_channel_enabled"] = True

    if data.channel_id:
        config["force_channel_id"] = data.channel_id
    if data.channel_username:
        config["force_channel_username"] = data.channel_username

    await save_channel_gate_config(chat_id, config)
    return {"success": True, "config": config}


@router.delete("/unlink")
async def unlink_channel(chat_id: int):
    """Remove channel requirement."""
    # Unrestrict all users first
    await delete_all_channel_records(chat_id)

    config = await get_channel_gate_config(chat_id)
    config["force_channel_enabled"] = False
    config["force_channel_id"] = None
    config["force_channel_username"] = None

    await save_channel_gate_config(chat_id, config)
    return {"success": True}


@router.post("/verify/{user_id}")
async def verify_user(chat_id: int, user_id: int, data: VerifyRequest):
    """Manually verify a user's channel membership."""
    # Check if user is member of the channel
    from bot.registry import get as registry_get
    from telegram.error import TelegramError

    ptb_app = registry_get(0)  # Get primary bot
    if not ptb_app:
        raise HTTPException(status_code=500, detail="Bot not available")

    try:
        member = await ptb_app.bot.get_chat_member(data.channel_id, user_id)
        if member.status in ["member", "administrator", "creator"]:
            await set_channel_verified(chat_id, user_id)
            return {"success": True, "verified": True}
    except TelegramError:
        pass

    return {"success": True, "verified": False}


@router.post("/kick/{user_id}")
async def kick_user(chat_id: int, user_id: int):
    """Kick a user from the group."""
    ptb_app = await get_bot_for_group(chat_id)

    if not ptb_app:
        raise HTTPException(status_code=500, detail="Bot not available")

    try:
        await ptb_app.bot.ban_chat_member(chat_id, user_id)
        await ptb_app.bot.unban_chat_member(chat_id, user_id)
        await delete_channel_record(chat_id, user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/exempt/{user_id}")
async def exempt_user_channel(chat_id: int, user_id: int):
    """Exempt a user from channel requirement."""
    # Create or update channel record to mark as verified
    await create_channel_record(chat_id, user_id, channel_id=0)
    await set_channel_verified(chat_id, user_id)
    return {"success": True}


@router.delete("/exempt/{user_id}")
async def remove_channel_exemption(chat_id: int, user_id: int):
    """Remove channel exemption from a user."""
    record = await get_channel_record(chat_id, user_id)
    if record:
        await set_channel_restricted(chat_id, user_id, True)
    return {"success": True}


@router.post("/restrict/{user_id}")
async def restrict_user_channel(chat_id: int, user_id: int):
    """Manually restrict a user pending channel verification."""
    await create_channel_record(chat_id, user_id, channel_id=0)
    await set_channel_restricted(chat_id, user_id, True)
    return {"success": True}


@router.delete("/{user_id}")
async def delete_channel_record_route(chat_id: int, user_id: int):
    """Delete a channel verification record."""
    success = await delete_channel_record(chat_id, user_id)
    return {"success": success}
