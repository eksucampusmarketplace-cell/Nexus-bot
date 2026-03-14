"""
bot/userbot/music_voice.py

Handles forwarded voice messages as music input.
When a user forwards a voice message to the group while replying
to a /play command (or sends /play while replying to a voice message),
this module downloads the OGG file and converts it to MP3 for streaming.

Returns a TrackInfo-compatible dict for MusicWorker.play().
"""

import os
import asyncio
import logging
from telegram import Message
from config import settings

log = logging.getLogger("music_voice")


async def resolve_voice_message(message: Message, bot) -> dict | None:
    """
    Download a voice message and convert to MP3.
    Returns dict with url, title, duration, thumbnail, source, file_path
    or None if failed.
    """
    voice = message.voice
    if not voice:
        return None

    duration = voice.duration or 0

    if duration > settings.MUSIC_MAX_DURATION:
        return None

    try:
        file = await bot.get_file(voice.file_id)
        ogg_path = os.path.join(settings.MUSIC_DOWNLOAD_DIR, f"voice_{voice.file_unique_id}.ogg")
        mp3_path = ogg_path.replace(".ogg", ".mp3")

        await file.download_to_drive(ogg_path)

        # Convert OGG -> MP3 via ffmpeg
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: os.system(f"ffmpeg -y -i {ogg_path} -q:a 0 {mp3_path} -loglevel quiet")
        )
        os.remove(ogg_path)

        sender = message.from_user
        title = f"Voice message from {sender.first_name}" if sender else "Voice message"

        log.info(f"[MUSIC] Voice resolved | duration={duration}s")
        return {
            "url": f"voice:{voice.file_unique_id}",
            "title": title,
            "duration": duration,
            "thumbnail": "",
            "source": "voice",
            "file_path": mp3_path,
        }
    except Exception as e:
        log.warning(f"[MUSIC] Voice resolve failed | error={e}")
        return None
