"""
bot/handlers/report.py

Report system — lets users flag messages for admin review.

Commands (groups only):
  /report [reason]       — reply to a message to report it
  /reports               — (admins) list open reports
  /resolve <id> [note]   — (admins) mark report resolved
  /dismiss <id> [note]   — (admins) dismiss a report

Callback actions (inline buttons on the admin report card):
  report:resolve:<id>
  report:dismiss:<id>

Logs prefix: [REPORT]
"""

import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from bot.utils.permissions import is_admin
from bot.logging.log_channel import log_event
from db.ops import reports as db_reports

log = logging.getLogger("report")

_MAX_REASON_LEN = 300


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /report [reason]
    Reply to a message to report it to admins.
    """
    message = update.effective_message
    chat = update.effective_chat
    reporter = update.effective_user
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    if not message.reply_to_message:
        await message.reply_text(
            "⚠️ Reply to a message with /report to flag it for admin review.\n"
            "Example: Reply to a spam message and type <code>/report Spam links</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    target_msg = message.reply_to_message
    target_user = target_msg.from_user

    if target_user and target_user.id == reporter.id:
        await message.reply_text("❌ You cannot report your own message.")
        return

    if target_user and target_user.is_bot:
        await message.reply_text("❌ You cannot report bot messages this way.")
        return

    reason = (
        " ".join(context.args).strip()[:_MAX_REASON_LEN] if context.args else "No reason provided"
    )

    if not db:
        await message.reply_text("⚠️ Report system unavailable right now.")
        return

    try:
        report_id = await db_reports.save_report(
            pool=db,
            chat_id=chat.id,
            reporter_id=reporter.id,
            reported_id=target_user.id if target_user else None,
            message_id=target_msg.message_id,
            reason=reason,
        )
    except Exception as e:
        log.error(f"[REPORT] DB save failed | chat={chat.id} | error={e}")
        await message.reply_text("❌ Could not save your report. Please try again later.")
        return

    if target_user and target_user.id:
        await db_reports.increment_user_report_count(db, chat.id, target_user.id)

    log.info(
        f"[REPORT] Submitted | report_id={report_id} "
        f"chat={chat.id} reporter={reporter.id} "
        f"reported={getattr(target_user, 'id', '?')} reason={reason!r}"
    )

    await message.reply_text(
        f"✅ <b>Report #{report_id} submitted</b>\n" f"Admins have been notified.",
        parse_mode=ParseMode.HTML,
    )

    target_name = (
        f"@{target_user.username}"
        if target_user and target_user.username
        else (target_user.full_name if target_user else "Unknown")
    )
    reporter_name = f"@{reporter.username}" if reporter.username else reporter.full_name

    admin_text = (
        f"🚨 <b>New Report #{report_id}</b>\n\n"
        f"<b>Reporter:</b> {reporter_name} (<code>{reporter.id}</code>)\n"
        f"<b>Reported:</b> {target_name}"
        + (f" (<code>{target_user.id}</code>)" if target_user else "")
        + f"\n<b>Reason:</b> {reason}\n"
        f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Resolve", callback_data=f"report:resolve:{report_id}"),
                InlineKeyboardButton("❌ Dismiss", callback_data=f"report:dismiss:{report_id}"),
            ]
        ]
    )

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        for admin in admins:
            if admin.user.is_bot:
                continue
            try:
                await context.bot.send_message(
                    chat_id=admin.user.id,
                    text=admin_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            except Exception:
                pass
    except Exception as e:
        log.warning(f"[REPORT] Could not notify admins | chat={chat.id} | error={e}")

    await log_event(
        bot=context.bot,
        db=db,
        chat_id=chat.id,
        event_type="report",
        actor=reporter,
        target=target_user,
        details={"reason": reason, "report_id": report_id},
        chat_title=chat.title or "",
    )


async def cmd_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reports
    Admins only — show all open reports for this group.
    """
    if not await is_admin(update, context):
        await update.effective_message.reply_text("❌ This command is for admins only.")
        return

    chat = update.effective_chat
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    if not db:
        await update.effective_message.reply_text("⚠️ Report system unavailable.")
        return

    open_reports = await db_reports.get_open_reports(db, chat.id)

    if not open_reports:
        await update.effective_message.reply_text(
            "✅ <b>No open reports</b>\n\nYour group is all clear!",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [f"📋 <b>Open Reports ({len(open_reports)})</b>\n"]
    for r in open_reports[:10]:
        ts = r["created_at"].strftime("%m-%d %H:%M") if r["created_at"] else "?"
        reason_short = (r["reason"] or "No reason")[:60]
        lines.append(
            f"<b>#{r['id']}</b> — {reason_short}\n"
            f"  <i>Reporter: <code>{r['reporter_id']}</code>"
            + (f" | Reported: <code>{r['reported_id']}</code>" if r["reported_id"] else "")
            + f" | {ts}</i>"
        )

    if len(open_reports) > 10:
        lines.append(f"\n<i>…and {len(open_reports) - 10} more. Use the dashboard to view all.</i>")

    lines.append("\n<i>Use /resolve &lt;id&gt; or /dismiss &lt;id&gt; to action a report.</i>")

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


async def cmd_resolve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /resolve <report_id> [note]
    Admins only — mark a report as resolved.
    """
    await _action_report(update, context, status="resolved")


async def cmd_dismiss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /dismiss <report_id> [note]
    Admins only — dismiss a report.
    """
    await _action_report(update, context, status="dismissed")


async def _action_report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status: str,
):
    if not await is_admin(update, context):
        await update.effective_message.reply_text("❌ This command is for admins only.")
        return

    if not context.args:
        cmd = "resolve" if status == "resolved" else "dismiss"
        await update.effective_message.reply_text(
            f"Usage: /{cmd} &lt;report_id&gt; [note]",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        report_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("❌ Report ID must be a number.")
        return

    note = " ".join(context.args[1:]).strip()[:_MAX_REASON_LEN] if len(context.args) > 1 else ""
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    success = await db_reports.resolve_report(
        pool=db,
        report_id=report_id,
        resolved_by=update.effective_user.id,
        status=status,
        note=note,
    )

    if success:
        emoji = "✅" if status == "resolved" else "❌"
        await update.effective_message.reply_text(
            f"{emoji} Report #{report_id} marked as <b>{status}</b>."
            + (f"\nNote: {note}" if note else ""),
            parse_mode=ParseMode.HTML,
        )
        log.info(
            f"[REPORT] {status.capitalize()} | report_id={report_id} "
            f"by={update.effective_user.id} chat={update.effective_chat.id}"
        )
    else:
        await update.effective_message.reply_text(
            f"❌ Report #{report_id} not found or already resolved."
        )


async def report_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle inline button callbacks: report:resolve:<id> and report:dismiss:<id>
    These arrive in private chat DMs to admins.
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, action, report_id_str = parts
    try:
        report_id = int(report_id_str)
    except ValueError:
        return

    if action not in ("resolve", "dismiss"):
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    status = "resolved" if action == "resolve" else "dismissed"

    success = await db_reports.resolve_report(
        pool=db,
        report_id=report_id,
        resolved_by=query.from_user.id,
        status=status,
        note="",
    )

    emoji = "✅" if action == "resolve" else "❌"
    label = "Resolved" if action == "resolve" else "Dismissed"

    if success:
        await query.edit_message_text(
            query.message.text
            + f"\n\n{emoji} <b>{label}</b> by @{query.from_user.username or query.from_user.first_name}",
            parse_mode=ParseMode.HTML,
        )
        log.info(f"[REPORT] {label} via button | report_id={report_id} " f"by={query.from_user.id}")
    else:
        await query.edit_message_text(
            query.message.text + f"\n\n⚠️ Report #{report_id} was already actioned.",
            parse_mode=ParseMode.HTML,
        )


report_handlers = [
    CommandHandler("report", cmd_report, filters=None),
    CommandHandler("reports", cmd_reports, filters=None),
    CommandHandler("resolve", cmd_resolve, filters=None),
    CommandHandler("dismiss", cmd_dismiss, filters=None),
    CallbackQueryHandler(report_callback_handler, pattern=r"^report:(resolve|dismiss):\d+$"),
]
