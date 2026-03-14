# Nexus Music Streaming System

## Overview

This implementation adds a complete music streaming system to Nexus bot using PyTGCalls for voice chat streaming. The system supports:

- **YouTube, SoundCloud, Spotify, and direct URL playback** via yt-dlp
- **Voice message playback** with OGG → MP3 conversion
- **Queue management** with position tracking
- **Volume control** (0-200)
- **Loop mode** for repeating tracks
- **Multi-bot support** with separate userbot per clone bot
- **Admin-only mode** via `/musicmode` command
- **Mini App integration** for userbot account management

## Architecture

```
MAIN BOT
  └── Userbot pool (N accounts, set by MUSIC_WORKER_COUNT)
  └── Music works immediately if configured
  └── One MusicWorker instance manages all group voice chats

CLONE BOT
  └── Owner adds their own userbot via /adduserbot or Mini App
  └── One userbot per clone bot (not per group)
  └── Without userbot → /play returns setup instructions
  └── Userbot joins VC on demand, auto-leaves after 3 min idle

SHARED COMPONENTS
  ├── MusicWorker — Core streaming engine (PyTGCalls + yt-dlp)
  ├── Queue system — Per-group track queue with position tracking
  ├── Session state — Playback state synced to database
  └── MusicAuth — Userbot authentication (phone+OTP, QR, session string)
```

## Key Files

### Core Music System
- `bot/userbot/music_worker.py` — MusicWorker class for streaming
- `bot/userbot/music_voice.py` — Voice message download and conversion
- `bot/userbot/music_auth.py` — Userbot authentication flows
- `bot/handlers/music_new.py` — Music commands (/play, /skip, /queue, etc.)
- `bot/handlers/adduserbot.py` — /adduserbot command for clone owners

### Database
- `db/migrations/add_music.sql` — Database schema for music tables
- `db/ops/music_new.py` — Database operations for userbots, queues, sessions

### API Routes (Mini App)
- `api/routes/music_auth.py` — Authentication endpoints for Mini App

### Factory Integration
- `bot/factory.py` — Registers music handlers, creates MusicWorker instances
- `main.py` — Initializes music workers on startup

## Commands

### For All Users
- `/play <url>` — Add track to queue (or reply to voice message)
- `/playnow <url>` — Skip queue and play immediately
- `/queue` — Show current queue
- `/nowplaying` — Show now-playing card with controls
- `/volume <0-200>` — Set volume

### For Clone Owners
- `/adduserbot` — Add a userbot account for music (private chat only)

### For Admins
- `/musicmode all|admins` — Restrict who can use music commands
- `/pause`, `/resume`, `/skip`, `/stop` — Playback controls
- `/loop` — Toggle loop mode

## Setup Instructions

### 1. Get Pyrogram API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Create a new app to get:
   - `api_id` (a number, e.g., 12345678)
   - `api_hash` (a string, e.g., "a1b2c3d4...")

### 2. Set Environment Variables

Add these to your `.env` file or Render dashboard:

```bash
# Pyrogram API credentials (required for music)
PYROGRAM_API_ID=12345678
PYROGRAM_API_HASH=your_api_hash_here

# Music configuration
MUSIC_WORKER_COUNT=1
MUSIC_MAX_QUEUE=50
MUSIC_MAX_DURATION=3600
MUSIC_IDLE_TIMEOUT=180
MUSIC_DEFAULT_VOLUME=100
MUSIC_DOWNLOAD_DIR=/tmp/nexus_music
```

### 3. Add a Userbot Account

**Option 1: Using /adduserbot command**

1. DM the primary bot in private chat
2. Send `/adduserbot`
3. Choose authentication method:
   - 📱 Phone + OTP — Enter phone number, then OTP code from Telegram
   - 📷 QR Code — Scan with Telegram app (Settings → Devices → Scan QR)
   - 🔑 Session String — Paste existing Pyrogram session string

**Option 2: Using Session String (Advanced)**

Generate a session string from Python:

```python
from pyrogram import Client

client = Client("my_account")
client.run(lambda c: print(c.export_session_string()))
```

Then paste the session string when prompted.

### 4. Start Playing Music

In any group:
- Send `/play https://youtube.com/watch?v=...` to add a track
- Or reply to a voice message with `/play`
- Use `/queue` to see the queue
- Use `/skip` to skip to the next track

## Mini App Integration

The Mini App includes a Music tab in Settings where clone owners can:

