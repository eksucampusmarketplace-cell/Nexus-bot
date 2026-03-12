"""
Advanced Music Player Handler with YouTube support, playlists, and multi-bot sync
"""

import logging
import os
import asyncio
import random
from typing import Optional, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Audio, Voice
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
import yt_dlp
import tempfile

logger = logging.getLogger(__name__)


async def download_from_youtube(url: str) -> Optional[Dict]:
    """
    Download audio from YouTube using yt-dlp
    Returns track dict with file_path, title, duration, etc.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': tempfile.gettempdir() + '/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            track = {
                'type': 'file',
                'file_path': ydl.prepare_filename(info),
                'title': info.get('title', 'Unknown'),
                'performer': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'url': url,
                'source': 'youtube'
            }

            # Clean up filename extension
            if track['file_path'].endswith('.webm'):
                track['file_path'] = track['file_path'][:-5] + '.mp3'

            logger.info(f"Downloaded: {track['title']}")
            return track

    except Exception as e:
        logger.error(f"YouTube download failed: {e}")
        return None


async def play_youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play music from YouTube URL"""
    if not update.message or not context.args:
        await update.message.reply_text(
            "🎵 <b>YouTube Music Player</b>\n\n"
            "Usage: /play_youtube <url>\n\n"
            "Example: /play_youtube https://youtube.com/watch?v=...",
            parse_mode=ParseMode.HTML
        )
        return

    url = context.args[0]
    await update.message.reply_text(f"🎬 Downloading from YouTube...\n\n{url[:50]}...")

    try:
        from bot.utils.music_helpers import get_queue, add_to_queue, play_next
        import db.ops.music as db_ops_music
        pool = context.bot_data.get("db_pool")

        # Download track
        track = await download_from_youtube(url)
        if not track:
            await update.message.reply_text("❌ Failed to download from YouTube. Check the URL and try again.")
            return

        # Add to queue
        await add_to_queue(update.effective_chat.id, track, pool)

        # Send the audio file
        with open(track['file_path'], 'rb') as audio_file:
            sent_message = await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=audio_file,
                title=track['title'],
                performer=track['performer'],
                duration=track['duration'],
                caption=f"🎵 <b>{track['title']}</b>\n\n"
                         f"👤 {track['performer']}\n"
                         f"⏱️ {track['duration']}s",
                parse_mode=ParseMode.HTML
            )

            # Update track with file_id for future playback
            track['file_id'] = sent_message.audio.file_id
            track['type'] = 'telegram'

            # Clean up temp file
            try:
                os.unlink(track['file_path'])
            except:
                pass

        await update.message.reply_text(
            f"✅ Added to queue: <b>{track['title']}</b>",
            parse_mode=ParseMode.HTML
        )

        # Start playing if not already
        queue_data = await get_queue(update.effective_chat.id, pool)
        if not queue_data.get('is_playing'):
            await play_next(update.effective_chat.id, context, pool)

    except Exception as e:
        logger.error(f"Error playing YouTube: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def volume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set volume (0-200, 100 is default)"""
    if not update.message:
        return

    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    if not context.args or not context.args[0].isdigit():
        current_volume = await db_ops_music.get_volume(pool, update.effective_chat.id)
        await update.message.reply_text(
            f"🔊 <b>Current Volume:</b> {current_volume}%\n\n"
            f"Usage: /volume <0-200>\n"
            f"Example: /volume 75",
            parse_mode=ParseMode.HTML
        )
        return

    volume = int(context.args[0])
    await db_ops_music.set_volume(pool, update.effective_chat.id, volume)
    await update.message.reply_text(f"🔊 Volume set to {volume}%")


async def repeat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set repeat mode"""
    if not update.message:
        return

    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    mode = context.args[0] if context.args else 'none'
    if mode not in ['none', 'one', 'all']:
        await update.message.reply_text(
            "🔄 <b>Repeat Mode</b>\n\n"
            "Usage: /repeat <mode>\n\n"
            "Modes:\n"
            "• none - Don't repeat (default)\n"
            "• one - Repeat current track\n"
            "• all - Repeat all tracks",
            parse_mode=ParseMode.HTML
        )
        return

    await db_ops_music.set_repeat_mode(pool, update.effective_chat.id, mode)
    mode_emoji = {'none': '🔁', 'one': '🔂', 'all': '🔁'}
    await update.message.reply_text(f"{mode_emoji.get(mode, '🔁')} Repeat mode: {mode}")


async def shuffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle shuffle mode"""
    if not update.message:
        return

    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    queue_data = await db_ops_music.get_or_create_queue(pool, update.effective_chat.id)
    current_shuffle = queue_data.get('shuffle_mode', False)
    new_shuffle = not current_shuffle

    await db_ops_music.set_shuffle_mode(pool, update.effective_chat.id, new_shuffle)
    status = "🔀 Enabled" if new_shuffle else "🔀 Disabled"
    await update.message.reply_text(f"{status} shuffle mode")


async def playlist_create_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a playlist"""
    if not update.message or not context.args:
        await update.message.reply_text(
            "📝 <b>Create Playlist</b>\n\n"
            "Usage: /playlist_create <name>\n\n"
            "Example: /playlist_create My Favorites",
            parse_mode=ParseMode.HTML
        )
        return

    playlist_name = ' '.join(context.args)
    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    # Get current queue
    queue_data = await db_ops_music.get_or_create_queue(pool, update.effective_chat.id)
    tracks = queue_data.get('queue', [])
    current_track = queue_data.get('current_track')

    all_tracks = []
    if current_track:
        all_tracks.append(current_track)
    all_tracks.extend(tracks)

    if not all_tracks:
        await update.message.reply_text("❌ No tracks to save. Add some music first!")
        return

    try:
        await db_ops_music.create_playlist(
            pool,
            update.effective_chat.id,
            playlist_name,
            all_tracks,
            update.effective_user.id
        )
        await update.message.reply_text(
            f"✅ Playlist '<b>{playlist_name}</b>' created with {len(all_tracks)} tracks!",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def playlist_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all playlists"""
    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    playlists = await db_ops_music.get_playlists(pool, update.effective_chat.id)

    if not playlists:
        await update.message.reply_text("📋 No playlists found.\nCreate one with /playlist_create <name>")
        return

    text = "📋 <b>Playlists</b>\n\n"
    for pl in playlists:
        tracks = pl.get('tracks', [])
        text += f"• <b>{pl['playlist_name']}</b> ({len(tracks)} tracks)\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def playlist_play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play a playlist"""
    if not update.message or not context.args:
        await update.message.reply_text(
            "🎵 <b>Play Playlist</b>\n\n"
            "Usage: /playlist_play <name>\n\n"
            "Example: /playlist_play My Favorites",
            parse_mode=ParseMode.HTML
        )
        return

    playlist_name = ' '.join(context.args)
    import db.ops.music as db_ops_music
    from bot.utils.music_helpers import add_tracks_to_queue, play_next
    pool = context.bot_data.get("db_pool")

    playlist = await db_ops_music.get_playlist(pool, update.effective_chat.id, playlist_name)
    if not playlist:
        await update.message.reply_text(f"❌ Playlist '{playlist_name}' not found.")
        return

    tracks = playlist.get('tracks', [])
    if not tracks:
        await update.message.reply_text(f"❌ Playlist '{playlist_name}' is empty.")
        return

    await add_tracks_to_queue(update.effective_chat.id, tracks, pool)
    await update.message.reply_text(
        f"✅ Added {len(tracks)} tracks from '<b>{playlist_name}</b>' to queue!",
        parse_mode=ParseMode.HTML
    )

    # Start playing
    await play_next(update.effective_chat.id, context, pool)


async def playlist_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a playlist"""
    if not update.message or not context.args:
        await update.message.reply_text(
            "🗑️ <b>Delete Playlist</b>\n\n"
            "Usage: /playlist_delete <name>\n\n"
            "Example: /playlist_delete My Favorites",
            parse_mode=ParseMode.HTML
        )
        return

    playlist_name = ' '.join(context.args)
    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    await db_ops_music.delete_playlist(pool, update.effective_chat.id, playlist_name)
    await update.message.reply_text(
        f"🗑️ Playlist '<b>{playlist_name}</b>' deleted!",
        parse_mode=ParseMode.HTML
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show play history"""
    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    limit = int(context.args[0]) if context.args and context.args[0].isdigit() else 10
    limit = min(limit, 50)

    history = await db_ops_music.get_history(pool, update.effective_chat.id, limit)

    if not history:
        await update.message.reply_text("📜 No play history yet.")
        return

    text = f"📜 <b>Play History (Last {limit})</b>\n\n"
    for i, entry in enumerate(history, 1):
        track = entry['track_data']
        played_at = entry['played_at'].strftime('%H:%M')
        text += f"{i}. {track.get('title', 'Unknown')} - {played_at}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search in queue and playlists"""
    if not update.message or not context.args:
        await update.message.reply_text(
            "🔍 <b>Search Music</b>\n\n"
            "Usage: /search <query>\n\n"
            "Searches in current queue and all playlists.",
            parse_mode=ParseMode.HTML
        )
        return

    query = ' '.join(context.args).lower()
    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    # Search in current queue
    queue_data = await db_ops_music.get_or_create_queue(pool, update.effective_chat.id)
    queue_tracks = queue_data.get('queue', [])

    results = []
    for track in queue_tracks:
        title = track.get('title', '').lower()
        if query in title:
            results.append(('Queue', track))

    # Search in playlists
    playlists = await db_ops_music.get_playlists(pool, update.effective_chat.id)
    for pl in playlists:
        for track in pl.get('tracks', []):
            title = track.get('title', '').lower()
            if query in title:
                results.append((f"Playlist: {pl['playlist_name']}", track))

    if not results:
        await update.message.reply_text(f"🔍 No results found for '{query}'")
        return

    text = f"🔍 <b>Search Results: '{query}'</b>\n\n"
    for source, track in results[:10]:
        text += f"• <b>{track.get('title', 'Unknown')}</b>\n"
        text += f"  📂 {source}\n"
        if track.get('performer'):
            text += f"  👤 {track['performer']}\n"
        text += "\n"

    await update.message.reply_text(text[:4096], parse_mode=ParseMode.HTML)


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sync music to all clone bots"""
    if not update.message:
        return

    import db.ops.bots as db_ops_bots
    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    # Check if user is owner
    from config import settings
    if update.effective_user.id != settings.OWNER_ID:
        await update.message.reply_text("❌ Only the bot owner can sync music.")
        return

    await update.message.reply_text("🔄 Syncing music to all bots...")

    try:
        # Get current queue
        queue_data = await db_ops_music.get_or_create_queue(pool, update.effective_chat.id)

        # Get all active bots
        from bot.registry import get_all as registry_get_all
        all_bots = registry_get_all()

        synced_count = 0
        for bot_id, bot_app in all_bots.items():
            try:
                # Update queue for each bot's chats
                await db_ops_music.update_queue(
                    pool,
                    update.effective_chat.id,
                    queue_data.get('queue', []),
                    queue_data.get('current_track'),
                    queue_data.get('is_playing', False)
                )
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync to bot {bot_id}: {e}")

        await update.message.reply_text(
            f"✅ Synced to {synced_count}/{len(all_bots)} bots"
        )
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        await update.message.reply_text(f"❌ Sync failed: {str(e)}")


async def music_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show music settings with interactive buttons"""
    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    queue_data = await db_ops_music.get_or_create_queue(pool, update.effective_chat.id)

    volume = queue_data.get('volume', 100)
    repeat = queue_data.get('repeat_mode', 'none')
    shuffle = queue_data.get('shuffle_mode', False)

    text = f"⚙️ <b>Music Settings</b>\n\n"
    text += f"🔊 Volume: {volume}%\n"
    text += f"🔄 Repeat: {repeat}\n"
    text += f"🔀 Shuffle: {'✅' if shuffle else '❌'}\n"

    keyboard = [
        [
            InlineKeyboardButton("🔉 Volume -10", callback_data=f"music:vol:-10:{update.effective_chat.id}"),
            InlineKeyboardButton("🔊 Volume +10", callback_data=f"music:vol:+10:{update.effective_chat.id}")
        ],
        [
            InlineKeyboardButton("🔁 None", callback_data=f"music:repeat:none:{update.effective_chat.id}"),
            InlineKeyboardButton("🔂 One", callback_data=f"music:repeat:one:{update.effective_chat.id}"),
            InlineKeyboardButton("🔁 All", callback_data=f"music:repeat:all:{update.effective_chat.id}")
        ],
        [
            InlineKeyboardButton("🔀 Toggle Shuffle", callback_data=f"music:shuffle:{update.effective_chat.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def music_advanced_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle advanced music callbacks"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':')
    if len(parts) < 3:
        return

    action = parts[1]
    chat_id = int(parts[2])

    import db.ops.music as db_ops_music
    pool = context.bot_data.get("db_pool")

    try:
        if action.startswith('vol'):
            volume_change = int(parts[1].split('_')[1])
            current_volume = await db_ops_music.get_volume(pool, chat_id)
            new_volume = max(0, min(200, current_volume + volume_change))
            await db_ops_music.set_volume(pool, chat_id, new_volume)
            await query.edit_message_text(f"🔊 Volume set to {new_volume}%")

        elif action == 'repeat':
            mode = parts[2]
            await db_ops_music.set_repeat_mode(pool, chat_id, mode)
            await query.edit_message_text(f"🔄 Repeat mode: {mode}")

        elif action == 'shuffle':
            current = await db_ops_music.get_shuffle_mode(pool, chat_id)
            new_mode = not current
            await db_ops_music.set_shuffle_mode(pool, chat_id, new_mode)
            status = "✅ Enabled" if new_mode else "❌ Disabled"
            await query.edit_message_text(f"🔀 Shuffle {status}")

    except Exception as e:
        logger.error(f"Error in music advanced callback: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")
