"""
Database operations for music player
Handles persistence of music queues, playlists, and settings
"""

import logging
import json
from typing import Optional, List, Dict
from datetime import datetime
import asyncpg

logger = logging.getLogger(__name__)


async def create_music_tables(pool: asyncpg.Pool):
    """Create music player tables if they don't exist"""
    async with pool.acquire() as conn:
        # Music queues table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_queues (
                id BIGSERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL UNIQUE,
                queue JSONB DEFAULT '[]'::jsonb,
                current_track JSONB,
                is_playing BOOLEAN DEFAULT FALSE,
                volume INTEGER DEFAULT 100,
                repeat_mode VARCHAR(20) DEFAULT 'none', -- none, one, all
                shuffle_mode BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Playlists table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_playlists (
                id BIGSERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                playlist_name VARCHAR(255) NOT NULL,
                tracks JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_by BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(chat_id, playlist_name)
            )
        """)

        # Music history table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_history (
                id BIGSERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                track_data JSONB NOT NULL,
                played_at TIMESTAMP DEFAULT NOW(),
                played_by BIGINT
            )
        """)

        # Create indexes
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_music_queues_chat_id ON music_queues(chat_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_playlists_chat_id ON music_playlists(chat_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_chat_id ON music_history(chat_id, played_at DESC)"
        )

        logger.info("Music tables created successfully")


async def get_or_create_queue(pool: asyncpg.Pool, chat_id: int) -> Optional[Dict]:
    """Get queue for a chat, create if doesn't exist"""
    async with pool.acquire() as conn:
        queue = await conn.fetchrow("SELECT * FROM music_queues WHERE chat_id = $1", chat_id)

        if not queue:
            queue = await conn.fetchrow(
                """
                INSERT INTO music_queues (chat_id)
                VALUES ($1)
                RETURNING *
                """,
                chat_id,
            )
            logger.info(f"Created new music queue for chat {chat_id}")

        return dict(queue)


async def update_queue(
    pool: asyncpg.Pool,
    chat_id: int,
    queue: List[Dict],
    current_track: Optional[Dict] = None,
    is_playing: bool = False,
):
    """Update queue for a chat"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE music_queues
            SET queue = $2, current_track = $3, is_playing = $4, updated_at = NOW()
            WHERE chat_id = $1
            """,
            chat_id,
            json.dumps(queue),
            json.dumps(current_track) if current_track else None,
            is_playing,
        )


async def clear_queue(pool: asyncpg.Pool, chat_id: int):
    """Clear queue for a chat"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE music_queues
            SET queue = '[]'::jsonb, current_track = NULL, is_playing = FALSE, updated_at = NOW()
            WHERE chat_id = $1
            """,
            chat_id,
        )


async def get_volume(pool: asyncpg.Pool, chat_id: int) -> int:
    """Get volume for a chat"""
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT volume FROM music_queues WHERE chat_id = $1", chat_id)
        return result or 100


async def set_volume(pool: asyncpg.Pool, chat_id: int, volume: int):
    """Set volume for a chat (0-200)"""
    volume = max(0, min(200, volume))  # Clamp between 0 and 200
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE music_queues
            SET volume = $1, updated_at = NOW()
            WHERE chat_id = $2
            """,
            volume,
            chat_id,
        )


async def get_repeat_mode(pool: asyncpg.Pool, chat_id: int) -> str:
    """Get repeat mode for a chat"""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT repeat_mode FROM music_queues WHERE chat_id = $1", chat_id
        )
        return result or "none"


async def set_repeat_mode(pool: asyncpg.Pool, chat_id: int, mode: str):
    """Set repeat mode: 'none', 'one', 'all'"""
    if mode not in ["none", "one", "all"]:
        raise ValueError("Invalid repeat mode. Must be 'none', 'one', or 'all'")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE music_queues
            SET repeat_mode = $1, updated_at = NOW()
            WHERE chat_id = $2
            """,
            mode,
            chat_id,
        )


async def get_shuffle_mode(pool: asyncpg.Pool, chat_id: int) -> bool:
    """Get shuffle mode for a chat"""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT shuffle_mode FROM music_queues WHERE chat_id = $1", chat_id
        )
        return result or False


async def set_shuffle_mode(pool: asyncpg.Pool, chat_id: int, shuffle: bool):
    """Set shuffle mode for a chat"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE music_queues
            SET shuffle_mode = $1, updated_at = NOW()
            WHERE chat_id = $2
            """,
            shuffle,
            chat_id,
        )


async def create_playlist(
    pool: asyncpg.Pool, chat_id: int, playlist_name: str, tracks: List[Dict], created_by: int
):
    """Create a playlist"""
    async with pool.acquire() as conn:
        playlist = await conn.fetchrow(
            """
            INSERT INTO music_playlists (chat_id, playlist_name, tracks, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            chat_id,
            playlist_name,
            json.dumps(tracks),
            created_by,
        )
        logger.info(f"Created playlist '{playlist_name}' for chat {chat_id}")
        return dict(playlist)


async def get_playlists(pool: asyncpg.Pool, chat_id: int) -> List[Dict]:
    """Get all playlists for a chat"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM music_playlists WHERE chat_id = $1 ORDER BY created_at DESC", chat_id
        )
        return [dict(row) for row in rows]


async def get_playlist(pool: asyncpg.Pool, chat_id: int, playlist_name: str) -> Optional[Dict]:
    """Get a specific playlist"""
    async with pool.acquire() as conn:
        playlist = await conn.fetchrow(
            """
            SELECT * FROM music_playlists
            WHERE chat_id = $1 AND playlist_name = $2
            """,
            chat_id,
            playlist_name,
        )
        return dict(playlist) if playlist else None


