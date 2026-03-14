from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from db.ops.modules import get_modules, set_module

router = APIRouter(prefix="/api/groups")


@router.get("/{chat_id}/modules")
async def list_modules(chat_id: int, user: dict = Depends(get_current_user)):
    # Verify user manages chat_id
    modules = await get_modules(chat_id)
    return modules


@router.put("/{chat_id}/modules/{name}")
async def toggle_module(
    chat_id: int, name: str, body: dict, user: dict = Depends(get_current_user)
):
    enabled = body.get("enabled", False)
    await set_module(chat_id, name, enabled)
    return {"status": "ok"}
