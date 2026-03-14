"""
Advanced Music Player API Routes
"""

import json
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/music", tags=["music"])


class Track(BaseModel):
    type: str
    title: str
    performer: Optional[str] = None
    duration: Optional[int] = 0
    file_id: Optional[str] = None
    url: Optional[str] = None


class MusicQueue(BaseModel):
    current: Optional[Track] = None
    queue: List[Track] = []
    is_playing: bool = False
    is_paused: bool = False
    volume: int = 100
    repeat_mode: str = "none"
    shuffle_mode: bool = False
    play_mode: str = "all"
    userbot_id: Optional[int] = None
    rotation_mode: str = "manual"
    auto_rotate: bool = False


class MusicCommand(BaseModel):
    command: str
    value: Optional[str] = None


class Playlist(BaseModel):
    id: int
    playlist_name: str
    tracks: List[Track]
    created_by: int
    created_at: str


class CreatePlaylist(BaseModel):
    playlist_name: str
    tracks: List[Track]


class MusicSettings(BaseModel):
    volume: int = 100
    repeat_mode: str = "none"
    shuffle_mode: bool = False
    play_mode: str = "all"
    announce_tracks: bool = True
    userbot_id: Optional[int] = None
    rotation_mode: str = "manual"
    auto_rotate: bool = False


class QueueReorderRequest(BaseModel):
    track_id: int
    new_position: int


async def _get_bot_id_from_user(user: dict) -> int:
    """Extract bot_id from user's validated bot token"""
    import hashlib

    import db.ops.bots as db_ops_bots
    from db.client import db

    bot_token = user.get("validated_bot_token")
    if not bot_token or not db.pool:
        return 0  # Default to shared pool

    # Get bot by token hash
    token_hash = hashlib.sha256(bot_token.encode()).hexdigest()
    bot = await db_ops_bots.get_bot_by_token_hash(db.pool, token_hash)
    if bot:
        return bot.get("bot_id", 0)
    return 0


@router.get("/status")
async def get_music_status():
    """
    Check music service availability.
    Returns status from Redis worker heartbeat if available, otherwise local status.
    """
    from db.client import db

    try:
        if db.redis:
            # Check for worker heartbeat
            heartbeat = await db.redis.get("music:worker:heartbeat")
            if heartbeat:
                # Check if heartbeat is recent (less than 30 seconds old)
                last_heartbeat = await db.redis.get("music:worker:heartbeat_time")
                if last_heartbeat:
                    age = time.time() - float(last_heartbeat)
                    if age < 30:
                        return {
                            "available": True,
                            "worker": "local_pc",
                            "reason": "Music worker is online and responding",
                        }

            # Check for local PyTGCalls availability
            try:
                from bot.userbot.music_worker import HAS_PYTGCALLS

                return {
                    "available": HAS_PYTGCALLS,
                    "worker": "local",
                    "reason": (
                        "PyTGCalls available"
                        if HAS_PYTGCALLS
                        else "Music worker offline. Start it on your PC to enable streaming."
                    ),
                }
            except ImportError:
                return {
                    "available": False,
                    "worker": None,
                    "reason": "Music system not initialized",
                }

        return {"available": False, "worker": None, "reason": "Redis not available"}
    except Exception as e:
        logger.error(f"[MUSIC_API] Error checking status: {e}")
        return {"available": False, "worker": None, "reason": f"Error checking status: {str(e)}"}


