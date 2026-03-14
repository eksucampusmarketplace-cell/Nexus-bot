from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from api.auth import get_current_user
from db.client import db
from datetime import datetime, timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/groups")

# Rate limiter instance - will be set by main app
limiter = Limiter(key_func=get_remote_address)


def _compact_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to MMDD to save bandwidth."""
    if date_str and len(date_str) >= 10:
        return date_str[5:7] + date_str[8:10]  # MM-DD -> MMDD
    return date_str


def _minify_response(data: dict) -> dict:
    """Remove null values and empty arrays to reduce payload size."""
    if isinstance(data, dict):
        return {k: _minify_response(v) for k, v in data.items() 
                if v is not None and v != [] and v != {}}
    if isinstance(data, list):
        return [_minify_response(item) for item in data]
    return data

@router.get("/{chat_id}/analytics")
@limiter.limit("30/minute")  # Limit analytics requests to 30 per minute per IP
async def group_analytics(request: Request, chat_id: int, user: dict = Depends(get_current_user)):
    async with db.pool.acquire() as conn:
        # Get current member count from groups table
        group_row = await conn.fetchrow(
            "SELECT member_count FROM groups WHERE chat_id = $1", chat_id
        )
        current_members = group_row["member_count"] if group_row else 0

        # Get date range (last 30 days)
        now = datetime.now()
        start_date = now - timedelta(days=29)

        # Activity: Aggregate message_count by join date from users table
        activity_rows = await conn.fetch("""
            SELECT DATE(join_date) as date, SUM(message_count) as messages
            FROM users
            WHERE chat_id = $1 AND join_date >= $2
            GROUP BY DATE(join_date)
            ORDER BY date
        """, chat_id, start_date)

        # Create activity map for quick lookup
        activity_map = {str(row["date"]): row["messages"] or 0 for row in activity_rows}

        # Build activity array for last 30 days
        activity = []
        for i in range(30):
            date = (now - timedelta(days=29-i)).strftime("%Y-%m-%d")
            messages = activity_map.get(date, 0)
            activity.append({"date": date, "messages": messages})

        # Member Growth: Get join/leave events from member_events table
        events_rows = await conn.fetch("""
            SELECT DATE(created_at) as date, event_type, COUNT(*) as count
            FROM member_events
            WHERE chat_id = $1 AND created_at >= $2
            GROUP BY DATE(created_at), event_type
            ORDER BY date
        """, chat_id, start_date)

        # Build events map
        events_map = {}
        for row in events_rows:
            date_str = str(row["date"])
            if date_str not in events_map:
                events_map[date_str] = {"joins": 0, "leaves": 0}
            if row["event_type"] in ("join", "captcha_pass", "approve"):
                events_map[date_str]["joins"] += row["count"]
            elif row["event_type"] in ("leave", "kick", "ban"):
                events_map[date_str]["leaves"] += row["count"]

        # Build growth array (backwards to calculate running total)
        growth = []
        running_total = current_members
        for i in range(29, -1, -1):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            day_events = events_map.get(date, {"joins": 0, "leaves": 0})
            # For historical data, we work backwards from current count
            # This is an approximation - in a perfect world we'd track daily snapshots
            joins = day_events["joins"]
            leaves = day_events["leaves"]
            growth.append({
                "date": date,
                "joins": joins,
                "leaves": leaves,
                "total": max(0, running_total)
            })
            running_total -= (joins - leaves)

        # Reverse to get chronological order
        growth.reverse()

        # Module Activity: Get action counts from actions_log table
        module_rows = await conn.fetch("""
            SELECT action, COUNT(*) as count
            FROM actions_log
            WHERE chat_id = $1 AND timestamp >= $2
            GROUP BY action
        """, chat_id, start_date)

        # Map actions to module names
        action_to_module = {
            "warn": "warn_system",
            "ban": "moderation",
            "unban": "moderation",
            "mute": "moderation",
            "unmute": "moderation",
            "kick": "moderation",
            "purge": "moderation",
        }

        module_counts = {}
        for row in module_rows:
            action = row["action"]
            module = action_to_module.get(action, action)
            module_counts[module] = module_counts.get(module, 0) + row["count"]

        # Format modules for response (top 5)
        modules = [
            {"name": name, "actions": count}
            for name, count in sorted(module_counts.items(), key=lambda x: -x[1])[:5]
        ]

        # Add default modules if none found
        if not modules:
            modules = [{"name": "no_activity", "actions": 0}]

    # Minify and compact response to reduce bandwidth
    response_data = _minify_response({
        "activity": [{"d": _compact_date(a["date"]), "m": a["messages"]} for a in activity],
        "growth": [{"d": _compact_date(g["date"]), "j": g["joins"], "l": g["leaves"]} for g in growth],
        "modules": modules
    })
    
    return JSONResponse(
        content=response_data,
        headers={"Content-Encoding": "identity"}  # Allow gzip if configured
    )

@router.get("/{chat_id}/analytics/heatmap")
@limiter.limit("20/minute")  # Limit heatmap requests to 20 per minute per IP
async def sentiment_heatmap(request: Request, chat_id: int, user: dict = Depends(get_current_user)):
    async with db.pool.acquire() as conn:
        # Get activity by day/hour from member_events
        heatmap_rows = await conn.fetch("""
            SELECT EXTRACT(DOW FROM created_at) as day,
                   EXTRACT(HOUR FROM created_at) as hour,
                   COUNT(*) as count
            FROM member_events
            WHERE chat_id = $1 AND created_at >= NOW() - INTERVAL '7 days'
            GROUP BY EXTRACT(DOW FROM created_at), EXTRACT(HOUR FROM created_at)
        """, chat_id)

        # Create lookup map
        heatmap_map = {}
        for row in heatmap_rows:
            day = int(row["day"])
            hour = int(row["hour"])
            heatmap_map[(day, hour)] = row["count"]

        # Build 7x24 grid
        heatmap = []
        for day in range(7):
            for hour in range(24):
                count = heatmap_map.get((day, hour), 0)
                heatmap.append({
                    "day": day,
                    "hour": hour,
                    "count": count,
                    "sentiment": 0  # Neutral sentiment (not tracked yet)
                })

    return heatmap


@router.get("/{chat_id}/member-stats")
@limiter.limit("30/minute")  # Limit member stats requests to 30 per minute per IP
async def member_stats(
    request: Request,
    chat_id: int,
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """Return top members by message count along with trust score stats.
    
    Optimized for bandwidth: returns compact field names and excludes nulls.
    """
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT user_id, username, first_name,
                      message_count, trust_score,
                      COALESCE(report_count, 0) AS report_count,
                      COALESCE(array_length(CASE
                          WHEN warns::text = '[]' OR warns IS NULL THEN ARRAY[]::text[]
                          ELSE ARRAY(SELECT jsonb_array_elements_text(warns))
                      END, 1), 0) AS warn_count
               FROM users
               WHERE chat_id = $1 AND message_count > 0
               ORDER BY message_count DESC
               LIMIT $2""",
            chat_id, limit
        )

        total_members = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE chat_id = $1", chat_id
        ) or 0

        avg_trust = await conn.fetchval(
            "SELECT AVG(trust_score) FROM users WHERE chat_id = $1", chat_id
        ) or 50.0

        low_trust_count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE chat_id = $1 AND trust_score <= 30", chat_id
        ) or 0

    # Compact field names to reduce payload size
    compact_members = []
    for r in rows:
        member = {
            "id": r["user_id"],
            "u": r["username"],
            "n": r["first_name"],
            "mc": r["message_count"],
            "ts": r["trust_score"],
            "rc": r["report_count"],
            "wc": r["warn_count"],
        }
        # Remove null values
        compact_members.append({k: v for k, v in member.items() if v is not None})

    return JSONResponse(content={
        "tm": compact_members,  # top_members
        "s": {  # summary
            "tt": total_members,  # total_tracked
            "at": round(float(avg_trust), 1),  # avg_trust
            "lt": low_trust_count,  # low_trust_count
        },
    })
