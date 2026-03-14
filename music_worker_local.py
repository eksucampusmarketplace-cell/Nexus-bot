"""
music_worker_local.py

Standalone music streaming worker for local PC/WSL deployment.
This script runs on your local machine (not on Render) and handles
all music streaming via Pyrogram + PyTGCalls.

Communication with the main bot happens via Redis.

Setup:
1. Copy .env.music.example to .env.music and fill in values
2. Ensure Redis and PostgreSQL are accessible from your PC
3. Run: python music_worker_local.py

Logs prefix: [MUSIC_WORKER]
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional

# Setup logging first
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s")
log = logging.getLogger("music_worker_local")

# Load environment
from dotenv import load_dotenv

load_dotenv(".env.music")

# Import required libraries
try:
    import asyncpg
    import redis.asyncio as aioredis
    import yt_dlp
    from pyrogram import Client
    from pytgcalls import PyTGCalls
    from pytgcalls.types.input_stream import AudioPiped
    from pytgcalls.types.input_stream.quality import HighQualityAudio
except ImportError as e:
    log.error(f"[MUSIC_WORKER] Missing required dependency: {e}")
    log.error("[MUSIC_WORKER] Please install: pip install asyncpg redis pyrogram py-tgcalls yt-dlp")
    sys.exit(1)

from bot.utils.crypto import decrypt_token

# Load config
from config import settings


class LocalMusicWorker:
    """
    Standalone music worker that runs on a local PC/WSL.
    Consumes jobs from Redis and streams audio via PyTGCalls.
    """

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        self.userbot_clients: Dict[int, Client] = {}
        self.userbot_calls: Dict[int, PyTGCalls] = {}
        self.sessions: Dict[tuple, Dict] = {}  # (chat_id, bot_id) -> session state
        self._running = False
        self._shutdown_event = asyncio.Event()

    def _print_banner(self):
        """Print startup banner"""
        print("=" * 60)
        print("  🎵 NEXUS MUSIC WORKER (Local PC)")
        print("=" * 60)
        print(f"  Redis: {settings.REDIS_URL}")
        print(f"  Database: Connected via asyncpg")
        print(f"  Download Dir: {settings.MUSIC_DOWNLOAD_DIR}")
        print(f"  Max Duration: {settings.MUSIC_MAX_DURATION // 60} minutes")
        print("=" * 60)

    async def start(self):
        """Start the music worker"""
        self._print_banner()

        # Connect to Redis
        try:
            self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.redis.ping()
            log.info("[MUSIC_WORKER] ✅ Redis connected")
        except Exception as e:
            log.error(f"[MUSIC_WORKER] ❌ Redis connection failed: {e}")
            sys.exit(1)

        # Connect to PostgreSQL
        try:
            self.db_pool = await asyncpg.create_pool(
                settings.SUPABASE_CONNECTION_STRING, min_size=1, max_size=5
            )
            log.info("[MUSIC_WORKER] ✅ Database connected")
        except Exception as e:
            log.error(f"[MUSIC_WORKER] ❌ Database connection failed: {e}")
            sys.exit(1)

        # Load userbot clients
        await self._load_userbots()

        if not self.userbot_clients:
            log.warning(
                "[MUSIC_WORKER] ⚠️ No active userbots found. Waiting for userbots to be added..."
            )

        self._running = True

        # Setup signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(sig, self._signal_handler)

        # Start background tasks
        log.info("[MUSIC_WORKER] 🚀 Starting job consumer and heartbeat...")
        await asyncio.gather(self._heartbeat_task(), self._job_consumer(), self._cleanup_task())

    def _signal_handler(self):
        """Handle shutdown signals"""
        log.info("[MUSIC_WORKER] 🛑 Shutdown signal received...")
        self._running = False
        self._shutdown_event.set()

    async def _load_userbots(self):
        """Load all active userbot sessions from database"""
        try:
            rows = await self.db_pool.fetch("""
                SELECT id, owner_bot_id, session_string, tg_name, is_active, is_banned
                FROM music_userbots
                WHERE is_active=TRUE AND is_banned=FALSE
                """)

            for row in rows:
                ub_id = row["id"]
                try:
                    await self._start_userbot(ub_id, row)
                except Exception as e:
                    log.error(f"[MUSIC_WORKER] ❌ Failed to start userbot {ub_id}: {e}")

            log.info(f"[MUSIC_WORKER] 📱 Loaded {len(self.userbot_clients)} userbots")
        except Exception as e:
            log.error(f"[MUSIC_WORKER] ❌ Failed to load userbots: {e}")

    async def _start_userbot(self, ub_id: int, row: asyncpg.Record) -> bool:
        """Start a single userbot client"""
        if ub_id in self.userbot_clients:
            log.info(f"[MUSIC_WORKER] Userbot {ub_id} already running")
            return True

        try:
            # Decrypt session string
            session_string = decrypt_token(row["session_string"])

            # Create Pyrogram client
            client = Client(
                name=f"nexus_worker_{ub_id}",
                api_id=settings.PYROGRAM_API_ID,
                api_hash=settings.PYROGRAM_API_HASH,
                session_string=session_string,
                in_memory=True,
            )

            await client.start()

            # Create PyTGCalls instance
            calls = PyTGCalls(client)

            # Register stream end handler
            @calls.on_stream_end()
            async def _on_stream_end(_, update, userbot_id=ub_id):
                await self._handle_stream_end(update.chat_id, userbot_id)

            await calls.start()

            # Store references
            self.userbot_clients[ub_id] = client
            self.userbot_calls[ub_id] = calls

            log.info(f"[MUSIC_WORKER] ✅ Started userbot {ub_id} ({row.get('tg_name', 'Unknown')})")
            return True

        except Exception as e:
            log.error(f"[MUSIC_WORKER] ❌ Failed to start userbot {ub_id}: {e}")
            return False

    async def _heartbeat_task(self):
        """Send heartbeat to Redis every 10 seconds"""
        while self._running:
            try:
                heartbeat_data = {
                    "worker_online": True,
                    "last_heartbeat": time.time(),
                    "userbots_count": len(self.userbot_clients),
                    "active_sessions": len(self.sessions),
                }
                await self.redis.setex("music:worker:heartbeat", 30, json.dumps(heartbeat_data))
                await self.redis.set("music:worker:heartbeat_time", str(time.time()))
            except Exception as e:
                log.warning(f"[MUSIC_WORKER] Heartbeat failed: {e}")

            # Wait for 10 seconds or until shutdown
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=10)
                break
            except asyncio.TimeoutError:
                continue

    async def _job_consumer(self):
        """Consume jobs from Redis queue"""
        log.info("[MUSIC_WORKER] 📥 Job consumer started, listening for jobs...")

        while self._running:
            try:
                # Check for new userbots periodically
                await self._refresh_userbots()

                # Block waiting for jobs
                result = await self.redis.blpop("music:jobs", timeout=5)
                if not result:
                    continue

                _, raw_job = result
                job = json.loads(raw_job)

                # Process job in background
                asyncio.create_task(self._process_job(job))

            except Exception as e:
                log.error(f"[MUSIC_WORKER] Job consumer error: {e}")
                await asyncio.sleep(1)

    async def _refresh_userbots(self):
        """Check for new userbots in database"""
        try:
            rows = await self.db_pool.fetch(
                """
                SELECT id, owner_bot_id, session_string, tg_name, is_active, is_banned
                FROM music_userbots
                WHERE is_active=TRUE AND is_banned=FALSE
                AND id = ANY($1::int[])
                """,
                list(self.userbot_clients.keys()),
            )

            # Find new userbots not yet loaded
            loaded_ids = set(self.userbot_clients.keys())
            db_ids = {row["id"] for row in rows}

            # Start new userbots
            for row in rows:
                if row["id"] not in loaded_ids:
                    await self._start_userbot(row["id"], row)

            # Stop removed userbots
            for ub_id in loaded_ids - db_ids:
                await self._stop_userbot(ub_id)

        except Exception as e:
            log.warning(f"[MUSIC_WORKER] Failed to refresh userbots: {e}")

    async def _stop_userbot(self, ub_id: int):
        """Stop a userbot client"""
        if ub_id not in self.userbot_clients:
            return

        try:
            calls = self.userbot_calls.pop(ub_id, None)
            client = self.userbot_clients.pop(ub_id, None)

            if calls:
                await calls.stop()
            if client:
                await client.stop()

            log.info(f"[MUSIC_WORKER] 🛑 Stopped userbot {ub_id}")
        except Exception as e:
            log.error(f"[MUSIC_WORKER] Error stopping userbot {ub_id}: {e}")

    async def _process_job(self, job: Dict[str, Any]):
        """Process a single job from the queue"""
        job_type = job.get("job") or job.get("action")
        chat_id = job.get("chat_id")
        bot_id = job.get("bot_id", 0)
        userbot_id = job.get("userbot_id")

        log.info(f"[MUSIC_WORKER] Processing job | type={job_type} chat={chat_id}")

        try:
            if job_type == "play":
                await self._handle_play(job)
            elif job_type == "pause":
                await self._handle_pause(chat_id, bot_id)
            elif job_type == "resume":
                await self._handle_resume(chat_id, bot_id)
            elif job_type == "skip":
                await self._handle_skip(chat_id, bot_id)
            elif job_type == "stop":
                await self._handle_stop(chat_id, bot_id)
            elif job_type == "volume":
                await self._handle_volume(chat_id, bot_id, job.get("volume", 100))
            else:
                log.warning(f"[MUSIC_WORKER] Unknown job type: {job_type}")

        except Exception as e:
            log.error(f"[MUSIC_WORKER] Job processing error: {e}")

    async def _get_userbot_for_job(self, job: Dict[str, Any]) -> Optional[int]:
        """
        Determine which userbot to use for a job.
        Handles rotation based on settings.
        """
        chat_id = job.get("chat_id")
        bot_id = job.get("bot_id", 0)
        requested_userbot = job.get("userbot_id")

        # If specific userbot requested, use it
        if requested_userbot and requested_userbot in self.userbot_calls:
            return requested_userbot

        # Get settings from database
        try:
            row = await self.db_pool.fetchrow(
                """
                SELECT userbot_id, auto_rotate, rotation_mode
                FROM music_settings
                WHERE chat_id=$1 AND bot_id=$2
                """,
                chat_id,
                bot_id,
            )

            if row:
                # Check rotation settings
                if row.get("auto_rotate"):
                    rotation_mode = row.get("rotation_mode", "round_robin")
                    return await self._get_next_rotation_userbot(bot_id, rotation_mode)
                elif row.get("userbot_id"):
                    return row["userbot_id"]

        except Exception as e:
            log.warning(f"[MUSIC_WORKER] Failed to get settings: {e}")

        # Fallback: use any available userbot for this bot
        userbots_for_bot = [
            ub_id
            for ub_id in self.userbot_calls.keys()
            if (
                await self.db_pool.fetchval(
                    "SELECT owner_bot_id FROM music_userbots WHERE id=$1", ub_id
                )
            )
            == bot_id
        ]

        if userbots_for_bot:
            return userbots_for_bot[0]

        # Ultimate fallback: any userbot
        if self.userbot_calls:
            return list(self.userbot_calls.keys())[0]

        return None

    async def _get_next_rotation_userbot(
        self, owner_bot_id: int, rotation_mode: str
    ) -> Optional[int]:
        """Get next userbot based on rotation strategy"""
        try:
            if rotation_mode == "least_used":
                row = await self.db_pool.fetchrow(
                    """
                    SELECT id FROM music_userbots
                    WHERE owner_bot_id=$1 AND is_active=TRUE AND is_banned=FALSE
                    ORDER BY play_count ASC, last_used_at ASC NULLS FIRST
                    LIMIT 1
                    """,
                    owner_bot_id,
                )
            elif rotation_mode == "random":
                row = await self.db_pool.fetchrow(
                    """
                    SELECT id FROM music_userbots
                    WHERE owner_bot_id=$1 AND is_active=TRUE AND is_banned=FALSE
                    ORDER BY RANDOM()
                    LIMIT 1
                    """,
                    owner_bot_id,
                )
            else:  # round_robin
                row = await self.db_pool.fetchrow(
                    """
                    SELECT id FROM music_userbots
                    WHERE owner_bot_id=$1 AND is_active=TRUE AND is_banned=FALSE
                    ORDER BY last_used_at ASC NULLS FIRST
                    LIMIT 1
                    """,
                    owner_bot_id,
                )

            return row["id"] if row else None
        except Exception as e:
            log.error(f"[MUSIC_WORKER] Rotation query failed: {e}")
            return None

    async def _record_userbot_usage(self, userbot_id: int, chat_id: int):
        """Record that a userbot was used"""
        try:
            await self.db_pool.execute(
                """
                UPDATE music_userbots
                SET play_count = play_count + 1, last_used_at = NOW()
                WHERE id=$1
                """,
                userbot_id,
            )
        except Exception as e:
            log.warning(f"[MUSIC_WORKER] Failed to record usage: {e}")

    async def _handle_play(self, job: Dict[str, Any]):
        """Handle play job"""
        chat_id = job.get("chat_id")
        bot_id = job.get("bot_id", 0)
        url = job.get("url")

        # Resolve audio URL
        track = await self._resolve_url(url)
        if not track:
            log.error(f"[MUSIC_WORKER] Failed to resolve URL: {url}")
            await self._update_status(chat_id, bot_id, {"error": "Failed to resolve track"})
            return

        # Get userbot to use
        userbot_id = await self._get_userbot_for_job(job)
        if not userbot_id or userbot_id not in self.userbot_calls:
            log.error(f"[MUSIC_WORKER] No userbot available for chat {chat_id}")
            await self._update_status(chat_id, bot_id, {"error": "No userbot available"})
            return

        # Record usage
        await self._record_userbot_usage(userbot_id, chat_id)

        # Get or create session
        session_key = (chat_id, bot_id)
        if session_key not in self.sessions:
            self.sessions[session_key] = {
                "queue": [],
                "current": None,
                "is_playing": False,
                "is_paused": False,
                "volume": 100,
                "userbot_id": userbot_id,
            }

        session = self.sessions[session_key]
        session["queue"].append(track)

        # Start playing if not already
        if not session["is_playing"] and not session["is_paused"]:
            await self._play_next(chat_id, bot_id)
        else:
            await self._update_status(chat_id, bot_id, session)

    async def _resolve_url(self, url: str) -> Optional[Dict]:
        """Resolve URL to audio file using yt-dlp"""
        import os
        import tempfile

        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": f"{settings.MUSIC_DOWNLOAD_DIR}/%(id)s.%(ext)s",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        }

        try:
            loop = asyncio.get_event_loop()

            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info

            info = await loop.run_in_executor(None, _download)

            duration = info.get("duration", 0)
            if duration > settings.MUSIC_MAX_DURATION:
                log.warning(f"[MUSIC_WORKER] Track too long: {duration}s")
                return None

            file_path = f"{settings.MUSIC_DOWNLOAD_DIR}/{info['id']}.mp3"

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

            return {
                "url": url,
                "title": info.get("title", "Unknown"),
                "duration": duration,
                "thumbnail": info.get("thumbnail", ""),
                "source": source,
                "file_path": file_path,
            }

        except Exception as e:
            log.error(f"[MUSIC_WORKER] Download failed: {e}")
            return None

    async def _play_next(self, chat_id: int, bot_id: int):
        """Play next track in queue"""
        session_key = (chat_id, bot_id)
        session = self.sessions.get(session_key)
        if not session or not session["queue"]:
            return

        track = session["queue"].pop(0)
        session["current"] = track
        session["is_playing"] = True
        session["is_paused"] = False

        userbot_id = session.get("userbot_id")
        if not userbot_id or userbot_id not in self.userbot_calls:
            log.error(f"[MUSIC_WORKER] No valid userbot for session")
            return

        calls = self.userbot_calls[userbot_id]

        try:
            try:
                await calls.join_group_call(
                    chat_id, AudioPiped(track["file_path"], HighQualityAudio())
                )
            except Exception:
                # Already in VC, change stream
                await calls.change_stream(
                    chat_id, AudioPiped(track["file_path"], HighQualityAudio())
                )

            log.info(f"[MUSIC_WORKER] ▶️ Playing: {track['title']} in chat {chat_id}")
            await self._update_status(chat_id, bot_id, session)

        except Exception as e:
            log.error(f"[MUSIC_WORKER] Stream failed: {e}")
            session["is_playing"] = False

    async def _handle_stream_end(self, chat_id: int, userbot_id: int):
        """Handle track ending"""
        # Find session for this chat
        for (cid, bid), session in list(self.sessions.items()):
            if cid == chat_id and session.get("userbot_id") == userbot_id:
                # Clean up file
                if session.get("current") and session["current"].get("file_path"):
                    try:
                        os.remove(session["current"]["file_path"])
                    except Exception:
                        pass

                # Play next or cleanup
                if session["queue"]:
                    await self._play_next(cid, bid)
                else:
                    await self._leave_vc(cid, bid)
                    del self.sessions[(cid, bid)]
                break

    async def _handle_pause(self, chat_id: int, bot_id: int):
        """Pause playback"""
        session = self.sessions.get((chat_id, bot_id))
        if not session:
            return

        userbot_id = session.get("userbot_id")
        if userbot_id and userbot_id in self.userbot_calls:
            try:
                await self.userbot_calls[userbot_id].pause_stream(chat_id)
                session["is_playing"] = False
                session["is_paused"] = True
                await self._update_status(chat_id, bot_id, session)
                log.info(f"[MUSIC_WORKER] ⏸ Paused chat {chat_id}")
            except Exception as e:
                log.error(f"[MUSIC_WORKER] Pause failed: {e}")

    async def _handle_resume(self, chat_id: int, bot_id: int):
        """Resume playback"""
        session = self.sessions.get((chat_id, bot_id))
        if not session:
            return

        userbot_id = session.get("userbot_id")
        if userbot_id and userbot_id in self.userbot_calls:
            try:
                await self.userbot_calls[userbot_id].resume_stream(chat_id)
                session["is_playing"] = True
                session["is_paused"] = False
                await self._update_status(chat_id, bot_id, session)
                log.info(f"[MUSIC_WORKER] ▶️ Resumed chat {chat_id}")
            except Exception as e:
                log.error(f"[MUSIC_WORKER] Resume failed: {e}")

    async def _handle_skip(self, chat_id: int, bot_id: int):
        """Skip current track"""
        session = self.sessions.get((chat_id, bot_id))
        if not session:
            return

        userbot_id = session.get("userbot_id")
        if userbot_id and userbot_id in self.userbot_calls:
            try:
                await self.userbot_calls[userbot_id].leave_group_call(chat_id)
            except Exception:
                pass

        await self._play_next(chat_id, bot_id)
        log.info(f"[MUSIC_WORKER] ⏭ Skipped in chat {chat_id}")

    async def _handle_stop(self, chat_id: int, bot_id: int):
        """Stop playback"""
        session = self.sessions.get((chat_id, bot_id))
        if not session:
            return

        userbot_id = session.get("userbot_id")
        if userbot_id and userbot_id in self.userbot_calls:
            try:
                await self.userbot_calls[userbot_id].leave_group_call(chat_id)
            except Exception:
                pass

        session["queue"] = []
        session["is_playing"] = False
        session["is_paused"] = False
        await self._update_status(chat_id, bot_id, session)
        del self.sessions[(chat_id, bot_id)]
        log.info(f"[MUSIC_WORKER] ⏹ Stopped chat {chat_id}")

    async def _handle_volume(self, chat_id: int, bot_id: int, volume: int):
        """Set volume"""
        session = self.sessions.get((chat_id, bot_id))
        if not session:
            return

        userbot_id = session.get("userbot_id")
        if userbot_id and userbot_id in self.userbot_calls:
            try:
                await self.userbot_calls[userbot_id].change_volume_call(chat_id, volume)
                session["volume"] = volume
                await self._update_status(chat_id, bot_id, session)
                log.info(f"[MUSIC_WORKER] 🔊 Volume set to {volume} in chat {chat_id}")
            except Exception as e:
                log.error(f"[MUSIC_WORKER] Volume change failed: {e}")

    async def _leave_vc(self, chat_id: int, bot_id: int):
        """Leave voice chat"""
        session = self.sessions.get((chat_id, bot_id))
        if not session:
            return

        userbot_id = session.get("userbot_id")
        if userbot_id and userbot_id in self.userbot_calls:
            try:
                await self.userbot_calls[userbot_id].leave_group_call(chat_id)
            except Exception:
                pass

    async def _update_status(self, chat_id: int, bot_id: int, session: Dict):
        """Update status in Redis"""
        try:
            current = session.get("current", {}) or {}
            status_data = {
                "is_playing": str(session.get("is_playing", False)),
                "is_paused": str(session.get("is_paused", False)),
                "current_title": current.get("title", ""),
                "current_source": current.get("source", ""),
                "current_duration": str(current.get("duration", 0)),
                "volume": str(session.get("volume", 100)),
                "userbot_id": str(session.get("userbot_id", 0)),
                "worker_online": "True",
                "last_heartbeat": str(time.time()),
            }

            await self.redis.hset(f"music:status:{chat_id}:{bot_id}", mapping=status_data)
            await self.redis.expire(f"music:status:{chat_id}:{bot_id}", 86400)
        except Exception as e:
            log.warning(f"[MUSIC_WORKER] Failed to update status: {e}")

    async def _cleanup_task(self):
        """Periodic cleanup task"""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                # Clean up old downloaded files
                import time as time_module

                now = time_module.time()
                for filename in os.listdir(settings.MUSIC_DOWNLOAD_DIR):
                    filepath = os.path.join(settings.MUSIC_DOWNLOAD_DIR, filename)
                    if os.path.isfile(filepath):
                        if now - os.path.getmtime(filepath) > 3600:  # Older than 1 hour
                            try:
                                os.remove(filepath)
                                log.debug(f"[MUSIC_WORKER] Cleaned up {filename}")
                            except Exception:
                                pass

            except Exception as e:
                log.warning(f"[MUSIC_WORKER] Cleanup error: {e}")

    async def stop(self):
        """Stop the worker gracefully"""
        log.info("[MUSIC_WORKER] 🛑 Stopping worker...")

        self._running = False

        # Stop all voice chats
        for (chat_id, bot_id), session in list(self.sessions.items()):
            await self._leave_vc(chat_id, bot_id)

        # Stop all userbot clients
        for ub_id in list(self.userbot_clients.keys()):
            await self._stop_userbot(ub_id)

        # Close connections
        if self.redis:
            await self.redis.close()
        if self.db_pool:
            await self.db_pool.close()

        log.info("[MUSIC_WORKER] ✅ Worker stopped")


if __name__ == "__main__":
    worker = LocalMusicWorker()

    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        log.info("[MUSIC_WORKER] Interrupted by user")
    except Exception as e:
        log.error(f"[MUSIC_WORKER] Fatal error: {e}")
        sys.exit(1)
