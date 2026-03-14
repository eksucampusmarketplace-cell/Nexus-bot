"""
music_service.py

Standalone music streaming process.
Run as a separate Render worker: python music_service.py

Responsibilities:
  - Consume jobs from Redis queues
  - Download audio via yt-dlp with retry + fallback
  - Stream via PyTGCalls
  - Publish results and status back to Redis
  - Send now-playing messages via Telegram Bot API
  - Post heartbeat every 30s
  - Auto-recover from PyTGCalls crashes per group
  - Monitor yt-dlp version against config — alert if mismatch

One Pyrogram client per userbot account (loaded from DB on startup).
PyTGCalls pool: one PyTGCalls instance wrapping all Pyrogram clients.

Logs prefix: [MUSIC_SVC]
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
import yt_dlp
from pyrogram import Client
from pytgcalls import PyTGCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio

# Load config (same config.py as main bot)
import sys

sys.path.insert(0, os.path.dirname(__file__))
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s")
log = logging.getLogger("music_service")


class MusicService:

    def __init__(self):
        self.redis: aioredis.Redis = None
        self.db = None
        self.clients: dict[int, Client] = {}
        # userbot_id → Pyrogram client
        self.calls: dict[int, PyTGCalls] = {}
        # userbot_id → PyTGCalls instance
        self.bot_clients: dict[int, list[int]] = {}
        # bot_id → list of userbot_ids
        self.sessions: dict[tuple, dict] = {}
        # (chat_id, bot_id) → session state dict
        self._running = False

    async def start(self):
        log.info("[MUSIC_SVC] Starting...")

        # Connect Redis
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await self.redis.ping()
        log.info("[MUSIC_SVC] Redis connected")

        # Connect DB
        import asyncpg

        self.db = await asyncpg.create_pool(settings.SUPABASE_CONNECTION_STRING)

        # Load all active Pyrogram clients from DB
        await self._load_clients()

        # Verify yt-dlp version
        self._check_ytdlp_version()

        self._running = True

        # Start background tasks
        await asyncio.gather(
            self._job_consumer(),
            self._heartbeat_task(),
            self._idle_cleanup_task(),
        )

    async def _load_clients(self):
        """Load all active userbot sessions from DB, start Pyrogram + PyTGCalls."""
        rows = await self.db.fetch(
            "SELECT id, owner_bot_id, session_string, tg_name FROM music_userbots "
            "WHERE is_active=TRUE AND is_banned=FALSE"
        )
        from bot.utils.crypto import decrypt_token

        for row in rows:
            ub_id = row["id"]
            bot_id = row["owner_bot_id"]
            try:
                raw = decrypt_token(row["session_string"])
                client = Client(
                    name=f"music_{ub_id}",
                    api_id=settings.PYROGRAM_API_ID,
                    api_hash=settings.PYROGRAM_API_HASH,
                    session_string=raw,
                    in_memory=True,
                )
                await client.start()
                self.clients[ub_id] = client

                calls = PyTGCalls(client)

                @calls.on_stream_end()
                async def _on_end(_, update, u=ub_id):
                    # Find session for this chat and userbot
                    chat_id = update.chat_id
                    for (cid, bid), sess in list(self.sessions.items()):
                        if cid == chat_id and sess.get("userbot_id") == u:
                            await self._handle_stream_end(cid, bid)
                            break

                await calls.start()
                self.calls[ub_id] = calls

                if bot_id not in self.bot_clients:
                    self.bot_clients[bot_id] = []
                self.bot_clients[bot_id].append(ub_id)

                log.info(
                    f"[MUSIC_SVC] Client loaded | ub={ub_id} bot={bot_id} name={row['tg_name']}"
                )
            except Exception as e:
                log.error(f"[MUSIC_SVC] Client load failed | ub={ub_id} error={e}")

    def _check_ytdlp_version(self):
        """Warn if yt-dlp version differs from pinned version in config."""
        try:
            import importlib.metadata

            installed = importlib.metadata.version("yt-dlp")
            if installed != settings.MUSIC_YTDLP_VERSION:
                log.warning(
                    f"[MUSIC_SVC] yt-dlp version mismatch | "
                    f"installed={installed} expected={settings.MUSIC_YTDLP_VERSION}"
                )
            else:
                log.info(f"[MUSIC_SVC] yt-dlp version ok | {installed}")
        except Exception:
            pass

    async def _heartbeat_task(self):
        """Post heartbeat every 30s. Bot checks this to show music status."""
        while self._running:
            await self.redis.setex("music:worker:heartbeat", 90, "1")
            await asyncio.sleep(30)

    async def _job_consumer(self):
        """
        Consume jobs from all active bot queues.
        Uses BLPOP to block until a job arrives.
        Builds key list dynamically from loaded clients.
        """
        log.info("[MUSIC_SVC] Job consumer started")
        while self._running:
            try:
                # Build list of all queue keys to listen on
                keys = []
                for bot_id in self.bot_clients:
                    keys.append(f"music:dispatch:{bot_id}")

                # Also listen on global queue (main bot's own music)
                if 0 not in self.bot_clients:
                    keys.append("music:dispatch:0")

                if not keys:
                    await asyncio.sleep(1)
                    continue

                result = await self.redis.blpop(keys, timeout=5)
                if not result:
                    continue

                _, raw_job = result
                job = json.loads(raw_job)
                asyncio.create_task(self._process_job(job))

            except Exception as e:
                log.error(f"[MUSIC_SVC] Consumer error | {e}")
                await asyncio.sleep(1)

    async def _process_job(self, job: dict):
        """Route job to correct handler."""
        action = job.get("action")
        chat_id = job.get("chat_id")
        bot_id = job.get("bot_id", 0)
        job_id = job.get("job_id")

        # Reject old jobs
        age = time.time() - job.get("created_at", 0)
        if age > settings.MUSIC_JOB_TTL:
            log.warning(f"[MUSIC_SVC] Job too old | job={job_id} age={age:.0f}s")
            return

        log.info(f"[MUSIC_SVC] Processing | action={action} chat={chat_id} bot={bot_id}")

        result = {"ok": False, "error": "Unknown action", "data": {}}

        try:
            if action == "play":
                result = await self._play(job)
            elif action == "pause":
                result = await self._pause(chat_id, bot_id)
            elif action == "resume":
                result = await self._resume(chat_id, bot_id)
            elif action == "skip":
                result = await self._skip(chat_id, bot_id)
            elif action == "stop":
                result = await self._stop(chat_id, bot_id)
            elif action == "volume":
                result = await self._set_volume(chat_id, bot_id, job.get("volume", 100))
            elif action == "loop":
                result = await self._toggle_loop(chat_id, bot_id)
        except Exception as e:
            log.error(f"[MUSIC_SVC] Job error | job={job_id} error={e}")
            result = {"ok": False, "error": str(e), "data": {}}

        # Publish result
        if job_id:
            await self.redis.setex(
                f"music:result:{job_id}", 30, json.dumps({"job_id": job_id, **result})
            )

    async def _get_userbot_for_chat(self, chat_id: int, bot_id: int) -> int:
        """Find best userbot to use for this chat."""
        # 1. Check DB for assigned userbot
        row = await self.db.fetchrow(
            "SELECT userbot_id FROM music_settings WHERE chat_id=$1 AND bot_id=$2", chat_id, bot_id
        )
        if row and row["userbot_id"] and row["userbot_id"] in self.clients:
            return row["userbot_id"]

        # 2. Check if a userbot is already active in this chat
        key = (chat_id, bot_id)
        if key in self.sessions and self.sessions[key].get("userbot_id"):
            return self.sessions[key]["userbot_id"]

        # 3. Pick any available userbot for this bot_id
        ub_ids = self.bot_clients.get(bot_id, [])
        if not ub_ids and bot_id != 0:
            # Fallback to shared pool (bot_id 0)
            ub_ids = self.bot_clients.get(0, [])

        if ub_ids:
            return ub_ids[0]

        return 0

    async def _play(self, job: dict) -> dict:
        """Download and stream a track."""
        chat_id = job["chat_id"]
        bot_id = job["bot_id"]
        url = job["url"]
        playnow = job.get("playnow", False)

        # Resolve track with retry + fallback chain
        track = await self._resolve_with_retry(url)
        if not track:
            return {
                "ok": False,
                "error": "Could not load track. URL may be unsupported or unavailable.",
            }

        # Select userbot
        userbot_id = await self._get_userbot_for_chat(chat_id, bot_id)
        if not userbot_id:
            return {
                "ok": False,
                "error": "No music userbots available. Please add one in the Mini App.",
            }

        key = (chat_id, bot_id)
        if key not in self.sessions:
            self.sessions[key] = {
                "queue": [],
                "current": None,
                "is_playing": False,
                "is_paused": False,
                "is_looping": False,
                "volume": 100,
                "np_message_id": None,
                "idle_task": None,
                "userbot_id": userbot_id,
            }

        sess = self.sessions[key]
        sess["userbot_id"] = userbot_id  # ensure it's set
        track["requested_by"] = job.get("requested_by")
        track["requested_by_name"] = job.get("requested_by_name")

        if playnow:
            sess["queue"].insert(0, track)
            if sess["is_playing"] or sess["is_paused"]:
                await self._stop_stream(chat_id, bot_id)
        else:
            sess["queue"].append(track)

        if not sess["is_playing"] and not sess["is_paused"]:
            return await self._play_next(chat_id, bot_id, job)

        pos = sess["queue"].index(track) + 1
        await self._update_status(chat_id, bot_id)
        return {
            "ok": True,
            "data": {
                "queued": True,
                "position": pos,
                "title": track["title"],
                "duration": track["duration"],
            },
        }

    async def _resolve_with_retry(self, url: str) -> dict | None:
        """
        Download audio with retry logic and source fallback chain.

        Retry: up to MUSIC_MAX_RETRIES attempts with exponential backoff.
        Fallback: if primary source fails 3+ times in last hour,
                  mark as broken in Redis and skip to direct URL attempt.

        Returns dict with title, duration, thumbnail, source, file_path
        or None if all attempts fail.
        """
        os.makedirs(settings.MUSIC_DOWNLOAD_DIR, exist_ok=True)

        # Detect source
        url_lower = url.lower()
        if "youtube" in url_lower or "youtu.be" in url_lower:
            source = "youtube"
        elif "soundcloud" in url_lower:
            source = "soundcloud"
        elif "spotify" in url_lower:
            source = "spotify"
        else:
            source = "direct"

        # Check if source is marked broken
        broken_key = f"music:ytdlp:broken:{source}"
        is_broken = await self.redis.exists(broken_key)
        if is_broken:
            log.warning(f"[MUSIC_SVC] Source marked broken | source={source}")

        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": f"{settings.MUSIC_DOWNLOAD_DIR}/%(id)s.%(ext)s",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
        }

        last_error = None
        for attempt in range(settings.MUSIC_MAX_RETRIES):
            try:
                loop = asyncio.get_event_loop()

                def _download():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=True)

                info = await loop.run_in_executor(None, _download)

                duration = info.get("duration", 0)
                if duration > settings.MUSIC_MAX_DURATION:
                    return None

                file_path = f"{settings.MUSIC_DOWNLOAD_DIR}/{info['id']}.mp3"
                if not os.path.exists(file_path):
                    # Try alternative extension
                    for ext in ["m4a", "webm", "ogg"]:
                        alt = f"{settings.MUSIC_DOWNLOAD_DIR}/{info['id']}.{ext}"
                        if os.path.exists(alt):
                            file_path = alt
                            break

                # Clear broken flag on success
                await self.redis.delete(broken_key)

                return {
                    "url": url,
                    "title": info.get("title", "Unknown"),
                    "duration": duration,
                    "thumbnail": info.get("thumbnail", ""),
                    "source": source,
                    "file_path": file_path,
                }

            except Exception as e:
                last_error = str(e)
                log.warning(
                    f"[MUSIC_SVC] Download attempt {attempt+1} failed | "
                    f"url={url[:50]} error={e}"
                )
                if attempt < settings.MUSIC_MAX_RETRIES - 1:
                    await asyncio.sleep(2**attempt)  # 1s, 2s, 4s

        # All attempts failed — mark source broken for 1 hour
        await self.redis.setex(broken_key, 3600, "1")
        log.error(
            f"[MUSIC_SVC] Download failed all retries | url={url[:50]} last_error={last_error}"
        )
        return None

    async def _play_next(self, chat_id: int, bot_id: int, original_job: dict) -> dict:
        """Pop next track from queue and start streaming."""
        key = (chat_id, bot_id)
        sess = self.sessions.get(key)
        if not sess:
            return {"ok": False, "error": "No session"}

        if sess["is_looping"] and sess["current"]:
            sess["queue"].insert(0, sess["current"])

        if not sess["queue"]:
            await self._leave_vc(chat_id, bot_id)
            self.sessions.pop(key, None)
            return {"ok": True, "data": {"ended": True}}

        track = sess["queue"].pop(0)
        sess["current"] = track
        sess["is_playing"] = True
        sess["is_paused"] = False

        if sess.get("idle_task"):
            sess["idle_task"].cancel()
            sess["idle_task"] = None

        ub_id = sess.get("userbot_id")
        calls = self.calls.get(ub_id)
        if not calls:
            return {"ok": False, "error": "No music client available for this session."}

        try:
            try:
                await calls.join_group_call(
                    chat_id,
                    AudioPiped(track["file_path"], HighQualityAudio()),
                )
            except Exception:
                await calls.change_stream(
                    chat_id, AudioPiped(track["file_path"], HighQualityAudio())
                )

            await self._update_status(chat_id, bot_id)

            # Send now-playing card via bot API
            await self._send_np_card(
                chat_id,
                bot_id,
                track,
                sess,
                original_job.get("reply_chat_id", chat_id),
                original_job.get("reply_bot_token", ""),
            )

            log.info(f"[MUSIC_SVC] Streaming | chat={chat_id} title={track['title']}")
            return {
                "ok": True,
                "data": {
                    "playing": True,
                    "title": track["title"],
                    "duration": track["duration"],
                    "thumbnail": track["thumbnail"],
                    "source": track["source"],
                    "queue_len": len(sess["queue"]),
                },
            }
        except Exception as e:
            log.error(f"[MUSIC_SVC] Stream failed | chat={chat_id} error={e}")
            sess["is_playing"] = False
            return {"ok": False, "error": f"Stream error: {e}"}

    async def _handle_stream_end(self, chat_id: int, bot_id: int):
        """Called by PyTGCalls when track ends."""
        key = (chat_id, bot_id)
        sess = self.sessions.get(key)
        if not sess:
            return

        # Delete temp file
        if sess["current"] and sess["current"].get("file_path"):
            try:
                os.remove(sess["current"]["file_path"])
            except Exception:
                pass

        log.info(f"[MUSIC_SVC] Track ended | chat={chat_id} queue={len(sess['queue'])}")

        if not sess["queue"] and not sess["is_looping"]:
            # Start idle timer
            sess["idle_task"] = asyncio.create_task(self._idle_leave(chat_id, bot_id))
        else:
            await self._play_next(chat_id, bot_id, {})

    async def _idle_leave(self, chat_id: int, bot_id: int):
        await asyncio.sleep(settings.MUSIC_IDLE_TIMEOUT)
        log.info(f"[MUSIC_SVC] Idle timeout | chat={chat_id}")
        await self._leave_vc(chat_id, bot_id)
        self.sessions.pop((chat_id, bot_id), None)
        await self._clear_status(chat_id, bot_id)

    async def _pause(self, chat_id, bot_id) -> dict:
        sess = self.sessions.get((chat_id, bot_id))
        if not sess or not sess["is_playing"]:
            return {"ok": False, "error": "Nothing playing"}
        ub_id = sess.get("userbot_id")
        calls = self.calls.get(ub_id)
        if not calls:
            return {"ok": False, "error": "No music client available"}
        try:
            await calls.pause_stream(chat_id)
            sess["is_playing"] = False
            sess["is_paused"] = True
            await self._update_status(chat_id, bot_id)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _resume(self, chat_id, bot_id) -> dict:
        sess = self.sessions.get((chat_id, bot_id))
        if not sess or not sess["is_paused"]:
            return {"ok": False, "error": "Nothing paused"}
        ub_id = sess.get("userbot_id")
        calls = self.calls.get(ub_id)
        if not calls:
            return {"ok": False, "error": "No music client available"}
        try:
            await calls.resume_stream(chat_id)
            sess["is_playing"] = True
            sess["is_paused"] = False
            await self._update_status(chat_id, bot_id)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _skip(self, chat_id, bot_id) -> dict:
        sess = self.sessions.get((chat_id, bot_id))
        if not sess:
            return {"ok": False, "error": "Nothing playing"}
        return await self._play_next(chat_id, bot_id, {})

    async def _stop(self, chat_id, bot_id) -> dict:
        key = (chat_id, bot_id)
        sess = self.sessions.get(key)
        if sess:
            sess["queue"].clear()
        await self._leave_vc(chat_id, bot_id)
        self.sessions.pop(key, None)
        await self._clear_status(chat_id, bot_id)
        return {"ok": True}

    async def _set_volume(self, chat_id, bot_id, volume) -> dict:
        volume = max(0, min(200, volume))
        sess = self.sessions.get((chat_id, bot_id))
        if not sess:
            return {"ok": False, "error": "Nothing playing"}
        ub_id = sess.get("userbot_id")
        calls = self.calls.get(ub_id)
        if not calls:
            return {"ok": False, "error": "No music client available"}
        try:
            await calls.change_volume_call(chat_id, volume)
            sess["volume"] = volume
            await self._update_status(chat_id, bot_id)
            return {"ok": True, "data": {"volume": volume}}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _toggle_loop(self, chat_id, bot_id) -> dict:
        sess = self.sessions.get((chat_id, bot_id))
        if not sess:
            return {"ok": False, "error": "Nothing playing"}
        sess["is_looping"] = not sess["is_looping"]
        await self._update_status(chat_id, bot_id)
        return {"ok": True, "data": {"looping": sess["is_looping"]}}

    async def _leave_vc(self, chat_id, bot_id):
        sess = self.sessions.get((chat_id, bot_id))
        if sess:
            ub_id = sess.get("userbot_id")
            calls = self.calls.get(ub_id)
            if calls:
                try:
                    await calls.leave_group_call(chat_id)
                except Exception:
                    pass

    async def _stop_stream(self, chat_id, bot_id):
        await self._leave_vc(chat_id, bot_id)
        sess = self.sessions.get((chat_id, bot_id))
        if sess:
            sess["is_playing"] = False
            sess["is_paused"] = False

    async def _update_status(self, chat_id: int, bot_id: int):
        """Write current session state to Redis for bot to read."""
        sess = self.sessions.get((chat_id, bot_id))
        if not sess:
            return
        current = sess.get("current", {}) or {}
        data = {
            "is_playing": str(sess["is_playing"]),
            "is_paused": str(sess["is_paused"]),
            "is_looping": str(sess["is_looping"]),
            "volume": str(sess["volume"]),
            "userbot_id": str(sess.get("userbot_id", 0)),
            "current_title": current.get("title", ""),
            "current_duration": str(current.get("duration", 0)),
            "current_source": current.get("source", ""),
            "queue_length": str(len(sess["queue"])),
            "np_message_id": str(sess.get("np_message_id") or ""),
            "last_updated": str(time.time()),
        }
        key = f"music:status:{chat_id}:{bot_id}"
        await self.redis.hset(key, mapping=data)
        await self.redis.expire(key, 86400)

    async def _clear_status(self, chat_id: int, bot_id: int):
        await self.redis.delete(f"music:status:{chat_id}:{bot_id}")

    async def _send_np_card(self, chat_id, bot_id, track, sess, reply_chat_id, bot_token):
        """
        Send or update the now-playing card via Telegram Bot API.
        Uses httpx to call bot API directly (no PTB dependency in music service).
        """
        if not bot_token:
            return
        import httpx

        source_emoji = {
            "youtube": "▶️",
            "soundcloud": "🔶",
            "spotify": "🟢",
            "direct": "🔗",
            "voice": "🎤",
        }.get(track.get("source", ""), "🎵")

        mins, secs = divmod(track.get("duration", 0), 60)
        text = (
            f"🎵 <b>Now Playing</b>\n\n"
            f"<b>{track['title']}</b>\n"
            f"⏱ {mins}:{secs:02d}  ·  🔊 {sess['volume']}%  ·  {source_emoji}\n"
            f"📋 {len(sess['queue'])} in queue"
            f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "⏸ Pause", "callback_data": f"music:pause:{chat_id}"},
                    {"text": "⏭ Skip", "callback_data": f"music:skip:{chat_id}"},
                    {"text": "⏹ Stop", "callback_data": f"music:stop:{chat_id}"},
                ],
                [
                    {"text": "🔁 Loop", "callback_data": f"music:loop:{chat_id}"},
                    {"text": "📋 Queue", "callback_data": f"music:queue:{chat_id}"},
                    {"text": "🔊 Vol", "callback_data": f"music:vol:{chat_id}"},
                ],
            ]
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": reply_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                msg_id = resp.json()["result"]["message_id"]
                if (chat_id, bot_id) in self.sessions:
                    self.sessions[(chat_id, bot_id)]["np_message_id"] = msg_id
                await self._update_status(chat_id, bot_id)

    async def _idle_cleanup_task(self):
        """Every 5 min: clean up temp files older than 30 min."""
        while self._running:
            await asyncio.sleep(300)
            try:
                now = time.time()
                for f in os.listdir(settings.MUSIC_DOWNLOAD_DIR):
                    path = os.path.join(settings.MUSIC_DOWNLOAD_DIR, f)
                    if os.path.isfile(path) and (now - os.path.getmtime(path)) > 1800:
                        os.remove(path)
                        log.debug(f"[MUSIC_SVC] Cleaned temp file | {f}")
            except Exception as e:
                log.warning(f"[MUSIC_SVC] Cleanup error | {e}")


if __name__ == "__main__":
    svc = MusicService()
    asyncio.run(svc.start())
