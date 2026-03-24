"""
bot/handlers/schedule_msg.py

Admin commands for scheduling announcements directly from chat.

Commands:
  /schedule <time> <message>  — Schedule a one-time announcement
  /schedule daily HH:MM <msg> — Schedule daily recurring message
  /schedule list              — List scheduled messages for this group
  /schedule cancel <id>       — Cancel a scheduled message

Log prefix: [SCHEDULE_CMD]
"""

import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.utils.permissions import is_admin

log = logging.getLogger("schedule_cmd")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /schedule <subcommand> ...

    Subcommands:
      /schedule <minutes>m <message>   — Send message after N minutes
      /schedule daily HH:MM <message>  — Send every day at HH:MM UTC
      /schedule list                   — List active scheduled messages
      /schedule cancel <id>            — Cancel a scheduled message
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command only works in groups.")
        return

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can schedule messages.")
        return

    if not context.args:
        await update.message.reply_text(
            "<b>Schedule Messages</b>\n\n"
            "<code>/schedule 30m Hello world</code> — send in 30 minutes\n"
            "<code>/schedule daily 09:00 Good morning!</code> — daily at 09:00 UTC\n"
            "<code>/schedule list</code> — view scheduled messages\n"
            "<code>/schedule cancel 5</code> — cancel message #5",
            parse_mode=ParseMode.HTML,
        )
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    sub = context.args[0].lower()

    if sub == "list":
        await _list_scheduled(update, db, chat.id)
    elif sub == "cancel":
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /schedule cancel <id>")
            return
        await _cancel_scheduled(update, db, chat.id, context.args[1])
    elif sub == "daily":
        await _schedule_daily(update, context, db, chat.id, user.id)
    else:
        await _schedule_once(update, context, db, chat.id, user.id)


async def _schedule_once(update, context, db, chat_id, user_id):
    """Schedule a one-time message after N minutes."""
    arg = context.args[0].lower()

    if not arg.endswith("m") and not arg.endswith("h"):
        await update.message.reply_text(
            "Specify delay like <code>30m</code> or <code>2h</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        if arg.endswith("m"):
            minutes = int(arg[:-1])
        else:
            minutes = int(arg[:-1]) * 60
    except ValueError:
        await update.message.reply_text("Invalid time format. Use e.g. 30m or 2h.")
        return

    content = " ".join(context.args[1:])
    if not content:
        await update.message.reply_text("Please provide a message to schedule.")
        return

    send_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO scheduled_messages
               (chat_id, content, schedule_type, scheduled_at,
                next_send_at, max_sends, created_by)
               VALUES ($1, $2, 'once', $3, $3, 1, $4)
               RETURNING id""",
            chat_id,
            content,
            send_at,
            user_id,
        )

    await update.message.reply_text(
        f"Scheduled message #{row['id']}\n"
        f"Will be sent at {send_at.strftime('%Y-%m-%d %H:%M UTC')}",
        parse_mode=ParseMode.HTML,
    )
    log.info(f"[SCHEDULE_CMD] Once | chat={chat_id} user={user_id} id={row['id']}")


async def _schedule_daily(update, context, db, chat_id, user_id):
    """Schedule a daily recurring message."""
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /schedule daily HH:MM Your message here",
        )
        return

    time_str = context.args[1]
    try:
        parts = time_str.split(":")
        from datetime import time as dt_time

        time_of_day = dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid time format. Use HH:MM (e.g. 09:00).")
        return

    content = " ".join(context.args[2:])
    if not content:
        await update.message.reply_text("Please provide a message to schedule.")
        return

    # Calculate first send time
    now = datetime.now(timezone.utc)
    next_send = now.replace(
        hour=time_of_day.hour, minute=time_of_day.minute, second=0, microsecond=0
    )
    if next_send <= now:
        next_send += timedelta(days=1)

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO scheduled_messages
               (chat_id, content, schedule_type, time_of_day,
                next_send_at, max_sends, created_by)
               VALUES ($1, $2, 'daily', $3, $4, 0, $5)
               RETURNING id""",
            chat_id,
            content,
            time_of_day,
            next_send,
            user_id,
        )

    await update.message.reply_text(
        f"Daily message #{row['id']} scheduled\n"
        f"Time: {time_str} UTC every day\n"
        f"Next send: {next_send.strftime('%Y-%m-%d %H:%M UTC')}",
    )
    log.info(f"[SCHEDULE_CMD] Daily | chat={chat_id} user={user_id} id={row['id']}")


async def _list_scheduled(update, db, chat_id):
    """List active scheduled messages."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, content, schedule_type, next_send_at, send_count, max_sends
               FROM scheduled_messages
               WHERE chat_id=$1 AND is_active=TRUE
               ORDER BY next_send_at ASC
               LIMIT 10""",
            chat_id,
        )

    if not rows:
        await update.message.reply_text("No active scheduled messages.")
        return

    lines = ["<b>Scheduled Messages</b>\n"]
    for r in rows:
        content_preview = (r["content"] or "")[:40]
        if len(r["content"] or "") > 40:
            content_preview += "..."
        next_at = (
            r["next_send_at"].strftime("%m/%d %H:%M") if r["next_send_at"] else "?"
        )
        stype = r["schedule_type"]
        sends = (
            f"{r['send_count']}/{r['max_sends']}"
            if r["max_sends"]
            else f"{r['send_count']}x"
        )
        lines.append(f"#{r['id']} [{stype}] {next_at} ({sends})\n  {content_preview}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def _cancel_scheduled(update, db, chat_id, msg_id_str):
    """Cancel a scheduled message."""
    try:
        msg_id = int(msg_id_str)
    except ValueError:
        await update.message.reply_text("Invalid message ID.")
        return

    async with db.acquire() as conn:
        result = await conn.execute(
            "UPDATE scheduled_messages SET is_active=FALSE WHERE id=$1 AND chat_id=$2",
            msg_id,
            chat_id,
        )

    if "UPDATE 1" in result:
        await update.message.reply_text(f"Cancelled scheduled message #{msg_id}.")
        log.info(f"[SCHEDULE_CMD] Cancelled | chat={chat_id} id={msg_id}")
    else:
        await update.message.reply_text(
            f"Message #{msg_id} not found or already cancelled."
        )


schedule_handlers = [
    CommandHandler("schedule", cmd_schedule),
]
