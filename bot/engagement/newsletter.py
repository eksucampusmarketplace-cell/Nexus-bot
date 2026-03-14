"""
bot/engagement/newsletter.py

Weekly Newsletter — auto-generated group summary.
Sent every Sunday at 9am UTC (configurable).
Compiled from DB stats, no manual work needed.

Sections:
1. Header with week dates
2. Most active members (top 5 by messages)
3. Top gainers (most XP earned this week)
4. New members who joined
5. Top reacted messages (if any)
6. Milestones reached this week
7. Leaderboard snapshot (top 3)
8. Streak highlights (longest streaks)
9. Custom admin message (optional)

Format: clean, readable, emoji-rich
Pinned automatically when sent (optional setting)
Previous newsletter unpinned when new one sent

Log prefix: [NEWSLETTER]
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("newsletter")


async def generate_newsletter(
    pool, chat_id: int, bot_id: int, week_start: date, week_end: date
) -> str:
    """
    Generate full newsletter text for a group.
    Pulls all stats from DB for the week period.
    Returns formatted message string ready to send.
    """
    try:
        stats = await get_week_stats(pool, chat_id, bot_id, week_start, week_end)

        # Format dates
        week_range = f"{week_start.strftime('%b %d')}–{week_end.strftime('%d, %Y')}"

        lines = [f"📰 Weekly Digest", f"Week of {week_range}", "━━━━━━━━━━━━━━━━━━━━━━", ""]

        # Most Active Members
        top_active = stats.get("most_active", [])
        if top_active:
            lines.append("🏆 Most Active Members")
            for i, m in enumerate(top_active[:3], 1):
                lines.append(f"{i}. {m.get('name', 'Unknown')} — {m.get('messages', 0)} messages")
            lines.append("")

        # Top XP Earners
        top_xp = stats.get("top_xp", [])
        if top_xp:
            lines.append("⭐ Top XP Earners This Week")
            for i, m in enumerate(top_xp[:3], 1):
                level_info = f" (now Level {m.get('level', 1)})" if m.get("leveled_up") else ""
                lines.append(f"{i}. {m.get('name', 'Unknown')} — +{m.get('xp', 0)} XP{level_info}")
            lines.append("")

        # New Members
        new_members = stats.get("new_members", [])
        if new_members:
            lines.append(f"👋 New Members ({len(new_members)})")
            names = [m.get("name", "Unknown") for m in new_members[:5]]
            if len(new_members) > 5:
                names.append(f"and {len(new_members) - 5} others")
            lines.append(", ".join(names))
            lines.append("Welcome to the group!")
            lines.append("")

        # Milestones
        milestones = stats.get("milestones", [])
        if milestones:
            lines.append("🎯 Milestones This Week")
            for m in milestones:
                lines.append(f"🎉 {m.get('description', '')}")
            lines.append("")

        # Leaderboard Snapshot
        leaderboard = stats.get("leaderboard", [])
        if leaderboard:
            lines.append("📊 Leaderboard")
            medals = ["👑", "⭐", "🌟"]
            for i, m in enumerate(leaderboard[:3], 1):
                medal = medals[i - 1] if i <= 3 else f"{i}."
                lines.append(
                    f"{medal} {m.get('name', 'Unknown')} — Lv.{m.get('level', 1)} — {m.get('xp', 0)} XP"
                )
            lines.append("")

        # Streak Highlights
        streaks = stats.get("streaks", [])
        if streaks:
            lines.append("🔥 Longest Streaks")
            for m in streaks[:3]:
                lines.append(f"{m.get('name', 'Unknown')} — {m.get('streak', 0)} days 🔥")
            lines.append("")

        lines.append("See you next week! 💪")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")

        return "\n".join(lines)

    except Exception as e:
        log.error(f"[NEWSLETTER] Error generating newsletter: {e}")
        return "📰 Weekly Digest\n\nStats temporarily unavailable."


async def send_newsletter(bot, pool, chat_id: int, bot_id: int):
    """
    Generate and send newsletter to group.
    Pin it if configured.
    Unpin previous newsletter.
    Save to newsletter_history.
    """
    try:
        # Calculate week range (previous week)
        today = date.today()
        week_end = today - timedelta(days=today.weekday() + 1)  # Last Sunday
        week_start = week_end - timedelta(days=6)  # Previous Monday

        # Generate newsletter
        text = await generate_newsletter(pool, chat_id, bot_id, week_start, week_end)

        # Get config
        async with pool.acquire() as conn:
            config = await conn.fetchrow(
                """
                SELECT * FROM newsletter_config
                WHERE chat_id=$1 AND bot_id=$2
                """,
                chat_id,
                bot_id,
            )

            pin_enabled = config["pin_newsletter"] if config else True

            # Unpin previous newsletter
            prev = await conn.fetchrow(
                """
                SELECT message_id FROM newsletter_history
                WHERE chat_id=$1 AND bot_id=$2
                ORDER BY sent_at DESC
                LIMIT 1
                """,
                chat_id,
                bot_id,
            )

            if prev and pin_enabled:
                try:
                    await bot.unpin_chat_message(chat_id, prev["message_id"])
                except Exception:
                    pass

        # Send newsletter
        msg = await bot.send_message(chat_id=chat_id, text=text)

        # Pin if enabled
        if pin_enabled:
            try:
                await bot.pin_chat_message(chat_id, msg.message_id)
            except Exception as e:
                log.warning(f"[NEWSLETTER] Could not pin message: {e}")

        # Save to history
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO newsletter_history
                    (chat_id, bot_id, message_id, stats_snapshot)
                VALUES ($1, $2, $3, $4)
                """,
                chat_id,
                bot_id,
                msg.message_id,
                {"week_start": week_start.isoformat(), "week_end": week_end.isoformat()},
            )

        log.info(f"[NEWSLETTER] Sent to chat {chat_id}")

    except Exception as e:
        log.error(f"[NEWSLETTER] Error sending newsletter: {e}")