@router.get("/{chat_id}/queue", response_model=MusicQueue)
async def get_music_queue(chat_id: int, user: dict = Depends(get_current_user)):
    """Get the current music queue and settings for a group"""
    import db.ops.music_new as db_music
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Get the bot_id for this user's active bot context
        bot_id = await _get_bot_id_from_user(user)

        # Try to get real-time status from Redis first
        redis = db.redis
        status = {}
        if redis:
            status = await redis.hgetall(f"music:status:{chat_id}:{bot_id}")

        # Get queue entries from DB
        queue_entries = await db_music.get_queue_entries(db.pool, chat_id, bot_id, played=False)

        # Get music settings from DB
        music_settings = await db_music.get_music_settings(db.pool, chat_id, bot_id)

        # Build current track
        current = None
        if status.get("current_title"):
            current = Track(
                type=status.get("current_source", "unknown"),
                title=status.get("current_title", "Unknown"),
                performer="Now Playing",
                duration=int(status.get("current_duration", 0)),
            )
        elif queue_entries:
            # Fallback to DB current track if session exists
            session = await db_music.get_session_state(db.pool, chat_id, bot_id)
            if session and session.get("current_track"):
                current_track_id = session.get("current_track")
                for entry in queue_entries:
                    if entry.get("id") == current_track_id:
                        current = Track(
                            type=entry.get("source", "unknown"),
                            title=entry.get("title", "Unknown"),
                            performer=entry.get("requested_by_name", "Unknown"),
                            duration=entry.get("duration", 0),
                        )
                        break

        # Build queue list
        queue = [
            Track(
                type=entry.get("source", "unknown"),
                title=entry.get("title", "Unknown"),
                performer=entry.get("requested_by_name", "Unknown"),
                duration=entry.get("duration", 0),
            )
            for entry in queue_entries
        ]

        # Get settings with defaults
        settings_data = {
            "play_mode": music_settings.get("play_mode", "all") if music_settings else "all",
            "userbot_id": music_settings.get("userbot_id") if music_settings else None,
            "rotation_mode": (
                music_settings.get("rotation_mode", "manual") if music_settings else "manual"
            ),
            "auto_rotate": music_settings.get("auto_rotate", False) if music_settings else False,
            "volume": music_settings.get("volume", 100) if music_settings else 100,
        }

        if status:
            return MusicQueue(
                current=current,
                queue=queue,
                is_playing=status.get("is_playing") == "True",
                is_paused=status.get("is_paused") == "True",
                volume=int(status.get("volume", settings_data["volume"])),
                repeat_mode="one" if status.get("is_looping") == "True" else "none",
                shuffle_mode=False,
                play_mode=settings_data["play_mode"],
                userbot_id=(
                    int(status.get("userbot_id", 0))
                    if status.get("userbot_id")
                    else settings_data["userbot_id"]
                ),
                rotation_mode=settings_data["rotation_mode"],
                auto_rotate=settings_data["auto_rotate"],
            )
        else:
            # Fallback to DB session
            session = await db_music.get_session_state(db.pool, chat_id, bot_id)
            return MusicQueue(
                current=current,
                queue=queue,
                is_playing=session.get("is_playing", False) if session else False,
                is_paused=session.get("is_paused", False) if session else False,
                volume=(
                    session.get("volume", settings_data["volume"])
                    if session
                    else settings_data["volume"]
                ),
                repeat_mode="one" if (session and session.get("is_looping")) else "none",
                shuffle_mode=False,
                play_mode=settings_data["play_mode"],
                userbot_id=settings_data["userbot_id"],
                rotation_mode=settings_data["rotation_mode"],
                auto_rotate=settings_data["auto_rotate"],
            )
    except Exception as e:
        logger.error(f"[MUSIC_API] Error fetching queue: {e}")
        return MusicQueue()


@router.get("/{chat_id}/playlists")
async def get_playlists(chat_id: int):
    """Get all playlists for a group"""
    # This would need pool injection in production
    playlists = []  # Mock data
    return {"playlists": playlists}


@router.post("/{chat_id}/playlists", response_model=Playlist)
async def create_playlist(chat_id: int, playlist: CreatePlaylist):
    """Create a new playlist"""
    # This would need pool injection in production
    return {
        "id": 1,
        "playlist_name": playlist.playlist_name,
        "tracks": playlist.tracks,
        "created_by": 0,
        "created_at": "2024-01-01T00:00:00",
    }


