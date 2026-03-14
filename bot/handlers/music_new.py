"""
bot/handlers/music_new.py

All music commands. Registered on every bot (main + clones) in factory.py.
Requires app.bot_data["music_worker"] to be set.
If music_worker is None (clone has no userbot): show setup instructions.

Commands:
  /play <url or search>     Add to queue. If reply to voice msg: play that.
  /playnow <url>            Skip queue, play immediately
  /pause                    Pause playback
  /resume                   Resume playback
  /skip                     Skip current track
  /stop                     Stop and clear queue
  /queue                    Show current queue
  /volume <0-200>           Set volume
  /loop                     Toggle loop current track
  /musicmode all|admins     Admin only: restrict who can /play

Now-playing card format:
  ┌─────────────────────────────────┐
  │ 🎵 Now Playing                  │
  │ {title}                         │
  │ ⏱ {duration} · 🔊 {volume}%   │
  │ Source: {source emoji}          │
  │                                 │
  │ [⏸ Pause] [⏭ Skip] [⏹ Stop]  │
  │ [🔁 Loop] [📋 Queue] [🔊 Vol]  │
  └─────────────────────────────────┘

Source emojis: YouTube=▶️ SoundCloud=🔶 Spotify=🟢 Direct=🔗 Voice=🎤

Logs prefix: [MUSIC_CMD]
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

from config import settings
import db.ops.music_new as db_music

log = logging.getLogger("music_cmd")

SOURCE_EMOJI = {
    "youtube": "▶️ YouTube",
    "soundcloud": "🔶 SoundCloud",
    "spotify": "🟢 Spotify",
    "direct": "🔗 Direct",
    "voice": "🎤 Voice message",
    "unknown": "🎵 Audio",
}


def _no_worker_message(bot_is_primary: bool) -> str:
    """Shown when a clone bot has no userbot configured."""
    main = settings.MAIN_BOT_USERNAME
    brand = settings.BOT_DISPLAY_NAME
    if bot_is_primary:
        return f"❌ Music worker not available. Contact @{main}.\n\n⚡ {brand}"
    return (
        f"🎵 <b>Music not set up yet</b>\n\n"
        f"To enable music in this bot, the bot owner needs to add "
        f"a userbot account.\n\n"
        f"<b>Bot owner:</b> Open Mini App → Settings → Music → Add Account\n\n"
        f"💡 Or use @{main} directly.\n\n⚡ Powered by {brand}"
    )


def _np_keyboard(chat_id: int, is_paused: bool, is_looping: bool) -> InlineKeyboardMarkup:
    pause_label = "▶️ Resume" if is_paused else "⏸ Pause"
    loop_label = "🔁 Loop ✅" if is_looping else "🔁 Loop"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(pause_label, callback_data=f"music:pause:{chat_id}"),
                InlineKeyboardButton("⏭ Skip", callback_data=f"music:skip:{chat_id}"),
                InlineKeyboardButton("⏹ Stop", callback_data=f"music:stop:{chat_id}"),
            ],
            [
                InlineKeyboardButton(loop_label, callback_data=f"music:loop:{chat_id}"),
                InlineKeyboardButton("📋 Queue", callback_data=f"music:queue:{chat_id}"),
                InlineKeyboardButton("🔊 Vol", callback_data=f"music:vol:{chat_id}"),
            ],
        ]
    )


def _np_text(title: str, duration: int, volume: int, source: str, queue_len: int) -> str:
    mins, secs = divmod(duration, 60)
    dur_str = f"{mins}:{secs:02d}" if duration else "Live"
    src_str = SOURCE_EMOJI.get(source, "🎵 Audio")
    queue_str = f"  ·  📋 {queue_len} in queue" if queue_len else ""
    return (
        f"🎵 <b>Now Playing</b>\n\n"
        f"<b>{title}</b>\n"
        f"⏱ {dur_str}  ·  🔊 {volume}%{queue_str}\n"
        f"{src_str}"
        f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}"
    )


async def _get_worker(context):
    return context.bot_data.get("music_worker")


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE, playnow=False):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    db = context.bot_data.get("db")
    worker = await _get_worker(context)
    is_primary = context.bot_data.get("is_primary", False)

    if not worker:
        await message.reply_text(_no_worker_message(is_primary), parse_mode=ParseMode.HTML)
        return

    # Check play permissions
    if db:
        allowed = await db_music.can_user_play(db, chat.id, context.bot.id, user.id, context.bot)
        if not allowed:
            await message.reply_text("🔒 Only admins can use music commands here.")
            return

    # Check if replying to a voice message
    url = None
    is_voice = False
    if message.reply_to_message and message.reply_to_message.voice:
        from bot.userbot.music_voice import resolve_voice_message

        track_data = await resolve_voice_message(message.reply_to_message, context.bot)
        if track_data:
            is_voice = True
            # Inject pre-resolved track directly
            url = track_data["url"]

    if not is_voice:
        url = " ".join(context.args) if context.args else None
        if not url:
            cmd_name = "playnow" if playnow else "play"
            await message.reply_text(
                f"❓ <b>Usage:</b> <code>/{cmd_name} &lt;URL or search query&gt;</code>\n\n"
                f"<b>Supported sources:</b>\n"
                f"• YouTube URL\n"
                f"• Spotify URL\n"
                f"• SoundCloud URL\n"
                f"• Direct audio link\n\n"
                f"<b>Or:</b> Reply to a voice message with <code>/{cmd_name}</code>\n\n"
                f"Examples:\n"
                f"<code>/{cmd_name} https://youtube.com/watch?v=...</code>\n"
                f"<code>/{cmd_name} Never Gonna Give You Up</code>",
                parse_mode=ParseMode.HTML,
            )
            return

    # Show loading indicator
    loading_msg = await message.reply_text("⏳ Loading track...")

    async def on_track_end(chat_id, next_track):
        """Update now-playing message when track changes."""
        session = worker._sessions.get(chat_id)
        if not session:
            return
        try:
            if next_track:
                text = _np_text(
                    next_track.title,
                    next_track.duration,
                    session.volume,
                    next_track.source,
                    len(session.queue),
                )
                kb = _np_keyboard(chat_id, session.is_paused, session.is_looping)
                if session.np_message_id:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=session.np_message_id,
                        text=text,
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML,
                    )
            else:
                if session.np_message_id:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=session.np_message_id,
                        text=f"✅ Queue finished.\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}",
                        parse_mode=ParseMode.HTML,
                    )
        except Exception as e:
            log.warning(f"[MUSIC_CMD] NP update failed | error={e}")

    result = await worker.play(
        chat_id=chat.id,
        url=url,
        requested_by=user.id,
        requested_by_name=user.full_name,
        playnow=playnow,
        on_track_end=on_track_end,
    )

    await loading_msg.delete()

    if not result.ok:
        await message.reply_text(f"❌ {result.error}")
        return

    data = result.data

    if data.get("queued"):
        await message.reply_text(
            f"📋 Added to queue (position {data['position']})\n" f"<b>{data['title']}</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Now playing card
    session = worker._sessions.get(chat.id)
    text = _np_text(
        data["title"],
        data["duration"],
        session.volume if session else 100,
        data["source"],
        data.get("queue_len", 0),
    )
    kb = _np_keyboard(chat.id, False, False)
    np_msg = await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    if session:
        session.np_message_id = np_msg.message_id


async def cmd_playnow(update, context):
    await cmd_play(update, context, playnow=True)


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker = await _get_worker(context)
    if not worker:
        return
    result = await worker.pause(update.effective_chat.id)
    session = worker._sessions.get(update.effective_chat.id)
    if result.ok and session and session.np_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=session.np_message_id,
                reply_markup=_np_keyboard(update.effective_chat.id, True, session.is_looping),
            )
        except Exception:
            pass
    await update.effective_message.reply_text("⏸ Paused." if result.ok else f"❌ {result.error}")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker = await _get_worker(context)
    if not worker:
        return
    result = await worker.resume(update.effective_chat.id)
    await update.effective_message.reply_text("▶️ Resumed." if result.ok else f"❌ {result.error}")


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker = await _get_worker(context)
    if not worker:
        return
    result = await worker.skip(update.effective_chat.id)
    await update.effective_message.reply_text(f"⏭ Skipped." if result.ok else f"❌ {result.error}")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker = await _get_worker(context)
    if not worker:
        return
    result = await worker.stop(update.effective_chat.id)
    await update.effective_message.reply_text(
        "⏹ Stopped and queue cleared." if result.ok else f"❌ {result.error}"
    )


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker = await _get_worker(context)
    if not worker:
        return
    result = worker.get_queue(update.effective_chat.id)
    data = result.data
    current = data.get("current")
    queue = data.get("queue", [])

    if not current and not queue:
        await update.effective_message.reply_text("📋 Queue is empty.")
        return

    lines = []
    if current:
        mins, secs = divmod(current["duration"], 60)
        lines.append(f"🎵 <b>Now:</b> {current['title']} ({mins}:{secs:02d})")
    for i, t in enumerate(queue[:10], 1):
        mins, secs = divmod(t["duration"], 60)
        lines.append(f"{i}. {t['title']} ({mins}:{secs:02d})")
    if len(queue) > 10:
        lines.append(f"...and {len(queue)-10} more")

    loop_str = "🔁 Looping on" if data.get("is_looping") else ""
    await update.effective_message.reply_text(
        "📋 <b>Queue</b>\n\n"
        + "\n".join(lines)
        + (f"\n\n{loop_str}" if loop_str else "")
        + f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker = await _get_worker(context)
    if not worker:
        return
    try:
        vol = int(context.args[0])
    except (IndexError, ValueError):
        await update.effective_message.reply_text(
            "❓ <b>Usage:</b> <code>/volume &lt;0-200&gt;</code>\n\n"
            "Set the playback volume.\n\n"
            "Examples:\n"
            "<code>/volume 50</code> - Half volume\n"
            "<code>/volume 100</code> - Full volume\n"
            "<code>/volume 150</code> - 150% (loud)\n\n"
            "<i>Default is 100%</i>",
            parse_mode=ParseMode.HTML,
        )
        return
    if vol < 0 or vol > 200:
        await update.effective_message.reply_text(
            "❌ Volume must be between 0 and 200.", parse_mode=ParseMode.HTML
        )
        return
    result = await worker.set_volume(update.effective_chat.id, vol)
    await update.effective_message.reply_text(
        f"🔊 Volume set to {result.data.get('volume')}%" if result.ok else f"❌ {result.error}"
    )


async def cmd_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker = await _get_worker(context)
    if not worker:
        return
    result = await worker.toggle_loop(update.effective_chat.id)
    state = "on 🔁" if result.data.get("looping") else "off"
    await update.effective_message.reply_text(
        f"Loop {state}" if result.ok else f"❌ {result.error}"
    )


async def cmd_musicmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only: /musicmode all|admins"""
    user = update.effective_user
    chat = update.effective_chat
    db = context.bot_data.get("db")

    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status not in ("administrator", "creator"):
        await update.effective_message.reply_text("❌ Admins only.")
        return

    mode = (context.args[0] if context.args else "").lower()
    if mode not in ("all", "admins"):
        await update.effective_message.reply_text("❓ Usage: /musicmode all|admins")
        return

    if db:
        await db_music.upsert_music_settings(db, chat.id, context.bot.id, play_mode=mode)

    label = "Everyone" if mode == "all" else "Admins only"
    await update.effective_message.reply_text(
        f"🎵 Music access: <b>{label}</b>", parse_mode=ParseMode.HTML
    )


