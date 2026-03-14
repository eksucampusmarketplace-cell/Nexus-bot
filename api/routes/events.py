"""
api/routes/events.py

GET /api/events?chat_id={id}&token={initData}

Server-Sent Events endpoint.
Streams real-time events to connected Mini App clients.

Events pushed:
  member_join         → when new member joins group
  member_leave        → when member leaves or is removed
  bot_action          → ban/mute/warn/kick/unban
  settings_change     → any setting toggled
  stat_update         → member count / message count changes
  notification        → billing, expiry, system alerts
  bulk_action         → bulk operation completed

Uses asyncio.Queue per connection.
Bot handlers push events via EventBus.publish().

Logs prefix: [SSE]
"""

import asyncio
import json
import logging
from datetime import timezone, datetime

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from config import settings

log = logging.getLogger("sse")
router = APIRouter()


class EventBus:
    """
    Global event bus.
    Bot handlers call EventBus.publish(chat_id, event_type, data).
    SSE connections for that chat_id receive the event.
    """

    _connections: dict[int, list[asyncio.Queue]] = {}

    @classmethod
    def subscribe(cls, chat_id: int) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        if chat_id not in cls._connections:
            cls._connections[chat_id] = []
        cls._connections[chat_id].append(q)
        log.debug(f"[SSE] Subscribe | chat={chat_id} total={len(cls._connections[chat_id])}")
        return q

    @classmethod
    def unsubscribe(cls, chat_id: int, queue: asyncio.Queue):
        if chat_id in cls._connections:
            cls._connections[chat_id] = [q for q in cls._connections[chat_id] if q is not queue]
        log.debug(f"[SSE] Unsubscribe | chat={chat_id}")

    @classmethod
    async def publish(cls, chat_id: int, event_type: str, data: dict):
        if chat_id not in cls._connections:
            return
        payload = json.dumps(
            {"type": event_type, "data": data, "ts": datetime.now(timezone.utc).isoformat()}
        )
        dead = []
        for q in cls._connections[chat_id]:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            cls.unsubscribe(chat_id, q)


def push_event(owner_id: int, data: dict):
    """
    Push event to the bot owner's live feed.
    Broadcasts to the relevant chat_id.
    """
    chat_id = data.get("chat_id")
    if chat_id:
        import asyncio

        asyncio.create_task(EventBus.publish(chat_id, data.get("type", "notification"), data))


@router.get("/api/events")
async def sse_events(request: Request, chat_id: int, token: str = ""):
    """SSE stream for a specific chat_id."""
    # Validate token
    from api.auth import validate_init_data

    if not settings.SKIP_AUTH:
        user_data = None
        # Try primary bot first
        try:
            user_data = validate_init_data(token, settings.PRIMARY_BOT_TOKEN)
        except Exception:
            # Try clones
            from bot.registry import get_all

            registered_bots = get_all()
            for bot_id, bot_app in registered_bots.items():
                try:
                    bot_token = bot_app.bot.token
                    if bot_token == settings.PRIMARY_BOT_TOKEN:
                        continue
                    user_data = validate_init_data(token, bot_token)
                    if user_data:
                        break
                except Exception:
                    continue

        if not user_data:
            return StreamingResponse(
                iter([f"event: error\ndata: {json.dumps({'error':'unauthorized'})}\n\n"]),
                media_type="text/event-stream",
            )

        user_id = user_data["user"].get("id")

    queue = EventBus.subscribe(chat_id)
    log.info(f"[SSE] Connection opened | chat={chat_id}")

    async def stream():
        try:
            # Send initial heartbeat
            yield f"data: {json.dumps({'type':'connected','data':{}})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=25)
                    event_data = json.loads(payload)
                    yield f"event: {event_data['type']}\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive ping every 25s
                    yield f"event: ping\ndata: {{}}\n\n"
        except Exception as e:
            log.warning(f"[SSE] Stream error | chat={chat_id} error={e}")
        finally:
            EventBus.unsubscribe(chat_id, queue)
            log.info(f"[SSE] Connection closed | chat={chat_id}")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