@router.delete("/{chat_id}/playlists/{playlist_name}")
async def delete_playlist(chat_id: int, playlist_name: str):
    """Delete a playlist"""
    return {"status": "deleted", "playlist_name": playlist_name}


@router.post("/{chat_id}/playlists/{playlist_name}/play")
async def play_playlist(chat_id: int, playlist_name: str):
    """Play a playlist"""
    return {"status": "playing", "playlist_name": playlist_name}


@router.get("/{chat_id}/settings", response_model=MusicSettings)
async def get_music_settings(chat_id: int, user: dict = Depends(get_current_user)):
    """Get music settings for a group"""
    import db.ops.music_new as db_music
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Get the bot_id for this user's active bot context
        bot_id = await _get_bot_id_from_user(user)

        # Get music settings from database
        music_settings = await db_music.get_music_settings(db.pool, chat_id, bot_id)

        if music_settings:
            return MusicSettings(
                volume=music_settings.get("volume", 100),
                repeat_mode="one" if music_settings.get("is_looping") else "none",
                shuffle_mode=music_settings.get("shuffle_mode", False),
                play_mode=music_settings.get("play_mode", "all"),
                announce_tracks=music_settings.get("announce_tracks", True),
                userbot_id=music_settings.get("userbot_id"),
                rotation_mode=music_settings.get("rotation_mode", "manual"),
                auto_rotate=music_settings.get("auto_rotate", False),
            )
        else:
            # Return default settings
            return MusicSettings()
    except Exception as e:
        logger.error(f"[MUSIC_API] Error fetching settings: {e}")
        return MusicSettings()


@router.put("/{chat_id}/settings", response_model=MusicSettings)
async def update_music_settings(
    chat_id: int, settings: MusicSettings, user: dict = Depends(get_current_user)
):
    """Update music settings for a group"""
    import db.ops.music_new as db_music
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Get the bot_id for this user's active bot context
        bot_id = await _get_bot_id_from_user(user)

        # Upsert music settings with all fields
        await db_music.upsert_music_settings(
            db.pool,
            chat_id=chat_id,
            bot_id=bot_id,
            play_mode=settings.play_mode,
            announce_tracks=settings.announce_tracks,
            userbot_id=settings.userbot_id,
            volume=settings.volume,
            rotation_mode=settings.rotation_mode,
            auto_rotate=settings.auto_rotate,
        )

        # Update session state for volume and loop if needed
        session = await db_music.get_session_state(db.pool, chat_id, bot_id)
        if session:
            await db_music.update_session_state(
                db.pool,
                chat_id=chat_id,
                bot_id=bot_id,
                volume=settings.volume,
                is_looping=(settings.repeat_mode != "none"),
            )

        # If userbot_id changed, we should probably tell the music service
        # For now, it will pick up the change on next track or next command
        if settings.userbot_id:
            redis = db.redis
            if redis:
                # Push a 'switch_userbot' job or similar if needed
                pass

        return settings
    except Exception as e:
        logger.error(f"[MUSIC_API] Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{chat_id}/history")
async def get_play_history(chat_id: int, limit: int = 20, user: dict = Depends(get_current_user)):
    """Get play history for a group"""
    import db.ops.music_new as db_music
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        bot_id = await _get_bot_id_from_user(user)
        history = await db_music.get_play_history(db.pool, chat_id, bot_id, limit=limit)

        return {
            "history": [
                {
                    "id": entry.get("id"),
                    "title": entry.get("title", "Unknown"),
                    "performer": entry.get("requested_by_name", "Unknown"),
                    "source": entry.get("source", "unknown"),
                    "duration": entry.get("duration", 0),
                    "added_at": (
                        entry.get("added_at").isoformat() if entry.get("added_at") else None
                    ),
                }
                for entry in history
            ],
            "count": len(history),
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] Error fetching history: {e}")
        return {"history": [], "count": 0}


