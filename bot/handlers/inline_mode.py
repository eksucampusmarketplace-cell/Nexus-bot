"""
bot/handlers/inline_mode.py

Inline bot mode — users can query the bot from any chat via @botname query.

Enabled per group: inline_mode_enabled setting.

Supported queries:
  @botname note rules          → sends #rules note inline
  @botname note faq            → sends #faq note inline
  @botname notes               → list all available notes (as buttons)
  @botname stats               → group statistics card
  @botname time                → current group time

Logs prefix: [INLINE]
"""

import logging
import uuid
from datetime import datetime

import pytz
from telegram import (
    Update, InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.ext import ContextTypes

log = logging.getLogger("inline")


async def handle_inline_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Handle @botname queries from users."""
    query    = update.inline_query
    user     = update.effective_user
    db       = context.bot_data.get("db")
    bot_id   = context.bot.id

    if not query:
        return

    raw_q  = (query.query or "").strip().lower()
    results = []

    user_groups = await db.fetch(
        """SELECT chat_id, inline_mode_enabled,
                  timezone
           FROM groups
           WHERE inline_mode_enabled=TRUE
           LIMIT 5""",
    )

    if not user_groups:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Inline mode not enabled",
            description="Ask your group admin to enable inline mode.",
            input_message_content=InputTextMessageContent(
                "Inline mode is not enabled. Ask your group admin."
            )
        ))
        await query.answer(results, cache_time=30)
        return

    parts = raw_q.split(None, 1)
    cmd   = parts[0] if parts else ""
    arg   = parts[1] if len(parts) > 1 else ""

    # ── Note query ─────────────────────────────────────────────────────────
    if cmd in ("note", "notes", "#"):
        for group in user_groups:
            chat_id = group["chat_id"]
            if arg:
                note = await db.fetchrow(
                    "SELECT * FROM notes WHERE chat_id=$1 AND name=$2",
                    chat_id, arg
                )
                if note:
                    content = note["content"] or f"#{note['name']}"
                    results.append(InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=f"#{note['name']}",
                        description=(note["content"] or "")[:60],
                        input_message_content=InputTextMessageContent(
                            content,
                            parse_mode="HTML"
                        )
                    ))
            else:
                notes = await db.fetch(
                    "SELECT name, content FROM notes WHERE chat_id=$1 ORDER BY name LIMIT 10",
                    chat_id
                )
                for n in notes:
                    results.append(InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=f"#{n['name']}",
                        description=(n["content"] or "")[:60],
                        input_message_content=InputTextMessageContent(
                            n["content"] or f"#{n['name']}",
                            parse_mode="HTML"
                        )
                    ))

    # ── Stats query ─────────────────────────────────────────────────────────
    elif cmd == "stats":
        for group in user_groups:
            chat_id = group["chat_id"]
            try:
                count = await context.bot.get_chat_member_count(chat_id)
                chat  = await context.bot.get_chat(chat_id)

                bans = await db.fetchval(
                    """SELECT COUNT(*) FROM activity_log
                       WHERE chat_id=$1 AND event_type='ban'
                       AND created_at > NOW() - INTERVAL '7 days'""",
                    chat_id
                ) or 0
                warns = await db.fetchval(
                    """SELECT COUNT(*) FROM activity_log
                       WHERE chat_id=$1 AND event_type='warn'
                       AND created_at > NOW() - INTERVAL '7 days'""",
                    chat_id
                ) or 0

                text = (
                    f"📊 <b>{chat.title}</b>\n\n"
                    f"👥 Members: {count}\n"
                    f"🚫 Bans (7d): {bans}\n"
                    f"⚠️ Warnings (7d): {warns}"
                )
                results.append(InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=f"Stats: {chat.title}",
                    description=f"{count} members",
                    input_message_content=InputTextMessageContent(
                        text, parse_mode="HTML"
                    )
                ))
            except Exception:
                pass

    # ── Time query ──────────────────────────────────────────────────────────
    elif cmd == "time":
        for group in user_groups:
            tz_name = group.get("timezone") or "UTC"
            try:
                tz       = pytz.timezone(tz_name)
                now      = datetime.now(tz)
                time_str = now.strftime("%H:%M:%S %Z")
                date_str = now.strftime("%d %B %Y")
                results.append(InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=f"Group Time: {time_str}",
                    description=date_str,
                    input_message_content=InputTextMessageContent(
                        f"🕐 {time_str}\n📅 {date_str}\n🌍 {tz_name}"
                    )
                ))
            except Exception:
                pass

    # ── Default: show available commands ────────────────────────────────────
    else:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Nexus Inline Mode",
            description="Try: note <name> | notes | stats | time",
            input_message_content=InputTextMessageContent(
                "⚡ <b>Nexus Inline Commands:</b>\n\n"
                "@botname note <name> — get a saved note\n"
                "@botname notes — list all notes\n"
                "@botname stats — group statistics\n"
                "@botname time — current group time",
                parse_mode="HTML"
            )
        ))

    await query.answer(results[:10], cache_time=10)

    if db and user:
        try:
            await db.execute(
                """INSERT INTO inline_queries
                   (bot_id, user_id, query, result_type)
                   VALUES ($1,$2,$3,$4)""",
                bot_id, user.id, raw_q,
                cmd or "help"
            )
        except Exception:
            pass

    log.info(
        f"[INLINE] Query | user={user.id} q={raw_q!r} "
        f"results={len(results)}"
    )
