"""
bot/engagement/newsletter.py

Weekly Newsletter — auto-generated group summary.
Sent every Sunday at 9am UTC (configurable).

Log prefix: [NEWSLETTER]
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("newsletter")


async def get_week_stats(
    pool,
    chat_id: int,
    bot_id: int,
    week_start: date,
    week_end: date
) -> dict:
    stats = {}
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, SUM(amount) AS xp_earned
            FROM xp_transactions
            WHERE chat_id=$1 AND bot_id=$2
              AND created_at >= $3 AND created_at < $4
            GROUP BY user_id
            ORDER BY xp_earned DESC
            LIMIT 5
            """,
            chat_id, bot_id,
            datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc),
            datetime.combine(week_end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        stats["top_xp_earners"] = [dict(r) for r in rows]

        rows = await conn.fetch(
            """
            SELECT user_id, total_messages
            FROM member_xp
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY total_messages DESC
            LIMIT 5
            """,
            chat_id, bot_id,
        )
        stats["most_active"] = [dict(r) for r in rows]

        rows = await conn.fetch(
            """
            SELECT user_id, xp, level
            FROM member_xp
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY xp DESC
            LIMIT 3
            """,
            chat_id, bot_id,
        )
        stats["leaderboard"] = [dict(r) for r in rows]

        rows = await conn.fetch(
            """
            SELECT user_id, streak_days
            FROM member_xp
            WHERE chat_id=$1 AND bot_id=$2 AND streak_days >= 3
            ORDER BY streak_days DESC
            LIMIT 5
            """,
            chat_id, bot_id,
        )
        stats["streaks"] = [dict(r) for r in rows]

        rows = await conn.fetch(
            """
            SELECT * FROM group_milestones
            WHERE chat_id=$1 AND bot_id=$2
              AND reached_at >= $3 AND reached_at < $4
            """,
            chat_id, bot_id,
            datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc),
            datetime.combine(week_end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        stats["milestones"] = [dict(r) for r in rows]

    return stats


async def generate_newsletter(
    pool,
    chat_id: int,
    bot_id: int,
    week_start: date,
    week_end: date
) -> str:
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
        lines.append(f"\n{config['custom_intro']}")

    if config.get("include_top_members") and stats.get("most_active"):
        lines.append("\n🏆 <b>Most Active Members</b>")
        for i, entry in enumerate(stats["most_active"], 1):
            lines.append(f"{i}. user {entry['user_id']} — {entry['total_messages']} messages")

    if stats.get("top_xp_earners"):
        lines.append("\n⭐ <b>Top XP Earners This Week</b>")
        for i, entry in enumerate(stats["top_xp_earners"], 1):
            lines.append(f"{i}. user {entry['user_id']} — +{entry['xp_earned']} XP")

    if config.get("include_milestones") and stats.get("milestones"):
        lines.append("\n🎯 <b>Milestones This Week</b>")
        for m in stats["milestones"]:
            lines.append(f"🎉 {m['milestone_type']} reached {m['milestone_value']}!")

    if config.get("include_leaderboard") and stats.get("leaderboard"):
        lines.append("\n📊 <b>Leaderboard</b>")
        medals = ["👑", "⭐", "🌟"]
        for i, entry in enumerate(stats["leaderboard"], 1):
            medal = medals[i - 1] if i <= 3 else f"{i}."
            lines.append(
                f"{medal} user {entry['user_id']} — Lv.{entry['level']} — {entry['xp']} XP"
            )

    if stats.get("streaks"):
        lines.append("\n🔥 <b>Longest Streaks</b>")
        for entry in stats["streaks"]:
            lines.append(f"user {entry['user_id']} — {entry['streak_days']} days 🔥")

    lines.append("\nSee you next week! 💪")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


async def send_newsletter(
    bot,
    pool,
    chat_id: int,
    bot_id: int
):
    from db.ops.engagement import save_newsletter_history, get_newsletter_history

    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 1)
    week_end = today - timedelta(days=1)

    text = await generate_newsletter(pool, chat_id, bot_id, week_start, week_end)

    try:
        msg = await bot.send_message(chat_id, text, parse_mode="HTML")
        message_id = msg.message_id

        try:
            history = await get_newsletter_history(pool, chat_id, bot_id, limit=1)
            if history and history[0].get("message_id"):
                await bot.unpin_chat_message(chat_id, history[0]["message_id"])
        except Exception:
            pass

        try:
            await bot.pin_chat_message(chat_id, message_id)
        except Exception:
            pass

        stats = await get_week_stats(pool, chat_id, bot_id, week_start, week_end)
        await save_newsletter_history(pool, chat_id, bot_id, message_id, stats)
        log.info(f"[NEWSLETTER] Sent | chat={chat_id}")
    except Exception as e:
        log.error(f"[NEWSLETTER] Failed to send | chat={chat_id} error={e}")


async def check_milestones(pool, bot, chat_id: int, bot_id: int):
    from db.ops.engagement import record_milestone, get_unannounced_milestones, mark_milestone_announced

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM member_xp WHERE chat_id=$1 AND bot_id=$2",
            chat_id, bot_id,
        )
        member_count = row["cnt"] if row else 0

        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(total_messages), 0) AS total FROM member_xp WHERE chat_id=$1 AND bot_id=$2",
            chat_id, bot_id,
        )
        total_messages = row["total"] if row else 0

    for milestone in [100, 500, 1000, 5000, 10000]:
        if member_count >= milestone:
            await record_milestone(pool, chat_id, bot_id, "member_count", milestone)

    for milestone in [1000, 10000, 100000]:
        if total_messages >= milestone:
            await record_milestone(pool, chat_id, bot_id, "total_messages", milestone)

    unannounced = await get_unannounced_milestones(pool, chat_id, bot_id)
    for m in unannounced:
        try:
            if m["milestone_type"] == "member_count":
                text = f"🎉 The group has reached <b>{m['milestone_value']}</b> members!"
            else:
                text = f"🎉 The group has sent <b>{m['milestone_value']}</b> messages!"
            await bot.send_message(chat_id, text, parse_mode="HTML")
            await mark_milestone_announced(pool, m["id"])
        except Exception as e:
            log.warning(f"[NEWSLETTER] Milestone announce failed: {e}")


async def send_weekly_newsletters(pool, bot):
    from datetime import datetime, timezone
    from db.ops.engagement import get_groups_for_newsletter

    now = datetime.now(timezone.utc)
    day_of_week = now.weekday()
    hour_utc = now.hour

    groups = await get_groups_for_newsletter(pool, day_of_week, hour_utc)
    count = 0
    import asyncio
    for group in groups:
        try:
            await send_newsletter(bot, pool, group["chat_id"], group["bot_id"])
            count += 1
            await asyncio.sleep(2)
        except Exception as e:
            log.error(f"[NEWSLETTER] Error for group {group['chat_id']}: {e}")

    log.info(f"[NEWSLETTER] Sent to {count} groups")
