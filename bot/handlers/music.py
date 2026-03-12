"""
bot/handlers/music.py (refactored for microservice)

Music commands now push jobs to Redis instead of calling MusicWorker directly.
Waits up to MUSIC_SERVICE_TIMEOUT seconds for result.
If music service is down: shows friendly error, never crashes bot.

Job dispatch helper: _dispatch(context, chat_id, action, **kwargs)
Status reader:       _get_status(context, chat_id)
Service check:       _service_alive(context)
"""

import asyncio
import json
import logging
import time
import uuid

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler, filters
)
from telegram.constants import ParseMode

from config import settings

log = logging.getLogger("music_cmd")

SOURCE_EMOJI = {
    "youtube": "▶️ YouTube", "soundcloud": "🔶 SoundCloud",
    "spotify": "🟢 Spotify",  "direct": "🔗 Direct",
    "voice": "🎤 Voice", "unknown": "🎵 Audio",
}


async def _redis(context):
    return context.bot_data.get("redis")


async def _service_alive(context) -> bool:
    """Check music service heartbeat in Redis."""
    r = await _redis(context)
    if not r:
        return False
    return bool(await r.exists("music:worker:heartbeat"))


async def _dispatch(context, chat_id: int, action: str, **kwargs) -> dict:
    """
    Push job to music service and wait for result.
    Returns result dict or {"ok": False, "error": "..."} on timeout/error.
    """
    r = await _redis(context)
    if not r:
        return {"ok": False, "error": "Music service unavailable."}

    if not await _service_alive(context):
        return {"ok": False, "error": "🎵 Music service is currently offline. Try again shortly."}

    bot_id = context.bot.id
    job_id = str(uuid.uuid4())
    job    = {
        "job_id":        job_id,
        "action":        action,
        "chat_id":       chat_id,
        "bot_id":        bot_id,
        "created_at":    time.time(),
        "reply_bot_token": (await context.bot.get_me()).token
        if hasattr(context.bot, 'token') else "",
        **kwargs
    }

    await r.lpush(f"music:dispatch:{bot_id}", json.dumps(job))

    # Wait for result
    deadline = time.time() + settings.MUSIC_SERVICE_TIMEOUT
    while time.time() < deadline:
        raw = await r.get(f"music:result:{job_id}")
        if raw:
            return json.loads(raw)
        await asyncio.sleep(0.25)

    return {"ok": False, "error": "Music service timed out. Try again."}


async def _get_status(context, chat_id: int) -> dict:
    """Get current playback status from Redis."""
    r = await _redis(context)
    if not r:
        return {}
    bot_id = context.bot.id
    data   = await r.hgetall(f"music:status:{chat_id}:{bot_id}")
    return data or {}


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE, playnow=False):
    chat    = update.effective_chat
    user    = update.effective_user
    message = update.effective_message
    db      = context.bot_data.get("db")

    # Handle voice message reply
    url = None
    if message.reply_to_message and message.reply_to_message.voice:
        from bot.userbot.music_voice import resolve_voice_message
        track_data = await resolve_voice_message(message.reply_to_message, context.bot)
        if track_data:
            url = track_data["url"]

    if not url:
        url = " ".join(context.args) if context.args else None
        if not url:
            await message.reply_text(
                "❓ <b>Usage:</b> /play <YouTube, Spotify, SoundCloud URL or direct link>\n"
                "Or reply to a voice message with /play",
                parse_mode=ParseMode.HTML
            )
            return

    loading = await message.reply_text("⏳ Loading track...")

    result = await _dispatch(
        context, chat.id, "play",
        url=url,
        playnow=playnow,
        requested_by=user.id,
        requested_by_name=user.full_name,
        reply_chat_id=chat.id,
    )

    await loading.delete()

    if not result.get("ok"):
        await message.reply_text(f"❌ {result.get('error', 'Failed')}")
        return

    data = result.get("data", {})
    if data.get("queued"):
        await message.reply_text(
            f"📋 Added to queue (position {data['position']})\n"
            f"<b>{data['title']}</b>",
            parse_mode=ParseMode.HTML
        )
    # Now-playing card is sent by music service directly