- View current music userbot status
- Add/remove userbot accounts
- Configure per-group music settings

API Endpoints:
- `POST /api/bots/{bot_id}/music/auth/start-phone` — Start phone auth
- `POST /api/bots/{bot_id}/music/auth/verify-otp` — Verify OTP code
- `POST /api/bots/{bot_id}/music/auth/start-qr` — Generate QR code
- `POST /api/bots/{bot_id}/music/auth/session-string` — Authenticate with session string
- `GET /api/bots/{bot_id}/music/userbot` — Get userbot info
- `DELETE /api/bots/{bot_id}/music/userbot` — Remove userbot
- `GET /api/groups/{chat_id}/music/settings` — Get group music settings
- `PUT /api/groups/{chat_id}/music/settings` — Update group music settings

## Database Schema

### music_userbots
Stores userbot accounts for music streaming.

- `id` — Primary key
- `owner_bot_id` — 0 for main bot, clone bot_id for clones
- `phone` — Phone number (optional)
- `session_string` — Encrypted Pyrogram session string
- `tg_user_id` — Telegram user ID
- `tg_username` — Telegram username
- `tg_name` — Full name
- `is_active` — Whether account is active
- `added_at`, `last_used_at` — Timestamps

### music_queues
Per-group queue of tracks.

- `id` — Primary key
- `chat_id` — Telegram group chat ID
- `bot_id` — Bot instance ID
- `position` — Position in queue
- `url` — Track URL
- `title`, `duration`, `thumbnail` — Track metadata
- `source` — youtube|soundcloud|spotify|direct|voice
- `requested_by`, `requested_by_name` — Who added the track
- `added_at` — When added
- `played` — Whether track has been played

### music_sessions
Per-group playback session state.

- `chat_id`, `bot_id` — Composite primary key
- `is_playing`, `is_paused`, `is_looping` — Playback flags
- `volume` — Current volume (0-200)
- `current_track` — FK to music_queues
- `np_message_id` — Now-playing message ID
- `started_at`, `updated_at` — Timestamps

### music_settings
Per-group music settings.

- `chat_id`, `bot_id` — Composite primary key
- `play_mode` — all|admins
- `dj_role_id` — Optional specific role for /play
- `announce_tracks` — Whether to post NP cards

## Troubleshooting

### Music not working
1. Check that PYROGRAM_API_ID and PYROGRAM_API_HASH are set
2. Verify userbot account is added (check database music_userbots table)
3. Check logs for `[MUSIC]` prefixed messages
4. Ensure ffmpeg is installed (included in render.yaml buildCommand)

### "Music worker not available" error
- Clone bot has no userbot configured
- Use `/adduserbot` in private chat with the primary bot
- Or configure via Mini App Settings → Music

### QR code not scanning
- Ensure you're scanning with Telegram (Settings → Devices → Scan QR)
- QR expires after 30 seconds
- Use phone+OTP method if QR fails

### Audio cuts out early
- Check MUSIC_MAX_DURATION setting
- Some sources may block streaming
- Try a different URL or source

## Dependencies

All added to `requirements.txt`:
- `pytgcalls==3.0.0.dev29` — Voice chat streaming
- `yt-dlp==2024.12.6` — Audio downloading
- `ffmpeg-python==0.2.0` — Audio conversion
- `qrcode==7.4.2` — QR code generation
- `pillow==10.3.0` — Image processing for QR
- `pyrogram>=2.0.106` — Userbot client
- `tgcrypto>=1.2.5` — Encryption for PyTGCalls

System dependency (added to render.yaml):
- `ffmpeg` — Audio processing

## Security Notes

- Session strings are encrypted with Fernet before storing in database
- Uses existing SECRET_KEY from config.py for encryption
- Userbot accounts are real Telegram accounts — keep them secure
- Never share session strings or phone numbers
- Music worker validates accounts are not bot accounts

## Performance Considerations

- Temp audio files are deleted immediately after streaming begins
- Idle timeout prevents userbot from staying in VC unnecessarily
- Music worker can stream to multiple groups simultaneously
- Queue is kept in memory for fast access
- State is synced to database for recovery after restarts

## Future Enhancements

Possible improvements:
- Playlist support with save/load
- Search within queue and playlists
- Shuffle mode
- Multiple userbot pooling for main bot
- History tracking
- Cross-bot queue sync
- Advanced equalizer settings
