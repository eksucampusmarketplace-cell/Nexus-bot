"""
Music Helper Functions
Shared utilities for music player operations
"""

import logging
import random
from typing import Dict, List, Optional
import db.ops.music as db_ops_music

logger = logging.getLogger(__name__)


async def get_queue(chat_id: int, pool) -> Optional[Dict]:
    """Get queue for a chat"""
    return await db_ops_music.get_or_create_queue(pool, chat_id)


async def add_to_queue(chat_id: int, track: Dict, pool):
    """Add a track to the queue"""
    queue_data = await get_queue(chat_id, pool)
    queue = queue_data.get("queue", [])

    # Check shuffle mode
    if queue_data.get("shuffle_mode", False):
        # Insert at random position
        pos = random.randint(0, len(queue))
        queue.insert(pos, track)
        logger.info(f"Added track at random position {pos} (shuffle mode)")
    else:
        queue.append(track)

    await db_ops_music.update_queue(pool, chat_id, queue)
    logger.info(f"Added track to queue: {track.get('title', 'Unknown')}")


async def add_tracks_to_queue(chat_id: int, tracks: List[Dict], pool):
    """Add multiple tracks to the queue"""
    queue_data = await get_queue(chat_id, pool)
    queue = queue_data.get("queue", [])

    if queue_data.get("shuffle_mode", False):
        random.shuffle(tracks)

    queue.extend(tracks)
    await db_ops_music.update_queue(pool, chat_id, queue)
    logger.info(f"Added {len(tracks)} tracks to queue")


async def play_next(chat_id: int, context, pool):
    """Play the next track in the queue"""
    queue_data = await get_queue(chat_id, pool)
    queue = queue_data.get("queue", [])
    current_track = queue_data.get("current_track")

    repeat_mode = queue_data.get("repeat_mode", "none")

    # Check repeat modes
    if current_track:
        if repeat_mode == "one":
            # Repeat current track
            await _play_track(chat_id, context, current_track, pool)
            return
        elif repeat_mode == "all":
            # Add current track to end of queue
            queue.append(current_track)
            await db_ops_music.update_queue(pool, chat_id, queue)

    if not queue:
        # No more tracks
        await db_ops_music.update_queue(pool, chat_id, queue, None, False)
        logger.info(f"Queue empty for chat {chat_id}")
        return

    # Get next track
    next_track = queue.pop(0)
    await db_ops_music.update_queue(pool, chat_id, queue, next_track, True)

    # Play the track
    await _play_track(chat_id, context, next_track, pool)

    # Add to history
    try:
        from bot.factory import create_application

        # Get bot from context
        user_id = context._user_id if hasattr(context, "_user_id") else None
        await db_ops_music.add_to_history(pool, chat_id, next_track, user_id)
    except:
        pass

    # Auto-play next after delay
    if queue:
        await asyncio.sleep(5)
        await play_next(chat_id, context, pool)


async def _play_track(chat_id: int, context, track: Dict, pool):
    """Play a single track"""
    try:
        if track.get("type") == "telegram":
            # Re-send the audio file
            file_id = track.get("file_id")
            title = track.get("title", "Unknown")
            performer = track.get("performer", "Unknown")

            caption = f"🎵 <b>{title}</b>"
            if performer and performer != "Unknown":
                caption += f"\n👤 {performer}"

            try:
                await context.bot.send_audio(
                    chat_id=chat_id, audio=file_id, caption=caption, parse_mode="HTML"
                )
            except Exception:
                # Try voice format
                await context.bot.send_voice(chat_id=chat_id, voice=file_id, caption=caption)

            logger.info(f"Playing: {title}")

    except Exception as e:
        logger.error(f"Error playing track: {e}")


def shuffle_queue(queue: List[Dict]) -> List[Dict]:
    """Shuffle a queue using Fisher-Yates algorithm"""
    shuffled = queue.copy()
    for i in range(len(shuffled) - 1, 0, -1):
        j = random.randint(0, i)
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    return shuffled


async def sync_queue_to_all_bots(chat_id: int, pool, registry):
    """Sync queue to all registered bots"""
    try:
        queue_data = await get_queue(chat_id, pool)

        # Get all bots
        all_bots = registry.get_all()

        synced = 0
        for bot_id, bot_app in all_bots.items():
            try:
                # Update queue for this bot
                await db_ops_music.update_queue(
                    pool,
                    chat_id,
                    queue_data.get("queue", []),
                    queue_data.get("current_track"),
                    queue_data.get("is_playing", False),
                )
                synced += 1
            except Exception as e:
                logger.error(f"Failed to sync to bot {bot_id}: {e}")

        logger.info(f"Synced queue to {synced}/{len(all_bots)} bots")
        return synced

    except Exception as e:
        logger.error(f"Queue sync failed: {e}")
        return 0


import asyncio