async def cmd_pause(update, context):
    result = await _dispatch(context, update.effective_chat.id, "pause")
    await update.effective_message.reply_text(
        "⏸ Paused." if result.get("ok") else f"❌ {result.get('error')}"
    )

async def cmd_resume(update, context):
    result = await _dispatch(context, update.effective_chat.id, "resume")
    await update.effective_message.reply_text(
        "▶️ Resumed." if result.get("ok") else f"❌ {result.get('error')}"
    )

async def cmd_skip(update, context):
    result = await _dispatch(context, update.effective_chat.id, "skip")
    await update.effective_message.reply_text(
        "⏭ Skipped." if result.get("ok") else f"❌ {result.get('error')}"
    )

async def cmd_stop(update, context):
    result = await _dispatch(context, update.effective_chat.id, "stop")
    await update.effective_message.reply_text(
        "⏹ Stopped." if result.get("ok") else f"❌ {result.get('error')}"
    )

async def cmd_volume(update, context):
    try:
        vol = int(context.args[0])
    except (IndexError, ValueError):
        await update.effective_message.reply_text("❓ Usage: /volume <0-200>")
        return
    result = await _dispatch(context, update.effective_chat.id, "volume", volume=vol)
    await update.effective_message.reply_text(
        f"🔊 Volume: {result['data']['volume']}%" if result.get("ok") else f"❌ {result.get('error')}"
    )

async def cmd_loop(update, context):
    result = await _dispatch(context, update.effective_chat.id, "loop")
    if result.get("ok"):
        state = "on 🔁" if result["data"]["looping"] else "off"
        await update.effective_message.reply_text(f"Loop {state}")
    else:
        await update.effective_message.reply_text(f"❌ {result.get('error')}")

async def cmd_queue(update, context):
    status = await _get_status(context, update.effective_chat.id)
    if not status:
        await update.effective_message.reply_text("📋 Queue is empty.")
        return
    current = status.get("current_title", "")
    queue_len = int(status.get("queue_length", 0))
    lines = []
    if current:
        lines.append(f"🎵 <b>Now:</b> {current}")
    lines.append(f"📋 {queue_len} track(s) in queue")
    await update.effective_message.reply_text(
        "\n".join(lines) + f"\n\n⚡ {settings.BOT_DISPLAY_NAME}",
        parse_mode=ParseMode.HTML
    )

async def music_callback(update, context):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split(":")
    action = parts[1]
    chat_id = int(parts[2])

    if action in ("pause", "skip", "stop", "loop"):
        await _dispatch(context, chat_id, action)
    elif action == "queue":
        status = await _get_status(context, chat_id)
        qlen   = status.get("queue_length", "0")
        await query.answer(f"Queue: {qlen} track(s)", show_alert=True)
        return
    elif action == "vol":
        await query.answer("Use /volume <0-200>", show_alert=True)
        return


async def _get_bot_owner(context, db) -> int:
    """Get owner_id for current bot."""
    if not db:
        return settings.OWNER_ID
    bot_id = context.bot.id
    row = await db.fetchrow(
        "SELECT owner_id FROM clone_bots WHERE bot_id=$1", bot_id
    )
    return row["owner_id"] if row else settings.OWNER_ID


music_handlers = [
    CommandHandler("play",      cmd_play),
    CommandHandler("playnow",   lambda u,c: cmd_play(u,c,playnow=True)),
    CommandHandler("pause",     cmd_pause),
    CommandHandler("resume",    cmd_resume),
    CommandHandler("skip",      cmd_skip),
    CommandHandler("stop",      cmd_stop),
    CommandHandler("queue",     cmd_queue),
    CommandHandler("volume",    cmd_volume),
    CommandHandler("loop",      cmd_loop),
    CallbackQueryHandler(music_callback, pattern=r"^music:"),
]
