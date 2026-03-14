"""
api/routes/scheduler.py

GET  /api/groups/{chat_id}/scheduled
     → list all scheduled messages

POST /api/groups/{chat_id}/scheduled
     → create scheduled message

PUT  /api/groups/{chat_id}/scheduled/{id}
     → update scheduled message

DELETE /api/groups/{chat_id}/scheduled/{id}
     → delete/deactivate

POST /api/groups/{chat_id}/scheduled/{id}/pause
     → toggle is_active

GET  /api/groups/{chat_id}/reports
     → list reports (admin only)

PUT  /api/groups/{chat_id}/reports/{id}
     → update report status
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException

from bot.scheduler.engine import _calc_next_send

log = logging.getLogger("scheduler_api")
router = APIRouter()


@router.get("/api/groups/{chat_id}/scheduled")
async def list_scheduled(chat_id: int, request: Request):
    db = request.app.state.db
    rows = await db.fetch(
        """SELECT * FROM scheduled_messages
           WHERE chat_id=$1
           ORDER BY next_send_at ASC NULLS LAST""",
        chat_id,
    )
    return [dict(r) for r in rows]


@router.post("/api/groups/{chat_id}/scheduled")
async def create_scheduled(chat_id: int, request: Request):
    db = request.app.state.db
    body = await request.json()

    stype = body.get("schedule_type")
    if stype not in ("once", "interval", "daily", "weekly", "cron"):
        raise HTTPException(status_code=400, detail="Invalid schedule_type")

    time_of_day = None
    if body.get("time_of_day"):
        from datetime import time

        parts = body["time_of_day"].split(":")
        time_of_day = time(int(parts[0]), int(parts[1]))

    scheduled_at = None
    if body.get("scheduled_at"):
        scheduled_at = datetime.fromisoformat(body["scheduled_at"].replace("Z", "+00:00"))

    mock_msg = {
        "schedule_type": stype,
        "interval_mins": body.get("interval_mins", 60),
        "time_of_day": time_of_day,
        "days_of_week": body.get("days_of_week", []),
        "cron_expr": body.get("cron_expr"),
        "timezone": body.get("timezone", "UTC"),
        "scheduled_at": scheduled_at,
    }
    next_send = scheduled_at if stype == "once" else _calc_next_send(mock_msg)

    user_id = getattr(request.state, "user_id", None)

    row = await db.fetchrow(
        """INSERT INTO scheduled_messages
           (chat_id, content, media_type, media_file_id,
            schedule_type, scheduled_at, interval_mins,
            cron_expr, days_of_week, time_of_day, timezone,
            max_sends, pin_after_send, next_send_at, created_by)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
           RETURNING id""",
        chat_id,
        body.get("content", ""),
        body.get("media_type"),
        body.get("media_file_id"),
        stype,
        scheduled_at,
        body.get("interval_mins"),
        body.get("cron_expr"),
        body.get("days_of_week"),
        time_of_day,
        body.get("timezone", "UTC"),
        body.get("max_sends", 0),
        body.get("pin_after_send", False),
        next_send,
        user_id,
    )
    return {"ok": True, "id": row["id"]}


@router.put("/api/groups/{chat_id}/scheduled/{msg_id}")
async def update_scheduled(chat_id: int, msg_id: int, request: Request):
    db = request.app.state.db
    body = await request.json()

    allowed = {
        "content",
        "max_sends",
        "pin_after_send",
        "interval_mins",
        "cron_expr",
        "days_of_week",
        "time_of_day",
        "timezone",
        "is_active",
    }
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    set_clauses = ", ".join(f"{k}=${i+3}" for i, k in enumerate(updates.keys()))
    values = [msg_id, chat_id] + list(updates.values())

    await db.execute(
        f"UPDATE scheduled_messages SET {set_clauses} WHERE id=$1 AND chat_id=$2", *values
    )
    return {"ok": True}


@router.delete("/api/groups/{chat_id}/scheduled/{msg_id}")
async def delete_scheduled(chat_id: int, msg_id: int, request: Request):
    db = request.app.state.db
    await db.execute(
        "UPDATE scheduled_messages SET is_active=FALSE WHERE id=$1 AND chat_id=$2", msg_id, chat_id
    )
    return {"ok": True}


@router.post("/api/groups/{chat_id}/scheduled/{msg_id}/pause")
async def pause_scheduled(chat_id: int, msg_id: int, request: Request):
    db = request.app.state.db
    row = await db.fetchrow(
        "SELECT is_active FROM scheduled_messages WHERE id=$1 AND chat_id=$2", msg_id, chat_id
    )
    if not row:
        raise HTTPException(status_code=404)
    await db.execute(
        "UPDATE scheduled_messages SET is_active=$1 WHERE id=$2", not row["is_active"], msg_id
    )
    return {"ok": True, "is_active": not row["is_active"]}


@router.get("/api/groups/{chat_id}/reports")
async def list_reports(chat_id: int, request: Request):
    db = request.app.state.db
    rows = await db.fetch(
        """SELECT * FROM reports WHERE chat_id=$1
           ORDER BY created_at DESC LIMIT 50""",
        chat_id,
    )
    return [dict(r) for r in rows]


@router.put("/api/groups/{chat_id}/reports/{report_id}")
async def update_report(chat_id: int, report_id: int, request: Request):
    db = request.app.state.db
    body = await request.json()
    status = body.get("status")

    if status not in ("reviewed", "dismissed"):
        raise HTTPException(status_code=400, detail="Invalid status")

    user_id = getattr(request.state, "user_id", None)

    await db.execute(
        """UPDATE reports SET status=$1, reviewed_by=$2
           WHERE id=$3 AND chat_id=$4""",
        status,
        user_id,
        report_id,
        chat_id,
    )
    return {"ok": True}
