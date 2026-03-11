from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from db.ops.groups import get_user_managed_groups, get_group, update_group_settings
from db.ops.logs import get_recent_logs

router = APIRouter(prefix="/api/groups")

@router.get("")
async def list_groups(user: dict = Depends(get_current_user)):
    groups = await get_user_managed_groups(user['id'])
    return groups

@router.get("/{chat_id}")
async def group_details(chat_id: int, user: dict = Depends(get_current_user)):
    group = await get_group(chat_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

@router.put("/{chat_id}/settings")
async def update_settings(chat_id: int, settings: dict, user: dict = Depends(get_current_user)):
    # In a real app, verify user is admin in chat_id
    await update_group_settings(chat_id, settings)
    return {"status": "ok"}

@router.get("/{chat_id}/logs")
async def group_logs(chat_id: int, user: dict = Depends(get_current_user)):
    logs = await get_recent_logs(chat_id)
    return logs