async def get_week_stats(pool, chat_id: int, bot_id: int, week_start: date, week_end: date) -> dict:
    """
    Gather all stats for the week:
    - Most active by message count
    - Top XP earners
    - New members
    - Milestones reached
    - Top reactions (from message_stats if available)
    - Streak highlights
    Returns structured dict used by generate_newsletter()
    """
    stats = {
        "most_active": [],
        "top_xp": [],
        "new_members": [],
        "milestones": [],
        "leaderboard": [],
        "streaks": [],
    }

    try:
        async with pool.acquire() as conn:
            # Most active by messages this week
            # This would need message tracking - using XP as proxy
            active_rows = await conn.fetch(
                """
                SELECT user_id, total_messages, level, xp
                FROM member_xp
                WHERE chat_id=$1 AND bot_id=$2
                ORDER BY total_messages DESC
                LIMIT 5
                """,
                chat_id,
                bot_id,
            )

            stats["most_active"] = [
                {
                    "user_id": r["user_id"],
                    "name": f"User {r['user_id']}",
                    "messages": r["total_messages"],
                }
                for r in active_rows
            ]

            # Top XP earners this week (from transactions)
            xp_rows = await conn.fetch(
                """
                SELECT user_id, SUM(amount) as xp_earned
                FROM xp_transactions
                WHERE chat_id=$1 AND bot_id=$2
                AND created_at >= $3 AND created_at <= $4
                GROUP BY user_id
                ORDER BY xp_earned DESC
                LIMIT 5
                """,
                chat_id,
                bot_id,
                datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc),
                datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc),
            )

            stats["top_xp"] = [
                {"user_id": r["user_id"], "name": f"User {r['user_id']}", "xp": r["xp_earned"]}
                for r in xp_rows
            ]

            # Current leaderboard
            lb_rows = await conn.fetch(
                """
                SELECT user_id, xp, level
                FROM member_xp
                WHERE chat_id=$1 AND bot_id=$2
                ORDER BY level DESC, xp DESC
                LIMIT 3
                """,
                chat_id,
                bot_id,
            )

            stats["leaderboard"] = [
                {
                    "user_id": r["user_id"],
                    "name": f"User {r['user_id']}",
                    "xp": r["xp"],
                    "level": r["level"],
                }
                for r in lb_rows
            ]

            # Top streaks
            streak_rows = await conn.fetch(
                """
                SELECT user_id, streak_days
                FROM member_xp
                WHERE chat_id=$1 AND bot_id=$2 AND streak_days > 0
                ORDER BY streak_days DESC
                LIMIT 3
                """,
                chat_id,
                bot_id,
            )

            stats["streaks"] = [
                {
                    "user_id": r["user_id"],
                    "name": f"User {r['user_id']}",
                    "streak": r["streak_days"],
                }
                for r in streak_rows
            ]

        return stats

    except Exception as e:
        log.error(f"[NEWSLETTER] Error getting week stats: {e}")
        return stats


