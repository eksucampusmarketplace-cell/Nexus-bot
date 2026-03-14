"""
api/routes/log_channel.py

GET  /api/groups/{chat_id}/log/settings
     → log channel id + category toggles

PUT  /api/groups/{chat_id}/log/settings
     → update log channel settings + category toggles

GET  /api/groups/{chat_id}/log/activity
     → paginated activity log

GET  /api/groups/{chat_id}/log/activity/export
     → download activity log as CSV
"""

import csv
import io
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from db.client import db as _db

log = logging.getLogger("log_api")
router = APIRouter()


def _get_pool(request: Request):
    """Return DB pool from app.state or fall back to module-level db."""
    try:
        pool = request.app.state.db
        if pool is not None:
            return pool
    except AttributeError:
        pass
    return _db.pool


@router.get("/api/groups/{chat_id}/log/settings")
async def get_log_settings(chat_id: int, request: Request):
    pool = _get_pool(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT log_channel_id, log_categories,
                      log_include_preview, log_include_userid,
                      inline_mode_enabled
               FROM groups WHERE chat_id=$1""",
            chat_id,
        )
    if not row:
        return {
            "log_channel_id": None,
            "log_categories": {},
            "log_include_preview": True,
            "log_include_userid": True,
            "inline_mode_enabled": False,
        }
    data = dict(row)
    cats = data.get("log_categories")
    if cats and not isinstance(cats, dict):
        try:
            data["log_categories"] = json.loads(cats)
        except Exception:
            data["log_categories"] = {}
    elif cats is None:
        data["log_categories"] = {}
    return data


@router.put("/api/groups/{chat_id}/log/settings")
async def update_log_settings(chat_id: int, request: Request):
    pool = _get_pool(request)
    body = await request.json()

    from db.ops.automod import update_group_setting

    if "log_channel_id" in body:
        await update_group_setting(pool, chat_id, "log_channel_id", body["log_channel_id"])
    if "log_include_preview" in body:
        await update_group_setting(
            pool, chat_id, "log_include_preview", body["log_include_preview"]
        )
    if "log_include_userid" in body:
        await update_group_setting(pool, chat_id, "log_include_userid", body["log_include_userid"])
    if "inline_mode_enabled" in body:
        await update_group_setting(
            pool, chat_id, "inline_mode_enabled", body["inline_mode_enabled"]
        )

    if "log_categories" in body:
        async with pool.acquire() as conn:
            current = await conn.fetchval(
                "SELECT log_categories FROM groups WHERE chat_id=$1", chat_id
            )
        if current:
            if isinstance(current, str):
                try:
                    current_dict = json.loads(current)
                except Exception:
                    current_dict = {}
            else:
                current_dict = dict(current)
        else:
            current_dict = {}
        current_dict.update(body["log_categories"])
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE groups SET log_categories=$1::jsonb WHERE chat_id=$2",
                json.dumps(current_dict),
                chat_id,
            )

    return {"ok": True}


@router.get("/api/groups/{chat_id}/log/activity")
async def get_activity_log(
    chat_id: int,
    request: Request,
    type: str = None,
    limit: int = 50,
    offset: int = 0,
    target_id: int = None,
    days: int = 30,
):
    pool = _get_pool(request)

    conditions = ["chat_id=$1", "created_at > NOW() - INTERVAL '1 day' * $2"]
    params = [chat_id, days]
    i = 3

    if type:
        conditions.append(f"event_type=${i}")
        params.append(type)
        i += 1

    if target_id:
        conditions.append(f"target_id=${i}")
        params.append(target_id)
        i += 1

    where = " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT * FROM activity_log
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ${i} OFFSET ${i+1}""",
            *params,
            limit,
            offset,
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM activity_log WHERE {where}", *params)

    def _row(r):
        d = dict(r)
        details = d.get("details")
        if details and not isinstance(details, dict):
            try:
                d["details"] = json.loads(details)
            except Exception:
                d["details"] = {}
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        return d

    return {
        "rows": [_row(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/groups/{chat_id}/log/activity/export")
async def export_activity_log(
    chat_id: int,
    request: Request,
    days: int = 7,
    type: str = "all",
):
    pool = _get_pool(request)

    conditions = ["chat_id=$1", "created_at > NOW() - INTERVAL '1 day' * $2"]
    params = [chat_id, days]

    if type and type != "all":
        conditions.append("event_type=$3")
        params.append(type)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT created_at, event_type, actor_name, target_name,
                       details
                FROM activity_log
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT 10000""",
            *params,
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "event_type", "actor", "target", "details"])
    for row in rows:
        details = row["details"]
        if details and not isinstance(details, dict):
            try:
                details = json.loads(details)
            except Exception:
                details = {}
        writer.writerow(
            [
                row["created_at"].isoformat(),
                row["event_type"],
                row["actor_name"] or "",
                row["target_name"] or "",
                json.dumps(details if details else {}),
            ]
        )

    output.seek(0)
    filename = f"nexus_log_{chat_id}_" f"{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
