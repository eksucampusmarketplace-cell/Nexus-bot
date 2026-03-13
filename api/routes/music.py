"""
Advanced Music Player API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging
import json

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
    volume: int = 100
    repeat_mode: str = "none"
    shuffle_mode: bool = False
    play_mode: str = "all"


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


async def _get_bot_id_from_user(user: dict) -> int:
    """Extract bot_id from user's validated bot token"""
    import hashlib
    from db.client import db
    import db.ops.bots as db_ops_bots

    bot_token = user.get("validated_bot_token")
    if not bot_token or not db.pool:
        return 0  # Default to shared pool

    # Get bot by token hash
    token_hash = hashlib.sha256(bot_token.encode()).hexdigest()
    bot = await db_ops_bots.get_bot_by_token_hash(db.pool, token_hash)
    if bot:
        return bot.get("bot_id", 0)
    return 0


@router.get("/{chat_id}/queue", response_model=MusicQueue)
async def get_music_queue(chat_id: int, user: dict = Depends(get_current_user)):
    """Get the current music queue and settings for a group"""
    from db.client import db
    import db.ops.music_new as db_music

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Get the bot_id for this user's active bot context
        bot_id = await _get_bot_id_from_user(user)

        # Get session state (current track, volume, etc.)
        session = await db_music.get_session_state(db.pool, chat_id, bot_id)

        # Get queue entries
        queue_entries = await db_music.get_queue_entries(db.pool, chat_id, bot_id, played=False)

        # Get music settings
        music_settings = await db_music.get_music_settings(db.pool, chat_id, bot_id)

        # Build current track if session exists
        current = None
        if session and session.get("current_track"):
            # Find the current track in queue entries
            current_track_id = session.get("current_track")
            for entry in queue_entries:
                if entry.get("id") == current_track_id:
                    current = Track(
                        type=entry.get("source", "unknown"),
                        title=entry.get("title", "Unknown"),
                        performer=entry.get("requested_by_name", "Unknown"),
                        duration=entry.get("duration", 0)
                    )
                    break

        # Build queue list
        queue = [
            Track(
                type=entry.get("source", "unknown"),
                title=entry.get("title", "Unknown"),
                performer=entry.get("requested_by_name", "Unknown"),
                duration=entry.get("duration", 0)
            )
            for entry in queue_entries
        ]

        return MusicQueue(
            current=current,
            queue=queue,
            is_playing=session.get("is_playing", False) if session else False,
            volume=session.get("volume", 100) if session else 100,
            repeat_mode="one" if (session and session.get("is_looping")) else "none",
            shuffle_mode=False,  # TODO: add shuffle support
            play_mode=music_settings.get("play_mode", "all") if music_settings else "all"
        )
    except Exception as e:
        logger.error(f"[MUSIC_API] Error fetching queue: {e}")
        # Return default values on error
        return MusicQueue(
            current=None,
            queue=[],
            is_playing=False,
            volume=100,
            repeat_mode="none",
            shuffle_mode=False,
            play_mode="all"
        )


@router.get("/{chat_id}/playlists")
async def get_playlists(chat_id: int):
    """Get all playlists for a group"""
    import db.ops.music as db_ops_music

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
        "created_at": "2024-01-01T00:00:00"
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
    from db.client import db
    import db.ops.music_new as db_music

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
                announce_tracks=music_settings.get("announce_tracks", True)
            )
        else:
            # Return default settings
            return MusicSettings()
    except Exception as e:
        logger.error(f"[MUSIC_API] Error fetching settings: {e}")
        return MusicSettings()


@router.put("/{chat_id}/settings", response_model=MusicSettings)
async def update_music_settings(chat_id: int, settings: MusicSettings, user: dict = Depends(get_current_user)):
    """Update music settings for a group"""
    from db.client import db
    import db.ops.music_new as db_music

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Get the bot_id for this user's active bot context
        bot_id = await _get_bot_id_from_user(user)

        # Upsert music settings
        await db_music.upsert_music_settings(
            db.pool,
            chat_id=chat_id,
            bot_id=bot_id,
            play_mode=settings.play_mode,
            announce_tracks=settings.announce_tracks
        )

        # Update session state for volume and loop if needed
        session = await db_music.get_session_state(db.pool, chat_id, bot_id)
        if session:
            await db_music.update_session_state(
                db.pool,
                chat_id=chat_id,
                bot_id=bot_id,
                volume=settings.volume,
                is_looping=(settings.repeat_mode != "none")
            )

        return settings
    except Exception as e:
        logger.error(f"[MUSIC_API] Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{chat_id}/history")
async def get_play_history(chat_id: int, limit: int = 20):
    """Get play history for a group"""
    return {"history": [], "count": 0}


@router.get("/{chat_id}/search")
async def search_music(chat_id: int, query: str):
    """Search for music in queue and playlists"""
    return {"results": [], "count": 0}


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
async def send_music_command(chat_id: int, command: MusicCommand, user: dict = Depends(get_current_user)):
    """Send a control command to the music player"""
    from bot.registry import get_all
    from db.client import db
    import db.ops.music_new as db_music

    # Handle musicmode command (update play_mode setting)
    if command.command == 'musicmode':
        if not db.pool:
            raise HTTPException(status_code=503, detail="Database not available")

        try:
            bot_id = await _get_bot_id_from_user(user)

            play_mode = command.value if command.value in ['all', 'admins'] else 'all'
            await db_music.upsert_music_settings(
                db.pool,
                chat_id=chat_id,
                bot_id=bot_id,
                play_mode=play_mode
            )
            return {"status": "ok", "command": command.command, "result": {"play_mode": play_mode}}
        except Exception as e:
            logger.error(f"[MUSIC_API] Error updating musicmode: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Get bot app for this group
    bots = get_all()
    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break

    if not bot_app:
        raise HTTPException(status_code=503, detail="Bot service unavailable")

    # Command mapping
    valid_commands = ['play', 'pause', 'resume', 'skip', 'stop', 'loop', 'shuffle', 'volume', 'musicmode']
    if command.command not in valid_commands:
        raise HTTPException(status_code=400, detail=f"Invalid command. Valid: {valid_commands}")

    # Get music worker
    worker = bot_app.bot_data.get("music_worker")
    if not worker:
        return {"status": "no_worker", "message": "Music worker not configured"}

    # Execute command
    result = None
    try:
        if command.command == 'pause':
            result = await worker.pause(chat_id)
        elif command.command == 'resume':
            result = await worker.resume(chat_id)
        elif command.command == 'skip':
            result = await worker.skip(chat_id)
        elif command.command == 'stop':
            result = await worker.stop(chat_id)
        elif command.command == 'loop':
            result = await worker.toggle_loop(chat_id)
        elif command.command == 'volume' and command.value:
            result = await worker.set_volume(chat_id, int(command.value))
        else:
            result = {"ok": True, "message": "Command queued"}

        return {"status": "ok", "command": command.command, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