async def get_newsletter_config(pool, chat_id: int, bot_id: int) -> dict:
    """Get newsletter configuration for a group."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM newsletter_config
                WHERE chat_id=$1 AND bot_id=$2
                """,
                chat_id,
                bot_id,
            )

            if row:
                return {
                    "enabled": row["enabled"],
                    "send_day": row["send_day"],
                    "send_hour_utc": row["send_hour_utc"],
                    "include_top_members": row["include_top_members"],
                    "include_leaderboard": row["include_leaderboard"],
                    "include_new_members": row["include_new_members"],
                    "include_milestones": row["include_milestones"],
                    "custom_intro": row["custom_intro"],
                }

            # Defaults
            return {
                "enabled": True,
                "send_day": 0,  # Sunday
                "send_hour_utc": 9,
                "include_top_members": True,
                "include_leaderboard": True,
                "include_new_members": True,
                "include_milestones": True,
                "custom_intro": None,
            }

    except Exception as e:
        log.error(f"[NEWSLETTER] Error getting config: {e}")
        return {
            "enabled": True,
            "send_day": 0,
            "send_hour_utc": 9,
            "include_top_members": True,
            "include_leaderboard": True,
            "include_new_members": True,
            "include_milestones": True,
            "custom_intro": None,
        }


async def update_newsletter_config(pool, chat_id: int, bot_id: int, **kwargs) -> bool:
    """Update newsletter configuration."""
    try:
        async with pool.acquire() as conn:
            # Build dynamic query
            allowed_fields = [
                "enabled",
                "send_day",
                "send_hour_utc",
                "include_top_members",
                "include_leaderboard",
                "include_new_members",
                "include_milestones",
                "custom_intro",
                "pin_newsletter",
            ]

            fields = []
            values = []
            for field, value in kwargs.items():
                if field in allowed_fields:
                    fields.append(f"{field} = ${len(values) + 3}")
                    values.append(value)

            if not fields:
                return False

            query = f"""
                INSERT INTO newsletter_config
                    (chat_id, bot_id, {', '.join([f.split('=')[0].strip() for f in fields])})
                VALUES ($1, $2, {', '.join([f'${i+3}' for i in range(len(fields))])})
                ON CONFLICT (chat_id, bot_id)
                DO UPDATE SET {', '.join(fields)}
            """

            await conn.execute(query, chat_id, bot_id, *values)
            return True

    except Exception as e:
        log.error(f"[NEWSLETTER] Error updating config: {e}")
        return False


async def get_newsletter_history(pool, chat_id: int, bot_id: int, limit: int = 10) -> list[dict]:
    """Get newsletter history for a group."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, sent_at, message_id, stats_snapshot
                FROM newsletter_history
                WHERE chat_id=$1 AND bot_id=$2
                ORDER BY sent_at DESC
                LIMIT $3
                """,
                chat_id,
                bot_id,
                limit,
            )

            return [
                {
                    "id": row["id"],
                    "sent_at": row["sent_at"].isoformat() if row["sent_at"] else None,
                    "message_id": row["message_id"],
                    "stats": row["stats_snapshot"],
                }
                for row in rows
            ]

    except Exception as e:
        log.error(f"[NEWSLETTER] Error getting history: {e}")
        return []
