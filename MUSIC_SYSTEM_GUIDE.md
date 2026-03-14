# Nexus Bot Music System - Complete Guide for Beginners

## Table of Contents
1. [How It Works](#how-it-works)
2. [Architecture Overview](#architecture-overview)
3. [Setup Instructions](#setup-instructions)
4. [Main Bot vs Clone Bots](#main-bot-vs-clone-bots)
5. [Userbots Explained](#userbots-explained)
6. [Testing Your Setup](#testing-your-setup)
7. [Troubleshooting](#troubleshooting)

---

## How It Works

### The Big Picture

The Nexus Bot music system uses a **distributed architecture** where:

1. **Your main bot runs on Render** (cloud) - handles commands, database, web panel
2. **Music streaming runs on your local PC** (via WSL) - handles voice chat audio
3. **They communicate via Redis** (a message queue)

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Telegram      │◄───────►│   Render Bot    │◄───────►│     Redis       │
│   (Users)       │         │   (Commands)    │         │   (Message Queue)│
└─────────────────┘         └─────────────────┘         └────────┬────────┘
                                                                 │
                                                                 ▼
                                                        ┌─────────────────┐
                                                        │   Your PC/WSL   │
                                                        │ (Music Worker)  │
                                                        │  - Pyrogram     │
                                                        │  - PyTGCalls    │
                                                        │  - yt-dlp       │
                                                        └─────────────────┘
```

### Why This Design?

**Render (free tier) cannot run PyTGCalls** because it requires:
- Native binary (ntgcalls) that doesn't work on Render's platform
- ffmpeg for audio conversion
- Direct network access for Telegram voice chats

**Your local PC can run PyTGCalls** because:
- It has WSL/Ubuntu with full system access
- Can install ffmpeg and native binaries
- Has direct internet connection
- Can join Telegram voice chats as a user

---

## Architecture Overview

### Components

#### 1. Main Bot (Render)
- **File**: `main.py`
- **Purpose**: Handles Telegram commands, database operations, Mini App API
- **What it does**:
  - Receives `/play` command from users
  - Adds song to queue in database
  - Pushes job to Redis queue
  - Serves Mini App web interface
  - Manages userbot accounts

#### 2. Music Worker (Your PC)
- **File**: `music_worker_local.py`
- **Purpose**: Streams audio to Telegram voice chats
- **What it does**:
  - Listens for jobs from Redis
  - Downloads audio using yt-dlp
  - Joins voice chats via Pyrogram
  - Streams audio via PyTGCalls
  - Reports status back to Redis

#### 3. Redis (Message Queue)
- **Purpose**: Connects Render bot and local worker
- **Keys used**:
  - `music:jobs` - Queue of play/skip/stop commands
  - `music:status:{chat_id}:{bot_id}` - Current playback status
  - `music:worker:heartbeat` - Worker health check

#### 4. PostgreSQL (Database)
- **Purpose**: Stores all persistent data
- **Tables**:
  - `music_userbots` - Telegram user accounts for streaming
  - `music_queues` - Song queue per group
  - `music_sessions` - Playback state per group
  - `music_settings` - Group-specific settings

---

## Setup Instructions

### Step 1: Prerequisites

On your Windows PC with WSL:
```bash
# Update WSL
wsl --update

# Install ffmpeg (required for audio conversion)
sudo apt-get update
sudo apt-get install ffmpeg -y

# Verify ffmpeg
ffmpeg -version
```

### Step 2: Get Telegram API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Create a new application:
   - App title: `NexusMusic`
   - Short name: `nexusmusic`
   - Platform: `Desktop`
   - Description: `Music streaming for Nexus Bot`
4. Save the **api_id** and **api_hash**

### Step 3: Clone and Setup Repository

```bash
# In WSL (Ubuntu)
cd ~
git clone <your-repo-url>
cd project

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Configure Environment

Create `.env.music` file:
```bash
cp .env.music.example .env.music
nano .env.music
```

Fill in these values:
```env
# From my.telegram.org
PYROGRAM_API_ID=12345678
PYROGRAM_API_HASH=your_api_hash_here

# Same as your Render bot uses
SUPABASE_CONNECTION_STRING=postgresql://postgres:password@db.xxxxxxxx.supabase.co:5432/postgres
REDIS_URL=redis://your-redis-host:6379
BOT_TOKEN=your_bot_token_here

# Music settings
MUSIC_DOWNLOAD_DIR=/tmp/nexus_music
MUSIC_MAX_DURATION=3600
LAZY_UNLOAD_TIMEOUT=1800
PYROGRAM_MAX_ACTIVE=10

# Same SECRET_KEY as your main bot
SECRET_KEY=your_fernet_key_here
```

### Step 5: Add a Userbot

**What is a userbot?**
A userbot is a Telegram user account (not a bot) that can:
- Join voice chats
- Stream audio
- Act like a real user

**How to add one:**

1. **Via Mini App (Recommended):**
   - Open your bot's Mini App
   - Go to Music section
   - Click "Add Userbot"
   - Choose method:
     - **QR Code**: Scan with Telegram mobile app
     - **Phone**: Enter phone number, get code
     - **Session String**: Paste Pyrogram session string

2. **Via Python Script:**
   ```python
   # save as create_session.py
   from pyrogram import Client

   app = Client(
       "my_account",
       api_id=12345678,
       api_hash="your_api_hash"
   )

   with app:
       session_string = app.export_session_string()
       print(f"Session string: {session_string}")
   ```
   Run it, log in, then paste the session string in Mini App.

### Step 6: Start the Music Worker

```bash
# Make sure you're in the project directory with venv activated
cd ~/project
source .venv/bin/activate

# Start the worker
./start_music_worker.sh
```

You should see:
```
============================================================
  🎵 NEXUS MUSIC WORKER (Local PC)
============================================================
  Redis: redis://...
  Database: Connected via asyncpg
  Download Dir: /tmp/nexus_music
  Max Duration: 60 minutes
============================================================
[MUSIC_WORKER] ✅ Redis connected
[MUSIC_WORKER] ✅ Database connected
[MUSIC_WORKER] 📱 Loaded X userbots
[MUSIC_WORKER] 🚀 Starting job consumer and heartbeat...
```

### Step 7: Test It

1. Add your bot to a Telegram group
2. Give it admin rights (needed for voice chats)
3. Start a voice chat in the group
4. Type: `/play https://youtube.com/watch?v=...`
5. The bot should join and play music!

---

## Main Bot vs Clone Bots

### Main Bot (Owner Bot)

**Bot ID**: `0` in the database

**Characteristics**:
- The primary bot you created
- Shares userbot pool with all groups using the main bot
- Userbots have `owner_bot_id = 0`

**Use case**: Most users use this. All groups share the same music userbots.

### Clone Bots

**Bot ID**: The clone's unique bot_id

**Characteristics**:
- Separate Telegram bots created via the clone system
- Can have their own dedicated userbots
- Userbots have `owner_bot_id = clone_bot_id`

**Use case**: Users who want their own branded bot with dedicated music resources.

### How It Works in Practice

```
Main Bot (ID: 0)
├── Userbot A (owner_bot_id: 0)
├── Userbot B (owner_bot_id: 0)
└── Group 1 uses Userbot A
    Group 2 uses Userbot B (if auto_rotate on)

Clone Bot "MyMusicBot" (ID: 12345)
├── Userbot C (owner_bot_id: 12345)
└── Group 3 uses Userbot C
```

---

## Userbots Explained

### What Are They?

Userbots are **real Telegram user accounts** that:
- Can join voice chats (bots can't do this)
- Stream audio via PyTGCalls
- Are controlled programmatically

### Why Multiple Userbots?

**Load Balancing**: If one userbot is rate-limited or banned, others continue working.

**Rotation Modes**:
- **Manual**: Always use the assigned userbot
- **Round Robin**: Cycle through userbots in order
- **Least Used**: Pick the userbot with fewest plays
- **Random**: Random selection

### Security

- Session strings are **encrypted** with Fernet (SECRET_KEY)
- Stored encrypted in PostgreSQL
- Decrypted only when creating Pyrogram client
- Never logged or exposed

---

## Testing Your Setup

### Test 1: Check Worker Status
```bash
# In another terminal, check Redis
redis-cli GET music:worker:heartbeat
```
Should return a JSON with worker status.

### Test 2: API Status Check
```bash
curl https://your-bot-url.com/api/music/status
```
Should return:
```json
{
  "available": true,
  "worker": "local_pc",
  "reason": "Music worker is online and responding"
}
```

### Test 3: Database Columns
```sql
-- Check migration ran
SELECT column_name FROM information_schema.columns
WHERE table_name = 'music_settings';
-- Should show: userbot_id, volume, rotation_mode, auto_rotate
```

### Test 4: Play a Song
```
/play https://www.youtube.com/watch?v=dQw4w9WgXcQ
```
Check worker logs - you should see download and streaming messages.

---

## Troubleshooting

### Problem: "Music worker is offline"

**Solution**:
1. Check if worker is running: `ps aux | grep music_worker`
2. Check logs: `tail -f music_worker.log`
3. Verify Redis connection: `redis-cli ping`
4. Check environment variables in `.env.music`

### Problem: "No userbots available"

**Solution**:
1. Add a userbot via Mini App
2. Check database: `SELECT * FROM music_userbots WHERE is_active = true;`
3. Verify session string is valid (test with Pyrogram script)

### Problem: "Could not resolve track"

**Solution**:
1. Check ffmpeg is installed: `ffmpeg -version`
2. Check yt-dlp works: `yt-dlp --version`
3. Try different YouTube URL
4. Check disk space for downloads

### Problem: PyTGCalls errors

**Solution**:
1. Ensure you're running on WSL (not Windows Python)
2. Reinstall py-tgcalls: `pip install --force-reinstall py-tgcalls`
3. Check ntgcalls binary exists: `python -c "import ntgcalls; print(ntgcalls.__file__)"`

### Problem: "Session expired" during phone auth

**Solution**:
1. Complete auth within 10 minutes
2. Check your phone has good signal
3. Try QR code method instead

### Problem: Worker crashes on startup

**Solution**:
1. Check all env vars are set: `cat .env.music`
2. Verify database connection string
3. Check Redis URL is correct
4. Look at `music_worker.log` for specific errors

---

## Quick Reference Commands

```bash
# Start worker
./start_music_worker.sh

# Stop worker
Ctrl+C

# View logs
tail -f music_worker.log

# Check Redis
redis-cli KEYS "music:*"

# Restart with fresh venv
deactivate
source .venv/bin/activate
./start_music_worker.sh

# Update dependencies
pip install -r requirements.txt --upgrade
```

---

## FAQ

**Q: Can I run the worker on Windows directly?**
A: No, use WSL2. PyTGCalls requires Linux environment.

**Q: Does my PC need to stay on?**
A: Yes. When your PC is off, music features are unavailable but the bot still works for other commands.

**Q: Can I use one userbot for multiple groups?**
A: Yes! One userbot can stream in multiple voice chats simultaneously.

**Q: What happens if my internet disconnects?**
A: The worker will retry connections. When internet returns, it auto-reconnects.

**Q: Is this against Telegram's Terms of Service?**
A: Using userbots for music streaming is generally acceptable. Don't spam or abuse.

---

## Support

If you encounter issues:
1. Check logs in `music_worker.log`
2. Verify all environment variables
3. Test Redis and database connections
4. Check Telegram API credentials are valid
