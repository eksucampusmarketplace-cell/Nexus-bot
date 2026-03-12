# Advanced Music Player Features

## Overview
The music player has been significantly enhanced with advanced features including YouTube support, database persistence, playlists, multi-bot sync, and more.

## New Features Added

### 1. Database Persistence (Supabase/PostgreSQL)
All music queues, playlists, and settings are now stored in the database:
- **Queue persistence** - Queues survive bot restarts
- **Playlists** - Save and manage playlists
- **Play history** - Track what was played
- **Settings storage** - Volume, repeat, shuffle modes saved

### 2. YouTube Support
Play music directly from YouTube URLs:
```
/play_youtube https://youtube.com/watch?v=...
```
Features:
- Automatic audio extraction (MP3, high quality)
- Metadata preservation (title, artist, duration)
- Automatic cleanup of temporary files

### 3. Volume Controls
Adjust playback volume (0-200%, 100% is default):
```
/volume 75
```
- Slider control in Mini App
- Real-time adjustment
- Persistent per-group settings

### 4. Repeat Modes
Three repeat modes available:
```
/repeat none  # Don't repeat (default)
/repeat one   # Repeat current track
/repeat all   # Repeat entire queue
```

### 5. Shuffle Mode
Randomize track order:
```
/shuffle  # Toggle on/off
```
- Fisher-Yates shuffle algorithm
- Visual indicator in UI
- Per-group setting

### 6. Playlist Management
Create and manage playlists:
```
/playlist_create My Favorites      # Create playlist
/playlist_list                   # List all playlists
/playlist_play My Favorites        # Play a playlist
/playlist_delete My Favorites      # Delete playlist
```

Features:
- Save current queue as playlist
- Load playlists to queue
- Track count per playlist
- Creator tracking

### 7. Search Functionality
Search across queue and playlists:
```
/search song name
```
- Searches current queue
- Searches all playlists
- Shows track location
- Case-insensitive search

### 8. Play History
View recently played tracks:
```
/history       # Last 10 tracks
/history 20   # Last 20 tracks
```

### 9. Multi-Bot Sync
Synchronize music queue across all clone bots:
```
/sync
```
Features:
- Sync queue to all registered bots
- Consistent playback across groups
- Owner-only command
- Visual confirmation

### 10. Interactive Settings Panel
```
/music_settings
```
Inline keyboard controls for:
- Volume adjustment (+/- 10%)
- Repeat mode selection
- Shuffle toggle

## Database Schema

### music_queues Table
```sql
- id (SERIAL PRIMARY KEY)
- chat_id (BIGINT UNIQUE)
- queue (JSONB) - List of tracks
- current_track (JSONB) - Currently playing
- is_playing (BOOLEAN)
- volume (INTEGER) - 0-200
- repeat_mode (VARCHAR) - 'none', 'one', 'all'
- shuffle_mode (BOOLEAN)
- updated_at (TIMESTAMP)
- created_at (TIMESTAMP)
```

### music_playlists Table
```sql
- id (SERIAL PRIMARY KEY)
- chat_id (BIGINT)
- playlist_name (VARCHAR)
- tracks (JSONB)
- created_by (BIGINT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
UNIQUE(chat_id, playlist_name)
```

### music_history Table
```sql
- id (SERIAL PRIMARY KEY)
- chat_id (BIGINT)
- track_data (JSONB)
- played_at (TIMESTAMP)
- played_by (BIGINT)
INDEX(chat_id, played_at DESC)
```

## API Endpoints

### Queue Operations
- `GET /api/music/{chat_id}/queue` - Get queue and settings
- `POST /api/music/{chat_id}/command` - Send command
- `PUT /api/music/{chat_id}/settings` - Update settings

### Playlist Operations
- `GET /api/music/{chat_id}/playlists` - List playlists
- `POST /api/music/{chat_id}/playlists` - Create playlist
- `DELETE /api/music/{chat_id}/playlists/{name}` - Delete playlist
- `POST /api/music/{chat_id}/playlists/{name}/play` - Play playlist

### YouTube Operations
- `POST /api/music/{chat_id}/youtube` - Play from URL

### Search & History
- `GET /api/music/{chat_id}/search` - Search music
- `GET /api/music/{chat_id}/history` - Get history

### Multi-Bot Sync
- `POST /api/music/{chat_id}/sync` - Sync to all bots

## Usage Examples

### Playing from YouTube
```
User: /play_youtube https://youtube.com/watch?v=dQw4w9WgXcQ
Bot: 🎬 Downloading from YouTube...
Bot: ✅ Added to queue: Rick Astley - Never Gonna Give You Up
[Bot plays the track]
```

