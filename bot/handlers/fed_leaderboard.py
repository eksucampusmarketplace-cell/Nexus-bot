"""
bot/handlers/fed_leaderboard.py

Federation Leaderboards — weekly XP competitions between groups.

Commands:
  /fedleaderboard        — Show this week's federation XP rankings
  /fedleaderboard last   — Show last week's rankings

Background:
  sync_federation_xp() is called periodically to aggregate XP per group per week.

Log prefix: [FED_LB]
"""

import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.utils.permissions import is_admin

log = logging.getLogger("fed_lb")


def _current_week_start() -> datetime:
    """Get the start of the current week (Monday 00:00 UTC)."""
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


async def cmd_fedleaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show federation XP leaderboard."""
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command only works in groups.")
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    # Determine which week to show
    show_last = context.args and context.args[0].lower() == "last"
    week_start = _current_week_start()
    if show_last:
        week_start -= timedelta(weeks=1)

    week_label = week_start.strftime("%b %d")

    async with db.acquire() as conn:
        # Find federations this group belongs to
        feds = await conn.fetch(
            """SELECT f.id, f.name
               FROM federation_members fm
               JOIN federations f ON f.id = fm.federation_id
               WHERE fm.chat_id=$1""",
            chat.id,
        )

        if not feds:
            await update.message.reply_text(
                "This group is not part of any TrustNet.\n"
                "Join one with /jointrust <code> first."
            )
            return

        # Show leaderboard for each federation
        for fed in feds:
            rows = await conn.fetch(
                """SELECT fwx.chat_id, fwx.total_xp, fwx.member_count,
                          g.title
                   FROM federation_weekly_xp fwx
                   LEFT JOIN groups g ON g.chat_id = fwx.chat_id
                   WHERE fwx.federation_id=$1 AND fwx.week_start=$2
                   ORDER BY fwx.total_xp DESC
                   LIMIT 10""",
                fed["id"],
                week_start.date(),
            )

            if not rows:
                await update.message.reply_text(
                    f"<b>{fed['name']}</b> — Week of {week_label}\n\n"
                    f"No XP data yet for this week.",
                    parse_mode=ParseMode.HTML,
                )
                continue

            lines = [
                f"<b>{fed['name']}</b> — Week of {week_label}\n",
            ]
            medals = ["🥇", "🥈", "🥉"]

            for i, r in enumerate(rows):
                medal = medals[i] if i < 3 else f"{i+1}."
                title = r["title"] or f"Chat {r['chat_id']}"
                xp = r["total_xp"] or 0
                members = r["member_count"] or 0
                avg = xp // members if members > 0 else 0
                marker = " (you)" if r["chat_id"] == chat.id else ""
                lines.append(
                    f"{medal} <b>{title}</b>{marker}\n"
                    f"   {xp:,} XP | {members} members | avg {avg}/member"
                )

            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def sync_federation_xp(db):
    """
    Aggregate XP earned this week per group for all federations.
    Called periodically (e.g., every hour) from main.py.
    """
    week_start = _current_week_start()

    async with db.acquire() as conn:
        # Get all federation member groups
        groups = await conn.fetch("""SELECT fm.federation_id, fm.chat_id
               FROM federation_members fm""")

        for g in groups:
            try:
                # Sum XP earned this week for this group (across all bots)
                xp_row = await conn.fetchrow(
                    """SELECT COALESCE(SUM(amount), 0) as total_xp,
                              COUNT(DISTINCT user_id) as member_count
                       FROM xp_transactions
                       WHERE chat_id=$1
                         AND created_at >= $2""",
                    g["chat_id"],
                    week_start,
                )

                total_xp = xp_row["total_xp"] if xp_row else 0
                member_count = xp_row["member_count"] if xp_row else 0

                await conn.execute(
                    """INSERT INTO federation_weekly_xp
                       (federation_id, chat_id, week_start, total_xp, member_count)
                       VALUES ($1, $2, $3, $4, $5)
                       ON CONFLICT (federation_id, chat_id, week_start)
                       DO UPDATE SET total_xp=EXCLUDED.total_xp,
                                     member_count=EXCLUDED.member_count,
                                     updated_at=NOW()""",
                    g["federation_id"],
                    g["chat_id"],
                    week_start.date(),
                    total_xp,
                    member_count,
                )
            except Exception as e:
                log.warning(f"[FED_LB] Sync error | chat={g['chat_id']}: {e}")

    log.debug(f"[FED_LB] Synced {len(groups)} groups for week {week_start.date()}")


fed_leaderboard_handlers = [
    CommandHandler("fedleaderboard", cmd_fedleaderboard),
]
