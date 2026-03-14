from fastapi import APIRouter, Depends, HTTPException, Body
from api.auth import get_current_user
from db.ops.channels import get_linked_channel, link_channel, unlink_channel, get_channel_posts
from bot.registry import get as registry_get
from bot.handlers.channel import send_to_channel
from datetime import datetime, timezone

router = APIRouter(prefix="/api/channels")


@router.get("/{group_chat_id}")
async def linked_channel_info(group_chat_id: int, user: dict = Depends(get_current_user)):
    info = await get_linked_channel(group_chat_id)
    if not info:
        return {"linked": False}
    return {**info, "linked": True}


@router.post("/{group_chat_id}/link")
async def link_channel_route(
    group_chat_id: int, body: dict, user: dict = Depends(get_current_user)
):
    channel_id = body.get("channel_id")
    channel_username = body.get("channel_username")
    channel_title = body.get("channel_title")
    bot_id = body.get("bot_id")

    await link_channel(group_chat_id, channel_id, channel_username, channel_title, bot_id)
    return {"status": "ok"}


@router.delete("/{group_chat_id}/unlink")
async def unlink_channel_route(group_chat_id: int, user: dict = Depends(get_current_user)):
    await unlink_channel(group_chat_id)
    return {"status": "ok"}


@router.post("/{group_chat_id}/post")
async def immediate_post(group_chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    info = await get_linked_channel(group_chat_id)
    if not info:
        raise HTTPException(status_code=400, detail="Channel not linked")

    bot_app = registry_get(info["bot_id"])
    if not bot_app:
        raise HTTPException(status_code=500, detail="Bot not active")

    text = body.get("text")
    media_file_id = body.get("media_file_id")
    media_type = body.get("media_type")

    msg = await send_to_channel(bot_app.bot, info["channel_id"], text, media_file_id, media_type)

    # Save to history
    from db.client import db

    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO channel_posts (bot_id, channel_id, group_chat_id, text, status, sent_at, sent_message_id, created_by)
            VALUES ($1, $2, $3, $4, 'sent', $5, $6, $7)
        """,
            info["bot_id"],
            info["channel_id"],
            group_chat_id,
            text,
            datetime.now(timezone.utc),
            msg.message_id,
            user["id"],
        )

    return {"status": "ok", "message_id": msg.message_id}


@router.get("/{group_chat_id}/posts")
async def list_posts(group_chat_id: int, user: dict = Depends(get_current_user)):
    posts = await get_channel_posts(group_chat_id)
    return posts
