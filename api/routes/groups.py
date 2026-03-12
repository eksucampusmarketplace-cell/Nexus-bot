from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth import get_current_user
from db.client import db
from db.ops.groups import get_user_managed_groups, get_group, update_group_settings
from db.ops.logs import get_recent_logs
import json

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

@router.put("/{chat_id}/settings/bulk")
async def bulk_update_settings(chat_id: int, request: Request):
    """Bulk update multiple settings at once (for templates)."""
    body = await request.json()
    settings = body.get("settings", {})
    
    async with db.pool.acquire() as conn:
        # Get current settings
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
        if not row:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Merge with new settings
        current = json.loads(row['settings']) if row['settings'] else {}
        merged = { **current, **settings }
        
        # Update
        await conn.execute(
            "UPDATE groups SET settings = $1 WHERE chat_id = $2",
            json.dumps(merged), chat_id
        )
    
    # Publish SSE event
    from api.routes.events import EventBus
    await EventBus.publish(chat_id, "settings_change", {"settings": settings})
    
    return {"status": "ok", "settings": merged}

@router.get("/{chat_id}/logs")
async def group_logs(chat_id: int, user: dict = Depends(get_current_user)):
    logs = await get_recent_logs(chat_id)
    return logs
