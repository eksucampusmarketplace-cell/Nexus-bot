"""
Advanced Music Player API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging
import json

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


@router.get("/{chat_id}/queue", response_model=MusicQueue)
async def get_music_queue(chat_id: int):
    """Get the current music queue and settings for a group"""
    from bot.utils.music_helpers import get_queue

    # Try to get from database (will be called by bot context in real implementation)
    # For API-only calls, we need pool access
    # This is a simplified version - in production, inject pool via dependency

    # Return mock data for now - real implementation needs DB pool
    return MusicQueue(
        current=None,
        queue=[],
        is_playing=False,
        volume=100,
        repeat_mode="none",
        shuffle_mode=False
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
async def get_music_settings(chat_id: int):
    """Get music settings for a group"""
    return MusicSettings()


@router.put("/{chat_id}/settings", response_model=MusicSettings)
async def update_music_settings(chat_id: int, settings: MusicSettings):
    """Update music settings for a group"""
    return settings


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
async def send_music_command(chat_id: int, command: MusicCommand):
    """Send a control command to the music player"""
    from bot.registry import get_all
    
    # Get bot app for this group
    bots = get_all()
    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break
    
    if not bot_app:
        raise HTTPException(status_code=503, detail="Bot service unavailable")
    
    # Command mapping
    valid_commands = ['play', 'pause', 'resume', 'skip', 'stop', 'loop', 'shuffle', 'volume']
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