async def delete_playlist(pool: asyncpg.Pool, chat_id: int, playlist_name: str):
    """Delete a playlist"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM music_playlists
            WHERE chat_id = $1 AND playlist_name = $2
            """,
            chat_id,
            playlist_name,
        )
        logger.info(f"Deleted playlist '{playlist_name}' for chat {chat_id}")


async def update_playlist(pool: asyncpg.Pool, chat_id: int, playlist_name: str, tracks: List[Dict]):
    """Update a playlist"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE music_playlists
            SET tracks = $3, updated_at = NOW()
            WHERE chat_id = $1 AND playlist_name = $2
            """,
            chat_id,
            playlist_name,
            json.dumps(tracks),
        )


async def add_to_history(pool: asyncpg.Pool, chat_id: int, track: Dict, played_by: int):
    """Add track to play history"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO music_history (chat_id, track_data, played_by)
            VALUES ($1, $2, $3)
            """,
            chat_id,
            json.dumps(track),
            played_by,
        )


async def get_history(pool: asyncpg.Pool, chat_id: int, limit: int = 20) -> List[Dict]:
    """Get play history for a chat"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM music_history
            WHERE chat_id = $1
            ORDER BY played_at DESC
            LIMIT $2
            """,
            chat_id,
            limit,
        )
        return [dict(row) for row in rows]


async def get_all_active_queues(pool: asyncpg.Pool) -> List[Dict]:
    """Get all queues with data for multi-bot sync"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM music_queues WHERE queue::text != '[]'::text OR current_track IS NOT NULL"
        )
        return [dict(row) for row in rows]


# Aliases and missing functions for API compatibility

# Aliases for import compatibility
set_repeat = set_repeat_mode
set_shuffle = set_shuffle_mode


async def add_to_queue(pool: asyncpg.Pool, chat_id: int, track: Dict):
    """Add a track to the queue"""
    queue_data = await get_or_create_queue(pool, chat_id)
    queue = queue_data.get("queue", []) or []
    queue.append(track)
    await update_queue(
        pool,
        chat_id,
        queue,
        current_track=queue_data.get("current_track"),
        is_playing=queue_data.get("is_playing", False),
    )


async def get_queue(pool: asyncpg.Pool, chat_id: int) -> List[Dict]:
    """Get queue for a chat"""
    queue_data = await get_or_create_queue(pool, chat_id)
    return queue_data.get("queue", []) or []


async def skip_track(pool: asyncpg.Pool, chat_id: int) -> Optional[Dict]:
    """Skip current track and return next track"""
    queue_data = await get_or_create_queue(pool, chat_id)
    queue = queue_data.get("queue", []) or []
    next_track = queue.pop(0) if queue else None
    await update_queue(
        pool, chat_id, queue, current_track=next_track, is_playing=next_track is not None
    )
    return next_track


async def pause_track(pool: asyncpg.Pool, chat_id: int):
    """Pause current track"""
    queue_data = await get_or_create_queue(pool, chat_id)
    await update_queue(
        pool,
        chat_id,
        queue_data.get("queue", []) or [],
        current_track=queue_data.get("current_track"),
        is_playing=False,
    )


async def resume_track(pool: asyncpg.Pool, chat_id: int):
    """Resume current track"""
    queue_data = await get_or_create_queue(pool, chat_id)
    await update_queue(
        pool,
        chat_id,
        queue_data.get("queue", []) or [],
        current_track=queue_data.get("current_track"),
        is_playing=True,
    )


async def get_current_track(pool: asyncpg.Pool, chat_id: int) -> Optional[Dict]:
    """Get current playing track"""
    queue_data = await get_or_create_queue(pool, chat_id)
    return queue_data.get("current_track")


async def get_player_state(pool: asyncpg.Pool, chat_id: int) -> Dict:
    """Get full player state for a chat"""
    queue_data = await get_or_create_queue(pool, chat_id)
    return {
        "current_track": queue_data.get("current_track"),
        "queue": queue_data.get("queue", []) or [],
        "is_playing": queue_data.get("is_playing", False),
        "volume": queue_data.get("volume", 100),
        "repeat_mode": queue_data.get("repeat_mode", "none"),
        "shuffle_mode": queue_data.get("shuffle_mode", False),
    }


async def add_to_playlist(pool: asyncpg.Pool, chat_id: int, playlist_name: str, track: Dict):
    """Add a track to a playlist"""
    playlist = await get_playlist(pool, chat_id, playlist_name)
    if not playlist:
        raise ValueError(f"Playlist '{playlist_name}' not found")

    tracks = playlist.get("tracks", []) or []
    tracks.append(track)
    await update_playlist(pool, chat_id, playlist_name, tracks)


async def get_playlist_tracks(pool: asyncpg.Pool, chat_id: int, playlist_name: str) -> List[Dict]:
    """Get tracks from a playlist"""
    playlist = await get_playlist(pool, chat_id, playlist_name)
    return playlist.get("tracks", []) if playlist else []


async def search_youtube(query: str) -> List[Dict]:
    """Search YouTube for tracks (placeholder - requires yt-dlp integration)"""
    # This is a placeholder - actual implementation would use yt-dlp
    logger.warning("search_youtube called but not fully implemented")
    return []


async def play_youtube(pool: asyncpg.Pool, chat_id: int, url: str, requested_by: int) -> Dict:
    """Play a YouTube URL (placeholder - requires yt-dlp integration)"""
    # This is a placeholder - actual implementation would use yt-dlp
    logger.warning("play_youtube called but not fully implemented")
    track = {
        "title": "Unknown",
        "url": url,
        "requested_by": requested_by,
        "duration": 0,
    }
    await add_to_queue(pool, chat_id, track)
    return track
