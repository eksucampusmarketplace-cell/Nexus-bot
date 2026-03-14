"""
bot/handlers/import_export.py

Export and import group settings as JSON.

/export
  → Bot sends a .json file with all exportable settings.

/import
  → User uploads a .json file (reply to bot's document message)
  → Bot validates, applies settings
  → Shows diff: X settings changed, Y notes added, etc.

/reset
  → Wipe all custom settings and restore defaults
  → Asks confirmation first (inline buttons Yes/No)
  → Does NOT delete: billing, warnings history, member data

Logs prefix: [IMPORT_EXPORT]
"""

import json
import logging
from datetime import datetime, timezone
from io import BytesIO

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.error import TelegramError

from bot.handlers.copy_settings import COPYABLE_SETTINGS_KEYS
from bot.logging.log_channel import log_event

log = logging.getLogger("import_export")

EXPORT_VERSION = "1.0"


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /export
    Bot sends complete settings as a downloadable JSON file.
    """
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")
    bot = context.bot
    user = update.effective_user

    settings_row = await db.fetchrow("SELECT * FROM groups WHERE chat_id=$1", chat.id)
    settings_dict = {}
    if settings_row:
        raw = dict(settings_row)
        settings_dict = {
            k: raw[k] for k in COPYABLE_SETTINGS_KEYS if k in raw and raw[k] is not None
        }

    notes = await db.fetch(
        """SELECT name, content, media_type, is_private
           FROM notes WHERE chat_id=$1 ORDER BY name""",
        chat.id,
    )
    filters = await db.fetch(
        """SELECT keyword, reply_content, media_type, reply_mode
           FROM filters WHERE chat_id=$1 AND is_active=TRUE""",
        chat.id,
    )
    blocklist = await db.fetch(
        """SELECT keyword, action
           FROM blocklist WHERE chat_id=$1 AND is_active=TRUE""",
        chat.id,
    )
    silent_times = await db.fetch(
        """SELECT slot, start_time::text, end_time::text,
                  is_active, start_text, end_text
           FROM silent_times WHERE chat_id=$1""",
        chat.id,
    )
    regex_pats = await db.fetch(
        "SELECT pattern, penalty FROM regex_patterns WHERE chat_id=$1", chat.id
    )
    nec_words = await db.fetch(
        "SELECT word FROM necessary_words WHERE chat_id=$1 AND is_active=TRUE", chat.id
    )
    rule_priority = await db.fetchrow(
        "SELECT rule_order FROM rule_priority WHERE chat_id=$1", chat.id
    )
    time_windows = await db.fetch(
        "SELECT rule_key, start_time::text, end_time::text FROM rule_time_windows WHERE chat_id=$1",
        chat.id,
    )
    penalties = await db.fetch(
        "SELECT rule_key, penalty, duration_hours FROM rule_penalties WHERE chat_id=$1", chat.id
    )

    export_data = {
        "nexus_version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "chat_id": chat.id,
        "chat_title": chat.title,
        "settings": settings_dict,
        "notes": [dict(r) for r in notes],
        "filters": [dict(r) for r in filters],
        "blocklist": [dict(r) for r in blocklist],
        "silent_times": [dict(r) for r in silent_times],
        "regex_patterns": [dict(r) for r in regex_pats],
        "necessary_words": [r["word"] for r in nec_words],
        "rule_priority": rule_priority["rule_order"] if rule_priority else [],
        "rule_time_windows": {
            r["rule_key"]: {"start": r["start_time"], "end": r["end_time"]} for r in time_windows
        },
        "rule_penalties": {
            r["rule_key"]: {"penalty": r["penalty"], "duration_hours": r["duration_hours"]}
            for r in penalties
        },
    }

    json_bytes = json.dumps(export_data, indent=2, default=str).encode()
    buf = BytesIO(json_bytes)
    buf.name = f"nexus_settings_{chat.id}_{datetime.now().strftime('%Y%m%d')}.json"

    try:
        await bot.send_document(
            chat_id=chat.id,
            document=buf,
            filename=buf.name,
            caption=(
                f"📤 <b>Settings Export</b>\n"
                f"Group: {chat.title}\n"
                f"Exported: {len(settings_dict)} settings, "
                f"{len(notes)} notes, {len(filters)} filters, "
                f"{len(blocklist)} blocklist entries\n\n"
                "Use /import to restore these settings in another group."
            ),
            parse_mode="HTML",
        )
    except TelegramError as e:
        await msg.reply_text(f"❌ Export failed: {e}")
        return

    await log_event(
        bot=bot,
        db=db,
        chat_id=chat.id,
        event_type="export",
        actor=user,
        details={
            "export_keys": len(settings_dict),
            "notes_count": len(notes),
            "filters_count": len(filters),
        },
        chat_title=chat.title,
        bot_id=bot.id,
    )
    log.info(
        f"[IMPORT_EXPORT] Exported | chat={chat.id} "
        f"settings={len(settings_dict)} notes={len(notes)}"
    )


async def cmd_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /import (reply to a JSON document message)
    Validates and applies the settings from the uploaded file.
    """
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")
    bot = context.bot
    user = update.effective_user

    doc = None
    if msg.document:
        doc = msg.document
    elif msg.reply_to_message and msg.reply_to_message.document:
        doc = msg.reply_to_message.document

    if not doc:
        await msg.reply_text(
            "Usage: Upload a Nexus JSON export file and send /import,\n"
            "or reply to the exported file with /import."
        )
        return

    if not doc.file_name.endswith(".json"):
        await msg.reply_text("❌ File must be a .json export from Nexus.")
        return

    if doc.file_size > 500_000:
        await msg.reply_text("❌ File too large. Max 500KB.")
        return

    try:
        file = await bot.get_file(doc.file_id)
        buf = BytesIO()
        await file.download_to_memory(buf)
        buf.seek(0)
        data = json.loads(buf.read().decode())
    except (json.JSONDecodeError, Exception) as e:
        await msg.reply_text(f"❌ Invalid JSON file: {e}")
        return

    if data.get("nexus_version") != EXPORT_VERSION:
        await msg.reply_text(
            f"⚠️ Export version mismatch "
            f"(got {data.get('nexus_version')}, expected {EXPORT_VERSION}).\n"
            "Import may still work — proceeding."
        )

    changes = await _apply_import(db, chat.id, data)

    await msg.reply_text(
        f"✅ <b>Import Complete</b>\n\n"
        f"✅ {changes['settings']} settings applied\n"
        f"✅ {changes['notes']} notes imported\n"
        f"✅ {changes['filters']} filters imported\n"
        f"✅ {changes['blocklist']} blocklist entries imported\n"
        f"✅ {changes['silent_times']} silent time slots imported\n"
        f"✅ {changes['regex_patterns']} regex patterns imported\n"
        f"✅ {changes['necessary_words']} necessary words imported",
        parse_mode="HTML",
    )

    await log_event(
        bot=bot,
        db=db,
        chat_id=chat.id,
        event_type="import",
        actor=user,
        details=changes,
        chat_title=chat.title,
        bot_id=bot.id,
    )
    log.info(f"[IMPORT_EXPORT] Imported | chat={chat.id} changes={changes}")


