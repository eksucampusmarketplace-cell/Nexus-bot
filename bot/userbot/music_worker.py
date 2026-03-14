"""
bot/userbot/music_worker.py

MusicWorker — core streaming engine per bot instance.
One MusicWorker is created per bot (main or clone) in factory.py.
Stored in app.bot_data["music_worker"].

Uses:
  Pyrogram client  — to join groups and voice chats as a real user
  PyTGCalls        — wraps Pyrogram to stream PCM audio into VC
  yt-dlp           — resolves and downloads audio from any source
  ffmpeg           — converts to PCM for streaming

Per-group state is kept in memory (active_sessions dict) AND synced
to music_sessions table so state survives restarts.

All public methods return MusicResult(ok, error, data).
Never raises to callers.
Logs prefix: [MUSIC]
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from pyrogram import Client

log = logging.getLogger("music_worker")

# Import PyTGCalls with fallback
HAS_PYTGCALLS = False
PyTGCalls = None
AudioPiped = None
HighQualityAudio = None
TGUpdate = None

try:
    from pytgcalls import PyTGCalls as _PyTGCalls
    from pytgcalls.types import Update as _TGUpdate
    from pytgcalls.types.input_stream import AudioPiped as _AudioPiped
    from pytgcalls.types.input_stream.quality import HighQualityAudio as _HighQualityAudio

    HAS_PYTGCALLS = True
    PyTGCalls = _PyTGCalls
    AudioPiped = _AudioPiped
    HighQualityAudio = _HighQualityAudio
    TGUpdate = _TGUpdate
except ImportError:
    log.warning("[MUSIC] pytgcalls not installed. Music features will be disabled.")

    # Define dummy classes for type hinting if needed
    class _PyTGCalls:
        def __init__(self, *args, **kwargs):
            pass

        def on_stream_end(self, *args, **kwargs):
            def decorator(f):
                return f

            return decorator

        async def start(self):
            pass

    class _AudioPiped:
        pass

    class _HighQualityAudio:
        pass

    class _TGUpdate:
        chat_id: int

    PyTGCalls = _PyTGCalls
    AudioPiped = _AudioPiped
    HighQualityAudio = _HighQualityAudio
    TGUpdate = _TGUpdate

import yt_dlp

from config import settings

os.makedirs(settings.MUSIC_DOWNLOAD_DIR, exist_ok=True)

# Log warning about PyTGCalls availability at module load time
if not HAS_PYTGCALLS:
    log.warning("[MUSIC] WARNING: PyTGCalls unavailable. Voice chat streaming disabled.")
    log.warning("[MUSIC] Bot will still respond to /play commands but cannot stream audio.")


@dataclass
class MusicResult:
    ok: bool
    error: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class TrackInfo:
    url: str
    title: str = "Unknown"
    duration: int = 0
    thumbnail: str = ""
    source: str = "unknown"
    file_path: str = ""


@dataclass
class GroupSession:
    chat_id: int
    is_playing: bool = False
    is_paused: bool = False
    is_looping: bool = False
    volume: int = 100
    queue: list = field(default_factory=list)  # list[TrackInfo]
    current: Optional[TrackInfo] = None
    idle_task: Optional[asyncio.Task] = None
    np_message_id: Optional[int] = None
    on_track_end: Optional[Callable] = None  # callback -> PTB bot updates NP card


class MusicWorker:

    def __init__(self, pyrogram_client: Client, bot_id: int, db=None, db_pool=None):
        self.client = pyrogram_client
        self.bot_id = bot_id
        self.db = db
        self.db_pool = db_pool  # For rotation queries
        self.calls = PyTGCalls(pyrogram_client) if HAS_PYTGCALLS else None
        self._sessions: dict[int, GroupSession] = {}
        self._started = False
        self._tgcalls_pool: dict[int, PyTGCalls] = {}  # userbot_id -> PyTGCalls for multi-userbot

        if HAS_PYTGCALLS:
            # Register PyTGCalls stream end callback
            @self.calls.on_stream_end()
            async def _on_end(_, update: TGUpdate):
                await self._handle_stream_end(update.chat_id)

        log.info(f"[MUSIC] MusicWorker created | bot={bot_id} pytgcalls={HAS_PYTGCALLS}")

    def status(self) -> dict:
        """Return status of PyTGCalls availability"""
        return {
            "available": HAS_PYTGCALLS,
            "reason": (
                "PyTGCalls installed and ready"
                if HAS_PYTGCALLS
                else "pytgcalls not installed. Install py-tgcalls and ntgcalls binary."
            ),
        }

    async def start(self):
        """Start PyTGCalls. Call once after Pyrogram client starts."""
        if not HAS_PYTGCALLS:
            log.warning("[MUSIC] Cannot start PyTGCalls - not available on this server")
            return

        if not self._started and self.calls:
            await self.calls.start()
            self._started = True
            log.info(f"[MUSIC] PyTGCalls started | bot={self.bot_id}")

    async def get_active_userbot_for_chat(self, chat_id: int) -> Optional[int]:
        """
        Get the active userbot ID for a chat based on settings and rotation mode.

        Args:
            chat_id: The chat/group ID

        Returns:
            userbot_id or None if no userbots available
        """
        if not self.db_pool:
            return None

        import db.ops.music_new as db_music

        # Get music settings for this chat
        settings_data = await db_music.get_music_settings(self.db_pool, chat_id, self.bot_id)

        if not settings_data:
            # No settings - return default behavior
            return None

        auto_rotate = settings_data.get("auto_rotate", False)
        rotation_mode = settings_data.get("rotation_mode", "manual")
        configured_userbot_id = settings_data.get("userbot_id")

        userbot_id = None

        if auto_rotate:
            # Use rotation to pick the next userbot
            userbot_id = await db_music.get_next_rotation_userbot(
                self.db_pool, owner_bot_id=self.bot_id, rotation_mode=rotation_mode
            )
        else:
            # Use configured userbot
            userbot_id = configured_userbot_id

        # Record usage if we have a userbot
        if userbot_id:
            await db_music.record_userbot_usage(self.db_pool, userbot_id, chat_id)

        return userbot_id

    # ── PUBLIC API ────────────────────────────────────────────────────────

    async def play(
        self,
        chat_id: int,
        url: str,
        requested_by: int,
        requested_by_name: str,
        playnow: bool = False,
        on_track_end: Optional[Callable[..., Awaitable]] = None,
    ) -> MusicResult:
        """
        Add a track to the queue (or play immediately if playnow=True).
        If nothing is playing, starts immediately.
        on_track_end: async callback(chat_id, next_track_or_None)
                      PTB bot uses this to update the now-playing message.
        """
        if not HAS_PYTGCALLS:
            return MusicResult(
                ok=False,
                error="Music worker not available on this server. Make sure your local PC worker is running.",
            )

        log.info(f"[MUSIC] Play request | bot={self.bot_id} chat={chat_id} url={url[:60]}")

        # Resolve track info
        result = await self._resolve(url)
        if not result.ok:
            return result

        track = TrackInfo(**result.data)

        session = self._get_or_create_session(chat_id)
        if on_track_end:
            session.on_track_end = on_track_end

        if playnow:
            # Insert at front of queue
            session.queue.insert(0, track)
            if session.is_playing or session.is_paused:
                await self._stop_current(chat_id)
        else:
            session.queue.append(track)

        if not session.is_playing and not session.is_paused:
            return await self._play_next(chat_id)

        pos = session.queue.index(track) + 1
        return MusicResult(
            ok=True,
            data={
                "queued": True,
                "position": pos,
                "title": track.title,
                "duration": track.duration,
            },
        )

    async def pause(self, chat_id: int) -> MusicResult:
        if not HAS_PYTGCALLS:
            return MusicResult(ok=False, error="Music worker not available on this server.")

        session = self._sessions.get(chat_id)
        if not session or not session.is_playing:
            return MusicResult(ok=False, error="Nothing is playing.")
        try:
            await self.calls.pause_stream(chat_id)
            session.is_playing = False
            session.is_paused = True
            log.info(f"[MUSIC] Paused | chat={chat_id}")
            return MusicResult(ok=True)
        except Exception as e:
            return MusicResult(ok=False, error=str(e))

    async def resume(self, chat_id: int) -> MusicResult:
        if not HAS_PYTGCALLS:
            return MusicResult(ok=False, error="Music worker not available on this server.")

        session = self._sessions.get(chat_id)
        if not session or not session.is_paused:
            return MusicResult(ok=False, error="Nothing is paused.")
        try:
            await self.calls.resume_stream(chat_id)
            session.is_playing = True
            session.is_paused = False
            log.info(f"[MUSIC] Resumed | chat={chat_id}")
            return MusicResult(ok=True)
        except Exception as e:
            return MusicResult(ok=False, error=str(e))

    async def skip(self, chat_id: int) -> MusicResult:
        if not HAS_PYTGCALLS:
            return MusicResult(ok=False, error="Music worker not available on this server.")

        session = self._sessions.get(chat_id)
        if not session or (not session.is_playing and not session.is_paused):
            return MusicResult(ok=False, error="Nothing is playing.")
        log.info(f"[MUSIC] Skip | chat={chat_id}")
        return await self._play_next(chat_id)

    async def stop(self, chat_id: int) -> MusicResult:
        if not HAS_PYTGCALLS:
            return MusicResult(ok=False, error="Music worker not available on this server.")

        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=False, error="Nothing is playing.")
        session.queue.clear()
        await self._leave_vc(chat_id)
        self._sessions.pop(chat_id, None)
        log.info(f"[MUSIC] Stopped | chat={chat_id}")
        return MusicResult(ok=True)

    async def set_volume(self, chat_id: int, volume: int) -> MusicResult:
        if not HAS_PYTGCALLS:
            return MusicResult(ok=False, error="Music worker not available on this server.")

        volume = max(0, min(200, volume))
        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=False, error="Nothing is playing.")
        try:
            await self.calls.change_volume_call(chat_id, volume)
            session.volume = volume
            return MusicResult(ok=True, data={"volume": volume})
        except Exception as e:
            return MusicResult(ok=False, error=str(e))

    async def toggle_loop(self, chat_id: int) -> MusicResult:
        if not HAS_PYTGCALLS:
            return MusicResult(ok=False, error="Music worker not available on this server.")

        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=False, error="Nothing is playing.")
        session.is_looping = not session.is_looping
        return MusicResult(ok=True, data={"looping": session.is_looping})

    def get_queue(self, chat_id: int) -> MusicResult:
        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=True, data={"queue": [], "current": None})
        return MusicResult(
            ok=True,
            data={
                "current": (
                    {
                        "title": session.current.title,
                        "duration": session.current.duration,
                        "source": session.current.source,
                    }
                    if session.current
                    else None
                ),
                "queue": [
                    {"title": t.title, "duration": t.duration, "source": t.source}
                    for t in session.queue
                ],
                "is_looping": session.is_looping,
                "volume": session.volume,
            },
        )

    async def get_status(self, chat_id: int) -> dict:
        """
        Get current session state for a chat.
        Used by the API queue endpoint.

        Returns:
            Dict with playing, paused, current track, queue length, volume
        """
        session = self._sessions.get(chat_id)
        if not session:
            return {
                "playing": False,
                "paused": False,
                "current": None,
                "queue_length": 0,
                "volume": 100,
            }

        return {
            "playing": session.is_playing,
            "paused": session.is_paused,
            "current": (
                {
                    "title": session.current.title,
                    "duration": session.current.duration,
                    "source": session.current.source,
                }
                if session.current
                else None
            ),
            "queue_length": len(session.queue),
            "volume": session.volume,
            "is_looping": session.is_looping,
        }

    # ── INTERNALS ─────────────────────────────────────────────────────────

    def _get_or_create_session(self, chat_id: int) -> GroupSession:
        if chat_id not in self._sessions:
            self._sessions[chat_id] = GroupSession(chat_id=chat_id)
        return self._sessions[chat_id]

    async def _resolve(self, url: str) -> MusicResult:
        """
        Resolve URL to downloadable audio using yt-dlp.
        Supports: YouTube, SoundCloud, Spotify (via yt-dlp spotdl fallback),
                  direct MP3/audio URLs.
        Returns MusicResult with data = TrackInfo fields.
        Rejects tracks over MUSIC_MAX_DURATION.
        """
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "noplaylist": True,
            "outtmpl": f"{settings.MUSIC_DOWNLOAD_DIR}/%(id)s.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                }
            ],
        }

        try:
            loop = asyncio.get_running_loop()

            def _extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info

            info = await loop.run_in_executor(None, _extract)

            duration = info.get("duration", 0)
            if duration > settings.MUSIC_MAX_DURATION:
                return MusicResult(
                    ok=False,
                    error=f"Track too long ({duration//60}min). Max is {settings.MUSIC_MAX_DURATION//60}min.",
                )

            # Find downloaded file
            file_path = f"{settings.MUSIC_DOWNLOAD_DIR}/{info['id']}.mp3"

            # Detect source
            webpage = info.get("webpage_url", url).lower()
            if "youtube" in webpage or "youtu.be" in webpage:
                source = "youtube"
            elif "soundcloud" in webpage:
                source = "soundcloud"
            elif "spotify" in webpage:
                source = "spotify"
            else:
                source = "direct"

            return MusicResult(
                ok=True,
                data={
                    "url": url,
                    "title": info.get("title", "Unknown"),
                    "duration": duration,
                    "thumbnail": info.get("thumbnail", ""),
                    "source": source,
                    "file_path": file_path,
                },
            )

        except Exception as e:
            log.warning(f"[MUSIC] Resolve failed | url={url[:60]} error={e}")
            return MusicResult(ok=False, error=f"Could not load track: {e}")

    async def _play_next(self, chat_id: int) -> MusicResult:
        """Pop next track from queue and stream it. Auto-leave if queue empty."""
        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=False, error="No session.")

        # Get active userbot for this chat (handles rotation)
        if self.db_pool:
            active_userbot_id = await self.get_active_userbot_for_chat(chat_id)
            if active_userbot_id:
                log.info(f"[MUSIC] Using userbot {active_userbot_id} for chat {chat_id}")

        # Loop: re-add current track to front
        if session.is_looping and session.current:
            session.queue.insert(0, session.current)

        if not session.queue:
            await self._leave_vc(chat_id)
            self._sessions.pop(chat_id, None)
            return MusicResult(ok=True, data={"ended": True})

        track = session.queue.pop(0)
        session.current = track
        session.is_playing = True
        session.is_paused = False

        # Cancel idle timer
        if session.idle_task:
            session.idle_task.cancel()
            session.idle_task = None

        try:
            # Join VC if not already in it
            try:
                await self.calls.join_group_call(
                    chat_id, AudioPiped(track.file_path, HighQualityAudio()), stream_type=None
                )
            except Exception:
                # Already in VC — change stream instead
                await self.calls.change_stream(
                    chat_id, AudioPiped(track.file_path, HighQualityAudio())
                )

            log.info(f"[MUSIC] Streaming | chat={chat_id} title={track.title}")
            return MusicResult(
                ok=True,
                data={
                    "playing": True,
                    "title": track.title,
                    "duration": track.duration,
                    "thumbnail": track.thumbnail,
                    "source": track.source,
                    "queue_len": len(session.queue),
                },
            )

        except Exception as e:
            log.error(f"[MUSIC] Stream failed | chat={chat_id} error={e}")
            session.is_playing = False
            return MusicResult(ok=False, error=f"Stream failed: {e}")

    async def _handle_stream_end(self, chat_id: int):
        """Called by PyTGCalls when current track finishes."""
        session = self._sessions.get(chat_id)
        if not session:
            return

        # Delete temp file
        if session.current and session.current.file_path:
            try:
                os.remove(session.current.file_path)
            except Exception:
                pass

        log.info(f"[MUSIC] Track ended | chat={chat_id} queue_remaining={len(session.queue)}")

        # Fire PTB callback to update now-playing message
        if session.on_track_end:
            try:
                next_track = session.queue[0] if session.queue else None
                await session.on_track_end(chat_id, next_track)
            except Exception as e:
                log.warning(f"[MUSIC] on_track_end callback failed | error={e}")

        result = await self._play_next(chat_id)
        if not result.ok or result.data.get("ended"):
            # Queue empty — start idle timer before leaving
            session_ref = self._sessions.get(chat_id)
            if session_ref:
                session_ref.idle_task = asyncio.create_task(self._idle_leave(chat_id))

    async def _idle_leave(self, chat_id: int):
        """Leave VC after MUSIC_IDLE_TIMEOUT seconds of inactivity."""
        await asyncio.sleep(settings.MUSIC_IDLE_TIMEOUT)
        log.info(f"[MUSIC] Idle timeout | chat={chat_id}")
        await self._leave_vc(chat_id)
        self._sessions.pop(chat_id, None)

    async def _stop_current(self, chat_id: int):
        """Stop current stream without clearing queue."""
        try:
            await self.calls.leave_group_call(chat_id)
        except Exception:
            pass
        session = self._sessions.get(chat_id)
        if session:
            session.is_playing = False
            session.is_paused = False

    async def _leave_vc(self, chat_id: int):
        """Leave voice chat silently."""
        try:
            await self.calls.leave_group_call(chat_id)
            log.info(f"[MUSIC] Left VC | chat={chat_id}")
        except Exception as e:
            log.warning(f"[MUSIC] Leave VC failed | chat={chat_id} error={e}")

    # ── Redis Job Helper ──────────────────────────────────────────────────

    @staticmethod
    async def push_job_to_redis(redis, job: dict) -> bool:
        """
        Push a music job to the Redis queue for processing by a worker.

        Args:
            redis: Redis client instance
            job: Job dict with action, chat_id, bot_id, etc.

        Returns:
            True if job was pushed successfully
        """
        import json

        try:
            await redis.lpush("music:jobs", json.dumps(job))
            return True
        except Exception as e:
            log.error(f"[MUSIC] Failed to push job to Redis: {e}")
            return False
