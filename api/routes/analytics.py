from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from db.client import db
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/groups")

@router.get("/{chat_id}/analytics")
async def group_analytics(chat_id: int, user: dict = Depends(get_current_user)):
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

    return {
        "activity": activity,
        "growth": growth,
        "modules": modules
    }

@router.get("/{chat_id}/analytics/heatmap")
async def sentiment_heatmap(chat_id: int, user: dict = Depends(get_current_user)):
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