async def _apply_import(db, chat_id: int, data: dict) -> dict:
    """Apply all sections of an import. Returns count of changes."""
    changes = {
        "settings": 0,
        "notes": 0,
        "filters": 0,
        "blocklist": 0,
        "silent_times": 0,
        "regex_patterns": 0,
        "necessary_words": 0,
    }

    settings = data.get("settings", {})
    allowed = {k: v for k, v in settings.items() if k in COPYABLE_SETTINGS_KEYS}
    if allowed:
        set_clauses = ", ".join(f"{k}=${i+2}" for i, k in enumerate(allowed.keys()))
        values = [chat_id] + list(allowed.values())
        await db.execute(
            f"""INSERT INTO groups
                (chat_id, {', '.join(allowed.keys())})
                VALUES ($1, {', '.join(f'${i+2}' for i in range(len(allowed)))})
                ON CONFLICT (chat_id)
                DO UPDATE SET {set_clauses}""",
            *values,
        )
        changes["settings"] = len(allowed)

    for note in data.get("notes", []):
        await db.execute(
            """INSERT INTO notes (chat_id, name, content, media_type, is_private)
               VALUES ($1,$2,$3,$4,$5)
               ON CONFLICT (chat_id, name) DO UPDATE SET
                 content=EXCLUDED.content,
                 media_type=EXCLUDED.media_type,
                 is_private=EXCLUDED.is_private""",
            chat_id,
            note.get("name", ""),
            note.get("content", ""),
            note.get("media_type"),
            note.get("is_private", False),
        )
        changes["notes"] += 1

    for f in data.get("filters", []):
        await db.execute(
            """INSERT INTO filters (chat_id, keyword, reply_content,
               media_type, reply_mode)
               VALUES ($1,$2,$3,$4,$5)
               ON CONFLICT (chat_id, keyword) DO UPDATE SET
                 reply_content=EXCLUDED.reply_content,
                 media_type=EXCLUDED.media_type""",
            chat_id,
            f.get("keyword", ""),
            f.get("reply_content", ""),
            f.get("media_type"),
            f.get("reply_mode", "reply"),
        )
        changes["filters"] += 1

    for b in data.get("blocklist", []):
        await db.execute(
            """INSERT INTO blocklist (chat_id, keyword, action)
               VALUES ($1,$2,$3)
               ON CONFLICT (chat_id, keyword)
               DO UPDATE SET action=EXCLUDED.action""",
            chat_id,
            b.get("keyword", ""),
            b.get("action", "delete"),
        )
        changes["blocklist"] += 1

    for st in data.get("silent_times", []):
        await db.execute(
            """INSERT INTO silent_times
               (chat_id, slot, start_time, end_time, is_active,
                start_text, end_text)
               VALUES ($1,$2,$3::TIME,$4::TIME,$5,$6,$7)
               ON CONFLICT (chat_id, slot) DO UPDATE SET
                 start_time=EXCLUDED.start_time,
                 end_time=EXCLUDED.end_time,
                 is_active=EXCLUDED.is_active,
                 start_text=EXCLUDED.start_text,
                 end_text=EXCLUDED.end_text""",
            chat_id,
            st.get("slot", 1),
            st.get("start_time", "00:00"),
            st.get("end_time", "08:00"),
            st.get("is_active", True),
            st.get("start_text", ""),
            st.get("end_text", ""),
        )
        changes["silent_times"] += 1

    for p in data.get("regex_patterns", []):
        await db.execute(
            """INSERT INTO regex_patterns (chat_id, pattern, penalty)
               VALUES ($1,$2,$3)
               ON CONFLICT DO NOTHING""",
            chat_id,
            p.get("pattern", ""),
            p.get("penalty", "delete"),
        )
        changes["regex_patterns"] += 1

    for word in data.get("necessary_words", []):
        await db.execute(
            """INSERT INTO necessary_words (chat_id, word)
               VALUES ($1,$2)
               ON CONFLICT (chat_id, word) DO NOTHING""",
            chat_id,
            word,
        )
        changes["necessary_words"] += 1

    if data.get("rule_priority"):
        await db.execute(
            """INSERT INTO rule_priority (chat_id, rule_order)
               VALUES ($1,$2)
               ON CONFLICT (chat_id)
               DO UPDATE SET rule_order=EXCLUDED.rule_order""",
            chat_id,
            json.dumps(data["rule_priority"]),
        )

    return changes


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reset — wipe all custom settings and restore defaults.
    Shows confirmation buttons first.
    """
    msg = update.effective_message
    chat = update.effective_chat

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Yes, reset everything", callback_data=f"reset_confirm:{chat.id}"
                ),
                InlineKeyboardButton("❌ Cancel", callback_data="reset_cancel"),
            ]
        ]
    )

    await msg.reply_text(
        "⚠️ <b>Reset Group Settings</b>\n\n"
        "This will delete:\n"
        "• All custom settings\n"
        "• All notes\n"
        "• All filters\n"
        "• All blocklist entries\n"
        "• Silent times\n"
        "• Regex patterns\n"
        "• Necessary words\n"
        "• Rule priority\n\n"
        "<b>This will NOT delete:</b>\n"
        "• Warning history\n"
        "• Member data\n"
        "• Billing/entitlements\n"
        "• Activity log\n\n"
        "Are you sure?",
        parse_mode="HTML",
        reply_markup=markup,
    )


async def handle_reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reset confirmation button presses."""
    query = update.callback_query
    data = query.data or ""
    db = context.bot_data.get("db")
    user = query.from_user
    bot = context.bot

    await query.answer()

    if data == "reset_cancel":
        await query.edit_message_text("✅ Reset cancelled.")
        return

    if not data.startswith("reset_confirm:"):
        return

    chat_id = int(data.split(":")[1])

    try:
        member = await bot.get_chat_member(chat_id, user.id)
        if member.status not in ("creator", "administrator"):
            await query.answer("❌ Admins only.", show_alert=True)
            return
    except Exception:
        return

    tables = [
        ("groups", "DELETE FROM groups WHERE chat_id=$1"),
        ("notes", "DELETE FROM notes WHERE chat_id=$1"),
        ("filters", "DELETE FROM filters WHERE chat_id=$1"),
        ("blocklist", "DELETE FROM blocklist WHERE chat_id=$1"),
        ("silent_times", "DELETE FROM silent_times WHERE chat_id=$1"),
        ("regex_patterns", "DELETE FROM regex_patterns WHERE chat_id=$1"),
        ("necessary_words", "DELETE FROM necessary_words WHERE chat_id=$1"),
        ("rule_priority", "DELETE FROM rule_priority WHERE chat_id=$1"),
        ("rule_time_windows", "DELETE FROM rule_time_windows WHERE chat_id=$1"),
        ("rule_penalties", "DELETE FROM rule_penalties WHERE chat_id=$1"),
        ("captcha_challenges", "DELETE FROM captcha_challenges WHERE chat_id=$1"),
        ("password_challenges", "DELETE FROM password_challenges WHERE chat_id=$1"),
        ("scheduled_messages", "DELETE FROM scheduled_messages WHERE chat_id=$1"),
        ("pinned_messages", "DELETE FROM pinned_messages WHERE chat_id=$1"),
    ]

    for table_name, query_str in tables:
        try:
            await db.execute(query_str, chat_id)
        except Exception as e:
            log.warning(f"[IMPORT_EXPORT] Reset failed on {table_name}: {e}")

    await query.edit_message_text(
        "✅ <b>Group reset complete.</b>\n\n"
        "All settings have been cleared. "
        "The bot will use default settings until you reconfigure.",
        parse_mode="HTML",
    )

    await log_event(
        bot=bot,
        db=db,
        chat_id=chat_id,
        event_type="reset",
        actor=user,
        details={"tables_cleared": len(tables)},
        bot_id=bot.id,
    )
    log.info(f"[IMPORT_EXPORT] Reset | chat={chat_id} by={user.id}")