### Creating a Playlist
```
User: /playlist_create Party Mix
Bot: ✅ Playlist 'Party Mix' created with 15 tracks!
```

### Playing a Playlist
```
User: /playlist_play Party Mix
Bot: ✅ Added 15 tracks from 'Party Mix' to queue!
[Bot starts playing]
```

### Using Search
```
User: /search Rick
Bot: 🔍 Search Results: 'Rick'

• Rick Astley - Never Gonna Give You Up
  📂 Queue
  👤 Rick Astley

• Rick Astley - Together Forever
  📂 Playlist: 80s Hits
  👤 Rick Astley
```

### Multi-Bot Sync
```
User: /sync
Bot: 🔄 Syncing music to all bots...
Bot: ✅ Synced to 5/5 bots
```

## Mini App Features

### Now Playing Display
- Large music icon
- Track title (bold)
- Artist name
- Duration
- Visual progress indicator

### Control Buttons
- ⏸️ Pause
- ⏭️ Skip
- ▶️ Resume
- ⏹️ Stop

### Volume Slider
- Range slider (0-200)
- Real-time percentage display
- Immediate API update

### Playback Modes
- 🔀 Shuffle toggle button
- 🔁 Repeat cycle button (none → one → all)

### Queue Management
- Track list with indices
- Click to remove tracks
- Clear all button
- Track count

### Playlists Section
- List all playlists
- Track count per playlist
- Play button per playlist
- Delete button per playlist
- Create new button

### History Section
- Last N tracks played
- Timestamp for each
- Track details

### Search Section
- Search input field
- Results display
- Source identification
- Click to play

### Multi-Bot Sync
- Sync button
- Confirmation dialog
- Status feedback

## Performance Optimizations

1. **Database Indexes**
   - chat_id indexes for fast lookups
   - played_at DESC for history queries

2. **Batch Operations**
   - Multiple track additions
   - Settings updates in single query

3. **Temporary File Cleanup**
   - Automatic cleanup of YouTube downloads
   - Temp directory management

4. **Caching**
   - Queue data cached in memory
   - Database for persistence only

## Security Considerations

1. **Owner-Only Commands**
   - `/sync` restricted to bot owner
   - Verified against OWNER_ID

2. **Per-Group Isolation**
   - Each chat has independent queue
   - No cross-group access

3. **Input Validation**
   - Volume clamped to 0-200
   - Repeat mode validated
   - YouTube URL validation

4. **Rate Limiting**
   - Consider implementing for YouTube downloads
   - Prevent abuse of API endpoints

## Troubleshooting

### YouTube Download Fails
- Check URL format (youtube.com or youtu.be)
- Verify FFmpeg is installed (required for audio extraction)
- Check internet connectivity
- Review logs for specific error

### Queue Not Persisting
- Verify database connection
- Check table creation succeeded
- Review migration status

### Sync Fails
- Ensure bot is owner
- Check all clone bots are active
- Verify webhook status on all bots
- Review network logs

### Playlists Not Saving
- Check database permissions
- Verify table exists
- Review JSON serialization

## Future Enhancements

1. **Spotify Integration**
   - Spotify API for music streaming
   - Playlist import from Spotify

2. **SoundCloud Support**
   - SoundCloud URL playback
   - Track metadata extraction

3. **Volume Per Track**
   - Different volumes per track
   - Normalization options

4. **Crossfade**
   - Smooth track transitions
   - Configurable fade duration

5. **Lyrics Display**
   - Fetch lyrics from APIs
   - Display with track info

6. **Collaborative Playlists**
   - Multiple users contribute
   - Voting system

7. **Music Discovery**
   - Recommendations based on history
   - Similar tracks feature

## Migration Notes

When upgrading from in-memory to database version:

1. Existing in-memory queues will be lost on restart
2. Database tables auto-created on first startup
3. No manual migration needed
4. Back up current queues if needed

## Monitoring

Key metrics to monitor:
- YouTube download success rate
- Database query performance
- API response times
- Queue sizes (potential memory issues)
- Sync operation failures

## Dependencies

New dependencies added:
- `yt-dlp>=2023.11.0` - YouTube audio extraction

Required system packages:
- FFmpeg - Audio conversion and extraction

Install FFmpeg:
```bash
# Ubuntu/Debian
apt-get install ffmpeg

# CentOS/RHEL
yum install ffmpeg

# macOS
brew install ffmpeg
```
