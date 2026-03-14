"""
bot/engagement/newsletter.py

Weekly Newsletter — auto-generated group summary.
Sent every Sunday at 9am UTC (configurable).

Sections:
1. Header with week dates
2. Most active members (top 5 by messages)
3. Top XP earners this week
4. New members who joined
5. Milestones reached this week
6. Leaderboard snapshot (top 3)
7. Streak highlights (longest streaks)
8. Custom admin message (optional)

Log prefix: [NEWSLETTER]
"""

import logging
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger("newsletter")

MEMBER_COUNT_MILESTONES = [100, 500, 1000, 5000, 10000]
MESSAGE_COUNT_MILESTONES = [1000, 10000, 100000]


async def get_week_stats(
    pool,
    chat_id: int,
    bot_id: int,
    week_start: date,
    week_end: date,
) -> dict:
    """Gather all stats for the week."""
    try:
        async with pool.acquire() as conn:
            start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(week_end, datetime.max.time()).replace(tzinfo=timezone.utc)

            top_members = await conn.fetch(
                """
                SELECT user_id, total_messages FROM member_xp
                WHERE chat_id=$1 AND bot_id=$2
                ORDER BY total_messages DESC LIMIT 5
                """,
                chat_id, bot_id,
            )

            top_xp_earners = await conn.fetch(
                """
                SELECT user_id, SUM(amount) AS xp_earned
                FROM xp_transactions
                WHERE chat_id=$1 AND bot_id=$2
                  AND created_at BETWEEN $3 AND $4
                  AND amount > 0
                GROUP BY user_id
                ORDER BY xp_earned DESC LIMIT 5
                """,
                chat_id, bot_id, start_dt, end_dt,
            )

            top_streaks = await conn.fetch(
                """
                SELECT user_id, streak_days FROM member_xp
                WHERE chat_id=$1 AND bot_id=$2 AND streak_days > 0
                ORDER BY streak_days DESC LIMIT 3
                """,
                chat_id, bot_id,
            )

            leaderboard = await conn.fetch(
                """
                SELECT user_id, xp, level FROM member_xp
                WHERE chat_id=$1 AND bot_id=$2
                ORDER BY xp DESC LIMIT 3
                """,
                chat_id, bot_id,
            )

            milestones = await conn.fetch(
                """
                SELECT * FROM group_milestones
                WHERE chat_id=$1 AND bot_id=$2
                  AND reached_at BETWEEN $3 AND $4
                """,
                chat_id, bot_id, start_dt, end_dt,
            )

        return {
            "top_members": [dict(r) for r in top_members],
            "top_xp_earners": [dict(r) for r in top_xp_earners],
            "top_streaks": [dict(r) for r in top_streaks],
            "leaderboard": [dict(r) for r in leaderboard],
            "milestones": [dict(r) for r in milestones],
        }
    except Exception as e:
        log.error(f"[NEWSLETTER] get_week_stats error | chat={chat_id} err={e}")
        return {}