@router.get("/{chat_id}/search")
async def search_music(chat_id: int, query: str, user: dict = Depends(get_current_user)):
    """Search for music in queue and playlists"""
    import db.ops.music_new as db_music
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    try:
        bot_id = await _get_bot_id_from_user(user)
        results = await db_music.search_queue(db.pool, chat_id, bot_id, query)

        return {
            "results": [
                {
                    "id": entry.get("id"),
                    "title": entry.get("title", "Unknown"),
                    "performer": entry.get("requested_by_name", "Unknown"),
                    "source": entry.get("source", "unknown"),
                    "duration": entry.get("duration", 0),
                    "position": entry.get("position", 0),
                }
                for entry in results
            ],
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"[MUSIC_API] Error searching queue: {e}")
        return {"results": [], "count": 0}


@router.post("/{chat_id}/queue/reorder")
async def reorder_queue(
    chat_id: int, request: QueueReorderRequest, user: dict = Depends(get_current_user)
):
    """Reorder a track in the queue"""
    import db.ops.music_new as db_music
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        bot_id = await _get_bot_id_from_user(user)
        success = await db_music.reorder_queue_entry(
            db.pool, chat_id, bot_id, request.track_id, request.new_position
        )

        if success:
            return {"ok": True}
        else:
            raise HTTPException(status_code=404, detail="Track not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MUSIC_API] Error reordering queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{chat_id}/queue/{track_id}")
async def delete_queue_track(chat_id: int, track_id: int, user: dict = Depends(get_current_user)):
    """Remove a specific track from the queue"""
    import db.ops.music_new as db_music
    from db.client import db

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        bot_id = await _get_bot_id_from_user(user)
        success = await db_music.delete_queue_entry(db.pool, chat_id, bot_id, track_id)

        if success:
            return {"ok": True}
        else:
            raise HTTPException(status_code=404, detail="Track not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MUSIC_API] Error deleting queue track: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{chat_id}/sync")
async def sync_music(chat_id: int):
    """Sync music queue to all clone bots"""
    return {"status": "synced", "bots_count": 0}


@router.post("/{chat_id}/youtube")
async def play_youtube(chat_id: int, url: str):
    """Play music from YouTube URL"""
    return {"status": "downloading", "url": url}


# Health check endpoint
@router.get("/health")
async def health_check():
    """Check if music API is healthy"""
    return {"status": "healthy", "service": "music-player"}


@router.post("/{chat_id}/command")
async def send_music_command(
    chat_id: int, command: MusicCommand, user: dict = Depends(get_current_user)
):
    """Send a control command to the music player"""
    import time
    import uuid

    import db.ops.music_new as db_music
    from db.client import db

    if not db.redis:
        raise HTTPException(status_code=503, detail="Redis not available")

    try:
        bot_id = await _get_bot_id_from_user(user)

        # Handle musicmode command (update play_mode setting)
        if command.command == "musicmode":
            play_mode = command.value if command.value in ["all", "admins"] else "all"
            await db_music.upsert_music_settings(
                db.pool, chat_id=chat_id, bot_id=bot_id, play_mode=play_mode
            )
            return {"status": "ok", "command": command.command, "result": {"play_mode": play_mode}}

        # Command mapping for music service
        action_map = {
            "pause": "pause",
            "resume": "resume",
            "skip": "skip",
            "stop": "stop",
            "loop": "loop",
            "volume": "volume",
        }

        action = action_map.get(command.command)
        if not action:
            raise HTTPException(status_code=400, detail=f"Invalid command: {command.command}")

        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "action": action,
            "chat_id": chat_id,
            "bot_id": bot_id,
            "created_at": time.time(),
            "volume": int(command.value) if command.command == "volume" and command.value else None,
        }

        await db.redis.lpush(f"music:dispatch:{bot_id}", json.dumps(job))
        return {"status": "ok", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MUSIC_API] Error sending command: {e}")
        raise HTTPException(status_code=500, detail=str(e))
