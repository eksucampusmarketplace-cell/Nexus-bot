from fastapi import APIRouter, Depends, HTTPException, Query
from api.auth import get_current_user
from db.client import db
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/groups")


@router.get("/{chat_id}/analytics")
async def group_analytics(chat_id: int, days: int = Query(default=30, ge=7, le=90), user: dict = Depends(get_current_user)):
    async with db.pool.acquire() as conn:
        group_row = await conn.fetchrow(
            "SELECT member_count FROM groups WHERE chat_id = $1", chat_id
        )
        current_members = group_row["member_count"] if group_row else 0

        now = datetime.now()
        start_date = now - timedelta(days=days - 1)

        activity_rows = await conn.fetch(
            """
            SELECT DATE(join_date) as date, SUM(message_count) as messages
            FROM users
            WHERE chat_id = $1 AND join_date >= $2
            GROUP BY DATE(join_date)
            ORDER BY date
        """,
            chat_id,
            start_date,
        )

        activity_map = {str(row["date"]): row["messages"] or 0 for row in activity_rows}

        activity = []
        for i in range(days):
            date = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            messages = activity_map.get(date, 0)
            activity.append({"date": date, "messages": messages})

        # Member Growth: Get join/leave events from member_events table
        events_rows = await conn.fetch(
            """
            SELECT DATE(created_at) as date, event_type, COUNT(*) as count
            FROM member_events
            WHERE chat_id = $1 AND created_at >= $2
            GROUP BY DATE(created_at), event_type
            ORDER BY date
        """,
            chat_id,
            start_date,
        )

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

        growth = []
        running_total = current_members
        for i in range(days - 1, -1, -1):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            day_events = events_map.get(date, {"joins": 0, "leaves": 0})
            joins = day_events["joins"]
            leaves = day_events["leaves"]
            growth.append(
                {"date": date, "joins": joins, "leaves": leaves, "total": max(0, running_total)}
            )
            running_total -= joins - leaves

        growth.reverse()

        # Module Activity: Get action counts from actions_log table
        module_rows = await conn.fetch(
            """
            SELECT action, COUNT(*) as count
            FROM actions_log
            WHERE chat_id = $1 AND timestamp >= $2
            GROUP BY action
        """,
            chat_id,
            start_date,
        )

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

        hour_rows = await conn.fetch(
            """
            SELECT EXTRACT(hour FROM created_at) as hour,
                   COUNT(*) as count
            FROM member_events
            WHERE chat_id = $1 AND created_at >= $2
            GROUP BY EXTRACT(hour FROM created_at)
        """,
            chat_id,
            start_date,
        )

        peak_hours = [0] * 24
        for row in hour_rows:
            peak_hours[int(row["hour"])] = row["count"]

    return {"activity": activity, "growth": growth, "modules": modules, "peak_hours": peak_hours}


@router.get("/{chat_id}/analytics/heatmap")
async def sentiment_heatmap(chat_id: int, user: dict = Depends(get_current_user)):
    async with db.pool.acquire() as conn:
        # Get activity by day/hour from member_events
        heatmap_rows = await conn.fetch(
            """
            SELECT EXTRACT(DOW FROM created_at) as day,
                   EXTRACT(HOUR FROM created_at) as hour,
                   COUNT(*) as count
            FROM member_events
            WHERE chat_id = $1 AND created_at >= NOW() - INTERVAL '7 days'
            GROUP BY EXTRACT(DOW FROM created_at), EXTRACT(HOUR FROM created_at)
        """,
            chat_id,
        )

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
                heatmap.append(
                    {
                        "day": day,
                        "hour": hour,
                        "count": count,
                        "sentiment": 0,  # Neutral sentiment (not tracked yet)
                    }
                )

    return heatmap


@router.get("/{chat_id}/member-stats")
async def member_stats(
    chat_id: int,
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """Return top members by message count along with trust score stats."""
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
            chat_id,
            limit,
        )

        total_members = (
            await conn.fetchval("SELECT COUNT(*) FROM users WHERE chat_id = $1", chat_id) or 0
        )

        avg_trust = (
            await conn.fetchval("SELECT AVG(trust_score) FROM users WHERE chat_id = $1", chat_id)
            or 50.0
        )

        low_trust_count = (
            await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE chat_id = $1 AND trust_score <= 30", chat_id
            )
            or 0
        )

    return {
        "top_members": [dict(r) for r in rows],
        "summary": {
            "total_tracked": total_members,
            "avg_trust_score": round(float(avg_trust), 1),
            "low_trust_count": low_trust_count,
        },
    }
