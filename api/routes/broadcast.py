from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from api.auth import get_current_user
from db.ops.broadcast import (
    create_broadcast_task,
    get_broadcast_task,
    get_bot_broadcasts,
    get_broadcast_targets,
)
from db.ops.bots import get_bot_by_id, get_bots_by_owner
from db.client import db

router = APIRouter(prefix="/api/broadcast")


@router.post("")
async def start_broadcast(
    bot_id: int = Body(...),
    target_type: str = Body(...),  # 'pms', 'groups', 'all'
    content: str = Body(...),
    media_file_id: Optional[str] = Body(None),
    media_type: Optional[str] = Body(None),
    user: dict = Depends(get_current_user),
):
    """Start a broadcast task."""
    # Verify user owns the bot or is primary owner
    bot = await get_bot_by_id(db.pool, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Check permission: bot owner or main bot owner
    from config import settings

    is_main_owner = user["id"] == settings.OWNER_ID
    if bot["owner_user_id"] != user["id"] and not is_main_owner:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Get targets to count them
    targets = await get_broadcast_targets(db.pool, bot_id, target_type)
    if not targets:
        raise HTTPException(status_code=400, detail="No targets found for this selection")

    task_id = await create_broadcast_task(
        db.pool,
        {
            "owner_id": user["id"],
            "bot_id": bot_id,
            "target_type": target_type,
            "content": content,
            "media_file_id": media_file_id,
            "media_type": media_type,
            "total_targets": len(targets),
        },
    )

    return {"task_id": task_id, "total_targets": len(targets)}


@router.get("/status/{task_id}")
async def get_status(task_id: int, user: dict = Depends(get_current_user)):
    task = await get_broadcast_task(db.pool, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check permission
    from config import settings

    if task["owner_id"] != user["id"] and user["id"] != settings.OWNER_ID:
        raise HTTPException(status_code=403, detail="Permission denied")

    return task


@router.get("/bot/{bot_id}")
async def get_bot_history(bot_id: int, user: dict = Depends(get_current_user)):
    # Check permission
    bot = await get_bot_by_id(db.pool, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    from config import settings

    if bot["owner_user_id"] != user["id"] and user["id"] != settings.OWNER_ID:
        raise HTTPException(status_code=403, detail="Permission denied")

    history = await get_bot_broadcasts(db.pool, bot_id)
    return history


@router.post("/global")
async def start_global_broadcast(
    target_type: str = Body(...),  # 'pms', 'groups', 'all'
    content: str = Body(...),
    media_file_id: Optional[str] = Body(None),
    media_type: Optional[str] = Body(None),
    include_clones: bool = Body(False),
    user: dict = Depends(get_current_user),
):
    """Main owner only: broadcast to everything."""
    from config import settings

    if user["id"] != settings.OWNER_ID:
        raise HTTPException(status_code=403, detail="Only main bot owner can do this")

    async with db.pool.acquire() as conn:
        primary_bot = await conn.fetchrow("SELECT bot_id FROM bots WHERE is_primary = TRUE")

        tasks = []
        if primary_bot:
            targets = await get_broadcast_targets(db.pool, primary_bot["bot_id"], target_type)
            if targets:
                tid = await create_broadcast_task(
                    db.pool,
                    {
                        "owner_id": user["id"],
                        "bot_id": primary_bot["bot_id"],
                        "target_type": target_type,
                        "content": content,
                        "media_file_id": media_file_id,
                        "media_type": media_type,
                        "total_targets": len(targets),
                    },
                )
                tasks.append({"bot_id": primary_bot["bot_id"], "task_id": tid})

        if include_clones:
            clones = await conn.fetch(
                "SELECT bot_id FROM bots WHERE is_primary = FALSE AND status = 'active'"
            )
            for clone in clones:
                targets = await get_broadcast_targets(db.pool, clone["bot_id"], target_type)
                if targets:
                    tid = await create_broadcast_task(
                        db.pool,
                        {
                            "owner_id": user["id"],
                            "bot_id": clone["bot_id"],
                            "target_type": target_type,
                            "content": content,
                            "media_file_id": media_file_id,
                            "media_type": media_type,
                            "total_targets": len(targets),
                        },
                    )
                    tasks.append({"bot_id": clone["bot_id"], "task_id": tid})

    return {"tasks": tasks}
