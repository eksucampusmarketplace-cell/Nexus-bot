from fastapi import APIRouter, Depends, HTTPException, Body
from api.auth import get_current_user
import json
from db.client import db

router = APIRouter(prefix="/api/groups")


@router.put("/{chat_id}/text-config")
async def update_text_config(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    # Verify user manages chat_id

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT text_config FROM groups WHERE chat_id = $1", chat_id)
        config = {}
        if row and row["text_config"]:
            config = row["text_config"]
            if isinstance(config, str):
                config = json.loads(config)

        # Merge new config
        config.update(body)

        await conn.execute(
            "UPDATE groups SET text_config = $1 WHERE chat_id = $2", json.dumps(config), chat_id
        )
    return {"status": "ok"}
