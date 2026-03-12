"""
Music Player API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging

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


class MusicCommand(BaseModel):
    command: str


# In-memory storage (for demo - use Redis/DB in production)
music_queues_store = {}


@router.get("/{chat_id}/queue", response_model=MusicQueue)
async def get_music_queue(chat_id: int):
    """Get the current music queue for a group"""
    if chat_id not in music_queues_store:
        return MusicQueue()
    
    return MusicQueue(**music_queues_store[chat_id])


@router.post("/{chat_id}/command")
async def send_music_command(chat_id: int, cmd: MusicCommand):
    """Send a music command to the group (skip, stop, pause, etc.)"""
    # This is a simplified implementation
    # In a real system, you would use the bot to send commands to the Telegram group
    
    logger.info(f"Music command '{cmd.command}' for chat {chat_id}")
    
    # Note: Since we can't directly execute bot commands via API in this architecture,
    # users should use Telegram commands directly (/play, /skip, etc.)
    # This endpoint can be extended to work with a bot messaging system
    
    return {"status": "command_sent", "command": cmd.command}


@router.post("/{chat_id}/add")
async def add_to_queue(chat_id: int, track: Track):
    """Add a track to the music queue"""
    if chat_id not in music_queues_store:
        music_queues_store[chat_id] = {"current": None, "queue": []}
    
    music_queues_store[chat_id]["queue"].append(track.dict())
    logger.info(f"Added track '{track.title}' to queue for chat {chat_id}")
    
    return {"status": "added", "track": track.title}


@router.post("/{chat_id}/clear")
async def clear_queue(chat_id: int):
    """Clear the music queue for a group"""
    if chat_id in music_queues_store:
        music_queues_store[chat_id]["queue"] = []
        music_queues_store[chat_id]["current"] = None
    
    return {"status": "cleared"}