# Inline button callbacks
async def music_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    chat_id = int(parts[2])
    worker = await _get_worker(context)
    if not worker:
        return

    if action == "pause":
        session = worker._sessions.get(chat_id)
        if session and session.is_paused:
            await worker.resume(chat_id)
        else:
            await worker.pause(chat_id)
    elif action == "skip":
        await worker.skip(chat_id)
    elif action == "stop":
        await worker.stop(chat_id)
        await query.edit_message_text(
            f"⏹ Stopped.\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}", parse_mode=ParseMode.HTML
        )
        return
    elif action == "loop":
        await worker.toggle_loop(chat_id)
    elif action == "queue":
        result = worker.get_queue(chat_id)
        queue = result.data.get("queue", [])
        text = "\n".join(f"{i+1}. {t['title']}" for i, t in enumerate(queue[:5])) or "Empty"
        await query.answer(f"Queue:\n{text}", show_alert=True)
        return
    elif action == "vol":
        await query.answer("Use /volume <0-200> to change volume.", show_alert=True)
        return

    # Refresh NP keyboard
    session = worker._sessions.get(chat_id)
    if session and session.current:
        try:
            await query.edit_message_reply_markup(
                reply_markup=_np_keyboard(chat_id, session.is_paused, session.is_looping)
            )
        except Exception:
            pass


# ── Handler objects ───────────────────────────────────────────────────────
music_handlers = [
    CommandHandler("play", cmd_play),
    CommandHandler("playnow", cmd_playnow),
    CommandHandler("pause", cmd_pause),
    CommandHandler("resume", cmd_resume),
    CommandHandler("skip", cmd_skip),
    CommandHandler("stop", cmd_stop),
    CommandHandler("queue", cmd_queue),
    CommandHandler("volume", cmd_volume),
    CommandHandler("loop", cmd_loop),
    CommandHandler("musicmode", cmd_musicmode),
    CallbackQueryHandler(music_callback, pattern=r"^music:"),
]
