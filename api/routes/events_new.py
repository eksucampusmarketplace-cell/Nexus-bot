import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api.auth import get_current_user
from bot.handlers.moderation.utils import EventBus

log = logging.getLogger("sse")
router = APIRouter(prefix="/api/events")


@router.get("/{chat_id}")
@router.get("/moderation/{chat_id}")
async def moderation_events(chat_id: int, request: Request, user: dict = Depends(get_current_user)):
    """
    SSE endpoint for moderation events.
    Supports both /api/events/{chat_id} and /api/events/moderation/{chat_id} paths.
    Falls back to in-memory EventBus if Redis is unavailable.
    """
    redis = getattr(request.app.state, "redis", None)

    async def event_stream():
        if redis:
            # Use Redis pub/sub
            channel = f"nexus:events:{chat_id}"
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)

            try:
                yield f'data: {json.dumps({"type": "connected", "chat_id": chat_id})}\n\n'

                while True:
                    if await request.is_disconnected():
                        break

                    try:
                        message = await asyncio.wait_for(
                            pubsub.get_message(ignore_subscribe_messages=True), timeout=30.0
                        )

                        if message and message["type"] == "message":
                            yield f'data: {message["data"].decode()}\n\n'
                        else:
                            yield f'data: {json.dumps({"type": "heartbeat"})}\n\n'
                    except asyncio.TimeoutError:
                        yield f'data: {json.dumps({"type": "heartbeat"})}\n\n'

            except Exception as e:
                log.error(f"[SSE] Error: {e}")
                yield f'data: {json.dumps({"type": "error", "message": str(e)})}\n\n'
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
        else:
            # Fallback to in-memory EventBus
            yield f'data: {json.dumps({"type": "connected", "chat_id": chat_id, "mode": "memory"})}\n\n'
            
            # Create a queue for this connection
            queue = asyncio.Queue()
            
            async def handler(payload):
                await queue.put(payload)
            
            EventBus.subscribe(chat_id, handler)
            
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    
                    try:
                        payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f'data: {json.dumps(payload)}\n\n'
                    except asyncio.TimeoutError:
                        yield f'data: {json.dumps({"type": "heartbeat"})}\n\n'
            except Exception as e:
                log.error(f"[SSE] Memory mode error: {e}")
                yield f'data: {json.dumps({"type": "error", "message": str(e)})}\n\n'
            finally:
                EventBus.unsubscribe(chat_id, handler)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
