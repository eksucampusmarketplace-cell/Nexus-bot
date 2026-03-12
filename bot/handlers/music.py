"""
Music Player Handler for Nexus Bot
Supports playing audio files, voice messages, and YouTube links (via yt-dlp)
"""

import logging
import os
import tempfile
import asyncio
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Audio, Voice
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# In-memory queue storage (for demo purposes - use Redis/DB in production)
# Structure: {chat_id: {'queue': [], 'current': None, 'is_playing': False}}
music_queues: Dict[int, dict] = {}


async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /play command - play audio from reply or attachment"""
    chat_id = update.effective_chat.id
    
    if not update.message:
        return
    
    # Check if there's a replied message with audio/voice
    if update.message.reply_to_message:
        replied_msg = update.message.reply_to_message
        audio = replied_msg.audio or replied_msg.voice
        
        if audio:
            await _add_to_queue(chat_id, {
                'type': 'telegram',
                'file_id': audio.file_id,
                'title': audio.title or 'Audio',
                'performer': audio.performer or 'Unknown',
                'duration': audio.duration or 0
            })
            await update.message.reply_text(
                f"🎵 Added to queue: <b>{audio.title or 'Audio'}</b>",
                parse_mode=ParseMode.HTML
            )
            if not music_queues.get(chat_id, {}).get('is_playing'):
                await _play_next(chat_id, context)
            return
    
    # Check for attached audio file
    if update.message.audio:
        audio = update.message.audio
        await _add_to_queue(chat_id, {
            'type': 'telegram',
            'file_id': audio.file_id,
            'title': audio.title or 'Audio',
            'performer': audio.performer or 'Unknown',
            'duration': audio.duration or 0
        })
        await update.message.reply_text(
            f"🎵 Added to queue: <b>{audio.title or 'Audio'}</b>",
            parse_mode=ParseMode.HTML
        )
        if not music_queues.get(chat_id, {}).get('is_playing'):
            await _play_next(chat_id, context)
        return
    
    # Check for voice message
    if update.message.voice:
        voice = update.message.voice
        await _add_to_queue(chat_id, {
            'type': 'telegram',
            'file_id': voice.file_id,
            'title': 'Voice Message',
            'performer': 'Unknown',
            'duration': voice.duration or 0
        })
        await update.message.reply_text("🎵 Voice message added to queue")
        if not music_queues.get(chat_id, {}).get('is_playing'):
            await _play_next(chat_id, context)
        return
    
    # Check for URL argument
    if context.args and len(context.args) > 0:
        url = context.args[0]
        await _add_to_queue(chat_id, {
            'type': 'url',
            'url': url,
            'title': url,
            'performer': 'Unknown',
            'duration': 0
        })
        await update.message.reply_text(f"🎵 Added to queue: {url}")
        if not music_queues.get(chat_id, {}).get('is_playing'):
            await _play_next(chat_id, context)
        return
    
    # No audio found
    await update.message.reply_text(
        "🎵 <b>How to play music:</b>\n\n"
        "1. Reply to an audio/voice message with /play\n"
        "2. Send an audio file with /play command\n"
        "3. Use /play <url> to play from URL",
        parse_mode=ParseMode.HTML
    )


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip the current track"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queues or not music_queues[chat_id]['queue']:
        await update.message.reply_text("❌ No music playing")
        return
    
    current = music_queues[chat_id]['current']
    if current:
        await update.message.reply_text(f"⏭️ Skipped: <b>{current['title']}</b>", parse_mode=ParseMode.HTML)
        await _play_next(chat_id, context)
    else:
        await update.message.reply_text("❌ No track playing")


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current music queue"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queues or not music_queues[chat_id]['queue']:
        await update.message.reply_text("📭 Queue is empty")
        return
    
    queue = music_queues[chat_id]['queue']
    current = music_queues[chat_id]['current']
    
    text = "🎵 <b>Music Queue</b>\n\n"
    
    if current:
        text += f"▶️ <b>Now Playing:</b>\n"
        text += f"   {current['title']}\n"
        if current.get('performer'):
            text += f"   By: {current['performer']}\n"
        text += "\n"
    
    if queue:
        text += "<b>Up Next:</b>\n"
        for i, track in enumerate(queue[:10], 1):  # Show max 10 tracks
            text += f"{i}. {track['title']}\n"
        
        if len(queue) > 10:
            text += f"\n... and {len(queue) - 10} more tracks"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop playing music and clear the queue"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queues:
        await update.message.reply_text("❌ No music playing")
        return
    
    music_queues[chat_id]['queue'] = []
    music_queues[chat_id]['current'] = None
    music_queues[chat_id]['is_playing'] = False
    
    await update.message.reply_text("⏹️ Music stopped and queue cleared")


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause playback (simulated - Telegram doesn't support actual pause)"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queues or not music_queues[chat_id]['is_playing']:
        await update.message.reply_text("❌ No music playing")
        return
    
    music_queues[chat_id]['is_playing'] = False
    await update.message.reply_text("⏸️ Paused (simulated)")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume playback"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queues or not music_queues[chat_id]['current']:
        await update.message.reply_text("❌ No paused music")
        return
    
    music_queues[chat_id]['is_playing'] = True
    current = music_queues[chat_id]['current']
    await update.message.reply_text(f"▶️ Resumed: <b>{current['title']}</b>", parse_mode=ParseMode.HTML)
    await _play_next(chat_id, context)


async def nowplaying_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the currently playing track"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queues or not music_queues[chat_id]['current']:
        await update.message.reply_text("❌ No music playing")
        return
    
    current = music_queues[chat_id]['current']
    text = f"🎵 <b>Now Playing:</b>\n"
    text += f"<b>{current['title']}</b>\n"
    if current.get('performer'):
        text += f"By: {current['performer']}\n"
    if current.get('duration'):
        text += f"Duration: {current['duration']}s\n"
    
    keyboard = [
        [
            InlineKeyboardButton("⏸️ Pause", callback_data=f"music:pause:{chat_id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"music:skip:{chat_id}")
        ],
        [
            InlineKeyboardButton("📋 Queue", callback_data=f"music:queue:{chat_id}"),
            InlineKeyboardButton("⏹️ Stop", callback_data=f"music:stop:{chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def music_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks for music controls"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(':')
    if len(parts) < 3:
        return
    
    action, chat_id_str = parts[1], parts[2]
    
    try:
        # Simulate the command by calling the handler
        # Create a fake update object
        fake_update = type('Update', (), {
            'effective_chat': type('Chat', (), {'id': int(chat_id_str)})(),
            'message': type('Message', (), {
                'reply_text': lambda text, **kwargs: asyncio.create_task(
                    query.edit_message_text(text=text, **kwargs)
                )
            })(),
            'callback_query': query
        })()
        
        if action == 'skip':
            await skip_command(fake_update, context)
        elif action == 'stop':
            await stop_command(fake_update, context)
        elif action == 'queue':
            await queue_command(fake_update, context)
        elif action == 'pause':
            await pause_command(fake_update, context)
            
    except Exception as e:
        logger.error(f"Error in music callback: {e}")


def _get_queue(chat_id: int) -> dict:
    """Get or create queue for a chat"""
    if chat_id not in music_queues:
        music_queues[chat_id] = {
            'queue': [],
            'current': None,
            'is_playing': False
        }
    return music_queues[chat_id]


async def _add_to_queue(chat_id: int, track: dict):
    """Add a track to the queue"""
    queue_data = _get_queue(chat_id)
    queue_data['queue'].append(track)


async def _play_next(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Play the next track in the queue"""
    queue_data = _get_queue(chat_id)
    
    if not queue_data['queue']:
        queue_data['current'] = None
        queue_data['is_playing'] = False
        return
    
    track = queue_data['queue'].pop(0)
    queue_data['current'] = track
    queue_data['is_playing'] = True
    
    try:
        if track['type'] == 'telegram':
            # Send audio/voice file
            file_id = track['file_id']
            
            # Check if it's a voice message or audio file
            # Note: We can't easily determine file type from file_id alone
            # so we'll try audio first, then voice
            
            try:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=file_id,
                    caption=f"🎵 <b>{track['title']}</b>",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                try:
                    await context.bot.send_voice(
                        chat_id=chat_id,
                        voice=file_id,
                        caption=f"🎵 {track['title']}"
                    )
                except Exception as e:
                    logger.error(f"Error sending audio/voice: {e}")
                    await _play_next(chat_id, context)
                    return
        
        elif track['type'] == 'url':
            # For URL playback, we just send the URL as text
            # In a production system, you'd use yt-dlp or similar to download and send
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎵 <b>Now Playing from URL:</b>\n{track['url']}\n\n"
                     f"<i>Note: Telegram bots cannot directly stream audio from URLs. "
                     f"Download the file and send it with /play</i>",
                parse_mode=ParseMode.HTML
            )
        
        # Auto-play next track after a delay
        if queue_data['queue'] and queue_data['is_playing']:
            await asyncio.sleep(5)  # Wait 5 seconds before next track
            await _play_next(chat_id, context)
    
    except Exception as e:
        logger.error(f"Error playing track: {e}")
        await _play_next(chat_id, context)
