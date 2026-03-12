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
import tempfile
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

from pyrogram import Client
from pytgcalls import PyTGCalls
from pytgcalls.types import Update as TGUpdate
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
import yt_dlp

from config import settings

log = logging.getLogger("music_worker")

os.makedirs(settings.MUSIC_DOWNLOAD_DIR, exist_ok=True)


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

    def __init__(self, pyrogram_client: Client, bot_id: int, db=None):
        self.client = pyrogram_client
        self.bot_id = bot_id
        self.db = db
        self.calls = PyTGCalls(pyrogram_client)
        self._sessions: dict[int, GroupSession] = {}
        self._started = False

        # Register PyTGCalls stream end callback
        @self.calls.on_stream_end()
        async def _on_end(_, update: TGUpdate):
            await self._handle_stream_end(update.chat_id)

        log.info(f"[MUSIC] MusicWorker created | bot={bot_id}")

    async def start(self):
        """Start PyTGCalls. Call once after Pyrogram client starts."""
        if not self._started:
            await self.calls.start()
            self._started = True
            log.info(f"[MUSIC] PyTGCalls started | bot={self.bot_id}")

    # ── PUBLIC API ────────────────────────────────────────────────────────

    async def play(
        self,
        chat_id: int,
        url: str,
        requested_by: int,
        requested_by_name: str,
        playnow: bool = False,
        on_track_end: Optional[Callable[..., Awaitable]] = None
    ) -> MusicResult:
        """
        Add a track to the queue (or play immediately if playnow=True).
        If nothing is playing, starts immediately.
        on_track_end: async callback(chat_id, next_track_or_None)
                      PTB bot uses this to update the now-playing message.
        """
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
        return MusicResult(ok=True, data={
            "queued": True,
            "position": pos,
            "title": track.title,
            "duration": track.duration,
        })

    async def pause(self, chat_id: int) -> MusicResult:
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
        session = self._sessions.get(chat_id)
        if not session or (not session.is_playing and not session.is_paused):
            return MusicResult(ok=False, error="Nothing is playing.")
        log.info(f"[MUSIC] Skip | chat={chat_id}")
        return await self._play_next(chat_id)

    async def stop(self, chat_id: int) -> MusicResult:
        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=False, error="Nothing is playing.")
        session.queue.clear()
        await self._leave_vc(chat_id)
        self._sessions.pop(chat_id, None)
        log.info(f"[MUSIC] Stopped | chat={chat_id}")
        return MusicResult(ok=True)

    async def set_volume(self, chat_id: int, volume: int) -> MusicResult:
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
        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=False, error="Nothing is playing.")
        session.is_looping = not session.is_looping
        return MusicResult(ok=True, data={"looping": session.is_looping})

    def get_queue(self, chat_id: int) -> MusicResult:
        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=True, data={"queue": [], "current": None})
        return MusicResult(ok=True, data={
            "current": {
                "title": session.current.title,
                "duration": session.current.duration,
                "source": session.current.source,
            } if session.current else None,
            "queue": [
                {"title": t.title, "duration": t.duration, "source": t.source}
                for t in session.queue
            ],
            "is_looping": session.is_looping,
            "volume": session.volume,
        })

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
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }],
        }

        try:
            loop = asyncio.get_event_loop()

            def _extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info

            info = await loop.run_in_executor(None, _extract)

            duration = info.get("duration", 0)
            if duration > settings.MUSIC_MAX_DURATION:
                return MusicResult(
                    ok=False,
                    error=f"Track too long ({duration//60}min). Max is {settings.MUSIC_MAX_DURATION//60}min."
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

            return MusicResult(ok=True, data={
                "url": url,
                "title": info.get("title", "Unknown"),
                "duration": duration,
                "thumbnail": info.get("thumbnail", ""),
                "source": source,
                "file_path": file_path,
            })

        except Exception as e:
            log.warning(f"[MUSIC] Resolve failed | url={url[:60]} error={e}")
            return MusicResult(ok=False, error=f"Could not load track: {e}")

    async def _play_next(self, chat_id: int) -> MusicResult:
        """Pop next track from queue and stream it. Auto-leave if queue empty."""
        session = self._sessions.get(chat_id)
        if not session:
            return MusicResult(ok=False, error="No session.")

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
                    chat_id,
                    AudioPiped(track.file_path, HighQualityAudio()),
                    stream_type=None
                )
            except Exception:
                # Already in VC — change stream instead
                await self.calls.change_stream(
                    chat_id,
                    AudioPiped(track.file_path, HighQualityAudio())
                )

            log.info(f"[MUSIC] Streaming | chat={chat_id} title={track.title}")
            return MusicResult(ok=True, data={
                "playing": True,
                "title": track.title,
                "duration": track.duration,
                "thumbnail": track.thumbnail,
                "source": track.source,
                "queue_len": len(session.queue),
            })

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
                session_ref.idle_task = asyncio.create_task(
                    self._idle_leave(chat_id)
                )

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
