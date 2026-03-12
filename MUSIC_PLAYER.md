# Music Player Feature

## Overview
The music player feature allows GroupGuard bot to play audio files and voice messages in Telegram groups with a queue management system.

## Bot Commands

### Core Commands
- `/play` - Play music (reply to audio/voice message or send an audio file)
- `/skip` - Skip to the next track in the queue
- `/queue` - View the current music queue
- `/stop` - Stop music and clear the queue
- `/pause` - Pause playback (simulated)
- `/resume` - Resume playback
- `/nowplaying` - Show the currently playing track with interactive controls

## Usage Examples

### 1. Play by Replying
```
User: [Sends an audio file]
Admin: /play [replies to the audio]
Bot: 🎵 Added to queue: [Song Title]
```

### 2. Play by Sending
```
User: /play [while uploading an audio file]
Bot: 🎵 Added to queue: [Song Title]
```

### 3. Play from URL
```
User: /play https://example.com/song.mp3
Bot: 🎵 Added to queue: https://example.com/song.mp3
```

### 4. View Queue
```
User: /queue
Bot: 🎵 Music Queue

   Now Playing:
   Song Title

   Up Next:
   1. Another Song
   2. Third Song
```

### 5. Skip Track
```
User: /skip
Bot: ⏭️ Skipped: Song Title
```

## Implementation Details

### File Structure
- `bot/handlers/music.py` - Main music player command handlers
- `api/routes/music.py` - REST API endpoints for music queue management
- `webapp/index.html` - Music player UI in the Mini App

### Features
1. **Queue Management** - Store and manage playback queue for each group
2. **Track Info** - Display track title, artist, and duration
3. **Interactive Controls** - Inline buttons for skip, pause, stop
4. **Multiple Audio Types** - Support for audio files and voice messages
5. **Auto-play** - Automatically plays next track after current one

### Data Storage
Currently uses in-memory storage (Python dict). For production:
- Use Redis for distributed queue management
- Store queue in database for persistence
- Add track metadata caching

### API Endpoints

#### GET `/api/music/{chat_id}/queue`
Get the current music queue for a group.

#### POST `/api/music/{chat_id}/command`
Send a music command to the group.

#### POST `/api/music/{chat_id}/add`
Add a track to the music queue.

#### POST `/api/music/{chat_id}/clear`
Clear the music queue for a group.

## Mini App Integration

The music player is integrated into the GroupGuard Mini App with:
- **Now Playing** display showing current track
- **Control buttons** for pause, skip, resume, stop
- **Queue view** showing upcoming tracks
- **How-to guide** for new users

### Music Tab Features
- Visual now-playing display
- Quick action buttons
- Real-time queue updates
- Instructional guide

## Limitations

1. **No Actual Audio Streaming**: Telegram bots cannot stream audio. The bot re-sends audio files already shared in the group.

2. **No True Pause/Resume**: Due to Telegram's limitations, pause/resume are simulated by queue management.

3. **In-Memory Storage**: Queue data is lost on bot restart. Implement database persistence for production.

4. **URL Playback**: URLs are not automatically downloaded and played. Users should download and send audio files directly.

## Future Enhancements

1. **Database Persistence** - Store queues in Supabase/PostgreSQL
2. **Redis Integration** - Use Redis for distributed queue management
3. **YouTube Support** - Add yt-dlp integration for YouTube playback
4. **Volume Control** - Add volume adjustment commands
5. **Shuffle/Repeat** - Add shuffle and repeat modes
6. **Playlists** - Allow saving and loading playlists
7. **Search** - Search for songs in the queue
8. **Multi-bot Coordination** - Sync music across clone bots

## Security Considerations

- Commands are group-only, not available in private chats
- Queue is isolated per group/chat
- URL playback is disabled by default (can be enabled with caution)
- File size limits follow Telegram's constraints

## Troubleshooting

### Bot doesn't play music
- Ensure bot is admin in the group
- Check that audio file was sent after bot joined
- Verify bot has permission to send messages

### Queue not persisting
- Current implementation uses in-memory storage
- Implement database persistence for production use

### Inline buttons not working
- Ensure callback query handler is registered
- Check callback query pattern matching

## Testing

Test the music player with:
1. Audio files (MP3, M4A, etc.)
2. Voice messages
3. Queue with multiple tracks
4. Skip functionality
5. Stop and clear queue
6. Mini App controls