async def generate_newsletter(
    pool,
    chat_id: int,
    bot_id: int,
    week_start: date,
    week_end: date,
) -> str:
    """Generate full newsletter text for a group."""
    from db.ops.engagement import get_newsletter_config

    config = await get_newsletter_config(pool, chat_id, bot_id)
    stats = await get_week_stats(pool, chat_id, bot_id, week_start, week_end)

    start_str = week_start.strftime("%B %-d")
    end_str = week_end.strftime("%-d, %Y")

    lines = [
        f"📰 <b>Weekly Digest</b>",
        f"{start_str}–{end_str}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if config.get("custom_intro"):
        lines.append(f"\n{config['custom_intro']}\n")

    if config.get("include_top_members") and stats.get("top_members"):
        lines.append("\n🏆 <b>Most Active Members</b>")
        for i, m in enumerate(stats["top_members"], 1):
            lines.append(f"{i}. User {m['user_id']} — {m['total_messages']} messages")

    if stats.get("top_xp_earners"):
        lines.append("\n⭐ <b>Top XP Earners This Week</b>")
        for i, m in enumerate(stats["top_xp_earners"], 1):
            lines.append(f"{i}. User {m['user_id']} — +{m['xp_earned']} XP")

    if config.get("include_leaderboard") and stats.get("leaderboard"):
        medals = ["👑", "⭐", "🌟"]
        lines.append("\n📊 <b>Leaderboard</b>")
        for i, m in enumerate(stats["leaderboard"]):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            lines.append(f"{medal} User {m['user_id']} — Lv.{m['level']} — {m['xp']} XP")

    if config.get("include_milestones") and stats.get("milestones"):
        lines.append("\n🎯 <b>Milestones This Week</b>")
        for m in stats["milestones"]:
            lines.append(f"🎉 {m['milestone_type'].replace('_', ' ').title()}: {m['milestone_value']}")

    if stats.get("top_streaks"):
        lines.append("\n🔥 <b>Longest Streaks</b>")
        for m in stats["top_streaks"]:
            lines.append(f"User {m['user_id']} — {m['streak_days']} days 🔥")

    lines.append("\nSee you next week! 💪")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


async def send_newsletter(
    bot,
    pool,
    chat_id: int,
    bot_id: int,
):
    """Generate and send newsletter to group. Pin it if configured."""
    try:
        from db.ops.engagement import (
            get_newsletter_config, save_newsletter_history, get_newsletter_history,
        )

        today = date.today()
        week_start = today - timedelta(days=7)
        week_end = today - timedelta(days=1)

        config = await get_newsletter_config(pool, chat_id, bot_id)
        if not config.get("enabled", True):
            return

        text = await generate_newsletter(pool, chat_id, bot_id, week_start, week_end)
        stats = await get_week_stats(pool, chat_id, bot_id, week_start, week_end)

        msg = await bot.send_message(chat_id, text, parse_mode="HTML")
        message_id = msg.message_id

        history = await get_newsletter_history(pool, chat_id, bot_id, limit=1)
        if history:
            try:
                await bot.unpin_chat_message(chat_id, history[0]["message_id"])
            except Exception:
                pass

        try:
            await bot.pin_chat_message(chat_id, message_id, disable_notification=True)
        except Exception:
            pass

        await save_newsletter_history(pool, chat_id, bot_id, message_id, stats)
        log.info(f"[NEWSLETTER] Sent | chat={chat_id}")
    except Exception as e:
        log.error(f"[NEWSLETTER] send_newsletter error | chat={chat_id} err={e}")


async def check_milestones(
    pool,
    bot,
    chat_id: int,
    bot_id: int,
):
    """Check if group has hit any milestones since last check."""
    try:
        async with pool.acquire() as conn:
            member_count = await conn.fetchval(
                "SELECT member_count FROM groups WHERE chat_id=$1", chat_id
            ) or 0

            for threshold in MEMBER_COUNT_MILESTONES:
                if member_count >= threshold:
                    exists = await conn.fetchval(
                        """
                        SELECT id FROM group_milestones
                        WHERE chat_id=$1 AND bot_id=$2
                          AND milestone_type='member_count' AND milestone_value=$3
                        """,
                        chat_id, bot_id, threshold,
                    )
                    if not exists:
                        await conn.execute(
                            """
                            INSERT INTO group_milestones
                                (chat_id, bot_id, milestone_type, milestone_value)
                            VALUES ($1, $2, 'member_count', $3)
                            """,
                            chat_id, bot_id, threshold,
                        )
                        if bot:
                            try:
                                await bot.send_message(
                                    chat_id,
                                    f"🎉 Milestone reached: <b>{threshold} members!</b>",
                                    parse_mode="HTML",
                                )
                            except Exception:
                                pass
                        log.info(f"[NEWSLETTER] Milestone: {threshold} members | chat={chat_id}")
    except Exception as e:
        log.error(f"[NEWSLETTER] check_milestones error | chat={chat_id} err={e}")


async def send_weekly_newsletters(context):
    """
    Find all groups with newsletter enabled.
    Generate and send newsletter for each.
    Rate limit: send one every 2 seconds to avoid flood.
    """
    import asyncio
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    day_of_week = now.weekday()
    hour_utc = now.hour

    from db.ops.engagement import get_groups_for_newsletter

    pool = context.bot_data.get("db")
    if not pool:
        return

    groups = await get_groups_for_newsletter(pool, day_of_week, hour_utc)
    log.info(f"[NEWSLETTER] Sending to {len(groups)} groups")

    for group in groups:
        try:
            await send_newsletter(context.bot, pool, group["chat_id"], group["bot_id"])
            await asyncio.sleep(2)
        except Exception as e:
            log.error(f"[NEWSLETTER] Failed for chat={group['chat_id']} err={e}")
