"""
api/routes/analytics_dashboard.py

Richer Analytics Dashboard — unified endpoint returning
message trends, active hours heatmap, growth charts, and top modules.

GET /api/groups/{chat_id}/analytics/dashboard?days=30

Returns:
  - message_trends: daily message counts with 7-day moving average
  - active_hours: 24-hour activity distribution
  - growth_chart: daily joins/leaves/net with running total
  - top_chatters: most active users this period
  - moderation_summary: warns, bans, mutes breakdown
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from api.auth import get_current_user
from db.client import db

log = logging.getLogger("analytics_dashboard")

router = APIRouter(prefix="/api/groups")


@router.get("/{chat_id}/analytics/dashboard")
async def analytics_dashboard(
    chat_id: int,
    days: int = Query(default=30, ge=7, le=90),
    user: dict = Depends(get_current_user),
):
    """Unified analytics dashboard endpoint."""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    async with db.pool.acquire() as conn:
        # ── Message Trends ────────────────────────────────────────────
        daily_rows = await conn.fetch(
            """SELECT day as date, message_count as messages,
                      spam_detected, warns_issued, bans_issued
               FROM bot_stats_daily
               WHERE chat_id = $1 AND day >= $2
               ORDER BY day ASC""",
            chat_id,
            start_date.date(),
        )

        # Fallback to hourly if no daily data
        if not daily_rows:
            daily_rows = await conn.fetch(
                """SELECT DATE(hour) as date,
                          SUM(message_count) as messages,
                          SUM(spam_detected) as spam_detected,
                          0 as warns_issued, 0 as bans_issued
                   FROM bot_stats_hourly
                   WHERE chat_id = $1 AND hour >= $2
                   GROUP BY DATE(hour)
                   ORDER BY date ASC""",
                chat_id,
                start_date,
            )

        # Build message trends with 7-day moving average
        msg_map = {}
        for r in daily_rows:
            msg_map[str(r["date"])] = {
                "messages": r["messages"] or 0,
                "spam": r["spam_detected"] or 0,
            }

        message_trends = []
        message_values = []
        for i in range(days):
            date_str = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            day_data = msg_map.get(date_str, {"messages": 0, "spam": 0})
            message_values.append(day_data["messages"])

            # 7-day moving average
            window = message_values[-7:]
            avg_7d = sum(window) / len(window) if window else 0

            message_trends.append(
                {
                    "date": date_str,
                    "messages": day_data["messages"],
                    "spam": day_data["spam"],
                    "avg_7d": round(avg_7d, 1),
                }
            )

        # ── Active Hours ──────────────────────────────────────────────
        hour_rows = await conn.fetch(
            """SELECT EXTRACT(HOUR FROM hour) as hr,
                      SUM(message_count) as total
               FROM bot_stats_hourly
               WHERE chat_id = $1 AND hour >= $2
               GROUP BY hr
               ORDER BY hr""",
            chat_id,
            start_date,
        )

        active_hours = [0] * 24
        for r in hour_rows:
            active_hours[int(r["hr"])] = int(r["total"] or 0)

        peak_hour = active_hours.index(max(active_hours)) if any(active_hours) else 0
        total_messages = sum(active_hours)

        # ── Growth Chart ──────────────────────────────────────────────
        group_row = await conn.fetchrow(
            "SELECT member_count FROM groups WHERE chat_id = $1", chat_id
        )
        current_members = group_row["member_count"] if group_row else 0

        events_rows = await conn.fetch(
            """SELECT DATE(created_at) as date, event_type, COUNT(*) as count
               FROM member_events
               WHERE chat_id = $1 AND created_at >= $2
               GROUP BY DATE(created_at), event_type
               ORDER BY date""",
            chat_id,
            start_date,
        )

        events_map = {}
        for r in events_rows:
            ds = str(r["date"])
            if ds not in events_map:
                events_map[ds] = {"joins": 0, "leaves": 0}
            if r["event_type"] in ("join", "captcha_pass", "approve"):
                events_map[ds]["joins"] += r["count"]
            elif r["event_type"] in ("leave", "kick", "ban"):
                events_map[ds]["leaves"] += r["count"]

        growth_chart = []
        running = current_members
        for i in range(days - 1, -1, -1):
            date_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            ev = events_map.get(date_str, {"joins": 0, "leaves": 0})
            net = ev["joins"] - ev["leaves"]
            growth_chart.append(
                {
                    "date": date_str,
                    "joins": ev["joins"],
                    "leaves": ev["leaves"],
                    "net": net,
                    "total": max(0, running),
                }
            )
            running -= net

        growth_chart.reverse()

        # ── Top Chatters ──────────────────────────────────────────────
        top_chatters = await conn.fetch(
            """SELECT user_id, username, first_name, message_count
               FROM users
               WHERE chat_id = $1 AND message_count > 0
               ORDER BY message_count DESC
               LIMIT 5""",
            chat_id,
        )

        # ── Moderation Summary ────────────────────────────────────────
        mod_rows = await conn.fetch(
            """SELECT action, COUNT(*) as count
               FROM actions_log
               WHERE chat_id = $1 AND timestamp >= $2
               GROUP BY action""",
            chat_id,
            start_date,
        )

        mod_summary = {}
        for r in mod_rows:
            mod_summary[r["action"]] = r["count"]

    return {
        "message_trends": message_trends,
        "active_hours": active_hours,
        "peak_hour": peak_hour,
        "total_messages": total_messages,
        "growth_chart": growth_chart,
        "current_members": current_members,
        "top_chatters": [dict(r) for r in top_chatters],
        "moderation_summary": mod_summary,
    }
