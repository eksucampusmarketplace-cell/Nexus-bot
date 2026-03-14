# Nexus Music System - Setup Guide for PC/Ubuntu

This guide walks you through setting up the Nexus music system on your local PC or Ubuntu server. The music system uses **Pyrogram** (a userbot library) to play music in Telegram voice chats.

## Prerequisites

Before starting, make sure you have:

- **Telegram Account** - You'll need a real Telegram account (not a bot) to use as the music userbot
- **Python 3.11+** - Check with `python3 --version`
- **Git** - To clone the repository
- **FFmpeg** - For audio processing (critical!)

---

## Step 1: Install System Dependencies

### On Ubuntu/Debian:

```bash
# Update package lists
sudo apt update

# Install required system packages
sudo apt install -y python3 python3-pip git ffmpeg

# Verify ffmpeg is installed
ffmpeg -version
```

### On macOS:

```bash
# Using Homebrew
brew install python@3.11 git ffmpeg

# Verify ffmpeg
ffmpeg -version
```

### On Windows:

1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Install FFmpeg:
   - Download from https://ffmpeg.org/download.html
   - Extract and add to PATH, OR
   - Use `choco install ffmpeg` if you have Chocolatey

---

## Step 2: Clone and Setup the Project

```bash
# Clone the repository
git clone https://github.com/your-repo/nexus.git
cd nexus

# Create virtual environment (recommended)
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

---

## Step 3: Get Telegram API Credentials

You need your own Pyrogram API credentials to create a userbot:

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Click **"Create application"**
4. Fill in the details:
   - App title: `Nexus Music` (or whatever you want)
   - Platform: `Desktop`
   - Device: `PC`
5. Copy the **API ID** and **API Hash**

---

## Step 4: Configure Environment Variables

### Option A: Using the Main .env File (Recommended)

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` and add these music-specific variables:

```bash
# === Required for Music ===
PYROGRAM_API_ID=12345678        # Your API ID from my.telegram.org
PYROGRAM_API_HASH=your_api_hash_here  # Your API Hash

# Music settings (optional, these have good defaults)
MUSIC_WORKER_COUNT=1
MUSIC_MAX_QUEUE=50
MUSIC_MAX_DURATION=3600
MUSIC_IDLE_TIMEOUT=180
MUSIC_DEFAULT_VOLUME=100
MUSIC_DOWNLOAD_DIR=/tmp/nexus_music

# Memory management (adjust if you have limited RAM)
PYROGRAM_MAX_ACTIVE=10
LAZY_UNLOAD_TIMEOUT=1800
```

### Option B: Using Separate .env.music File

If you prefer separate configuration, create `.env.music`:

```bash
cp .env.music.example .env.music
```

Edit `.env.music` with your values:

```bash
# Music Worker Local Configuration
PYROGRAM_API_ID=12345678
PYROGRAM_API_HASH=your_api_hash_here

# Bot token for sending now-playing messages
BOT_TOKEN=your_bot_token_here

# Music settings
MUSIC_DOWNLOAD_DIR=/tmp/nexus_music
MUSIC_MAX_DURATION=3600

# Secret key (must match your main bot's SECRET_KEY)
SECRET_KEY=your_fernet_key_here
```

> **Note:** The `.env.music` file is optional. Most users should just add variables to the main `.env` file.

---

## Step 5: Generate a SECRET_KEY (If Not Already Done)

If you haven't generated a Fernet key yet:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output and add to your `.env`:

```bash
SECRET_KEY=your_generated_key_here
```

---

## Step 6: Run the Bot

### Option A: Run Everything Together

```bash
# Make sure your .env is configured
python3 main.py
```

### Option B: Run Music Worker Separately (Advanced)

For a dedicated music worker:

```bash
python3 music_worker_local.py
```

---

## Step 7: Add a Userbot Account

Once the bot is running, you need to add a Telegram account for music:

### Method 1: Using /adduserbot Command

1. Open the bot in Telegram
2. Send `/adduserbot` in a private chat with the bot
3. Follow the prompts to authenticate

### Method 2: Using Session String (Manual)

If you already have a Pyrogram session, you can paste it directly:

```python
# Generate session string (run locally)
from pyrogram import Client

client = Client("my_session")
client.run()
# After logging in:
print(client.export_session_string())
```

Then send the session string when prompted by `/adduserbot`.

---

## Common Issues and Solutions

### ❌ "ffmpeg not found" Error

**Problem:** Bot can't find FFmpeg

**Solution:**
```bash
# Check if ffmpeg is installed
which ffmpeg

# On Ubuntu, reinstall:
sudo apt install ffmpeg

# Make sure it's in your PATH
export PATH=$PATH:/usr/bin/ffmpeg
```

### ❌ "pytgcalls not installed" Warning

**Problem:** PyTGCalls native binary not available

**Solution:**
```bash
# Install py-tgcalls
pip install py-tgcalls

# On some systems, you may need:
pip install py-tgcalls --no-binary :all:
```

### ❌ Music Not Playing in Groups

**Checklist:**
1. Is the bot added to the group?
2. Does the bot have permission to join voice chats?
3. Did you add a userbot account with `/adduserbot`?
4. Check logs for `[MUSIC]` prefixed messages

### ❌ "Session string invalid" Error

**Solution:**
- Make sure you're using a **user account** session string, not a bot token
- The session might have expired - generate a new one

### ❌ Bot Crashes on Music Commands

**Check:**
1. Is FFmpeg installed and in PATH?
2. Do you have enough RAM? (Minimum 2GB recommended)
3. Check the logs for specific error messages

---

## Testing Music Commands

Once set up, try these commands in a group where the bot is present:

```
/play https://youtube.com/watch?v=dQw4w9WgXcQ
/queue
/volume 80
/nowplaying
/skip
/stop
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Your Server/PC                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│   ┌─────────────┐     ┌────────────────────────┐  │
│   │  Main Bot   │────▶│   Music Worker         │  │
│   │  (PTB)      │     │   (Pyrogram +          │  │
│   │             │     │    PyTGCalls)          │  │
│   └─────────────┘     └────────────────────────┘  │
│         │                      │                   │
│         │              ┌───────▼───────┐          │
│         │              │  Userbot      │          │
│         │              │  (Your        │          │
│         │              │  Telegram     │          │
│         │              │  Account)     │          │
│         │              └───────────────┘          │
│         │                                        │
│   ┌─────▼────────┐                               │
│   │  Database    │  (PostgreSQL/Supabase)        │
│   └──────────────┘                               │
│                                                     │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Telegram Voice Chat  │
              │   (Music streams      │
              │    to group VC)       │
              └───────────────────────┘
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PYROGRAM_API_ID` | Yes | - | Get from my.telegram.org |
| `PYROGRAM_API_HASH` | Yes | - | Get from my.telegram.org |
| `MUSIC_WORKER_COUNT` | No | 1 | Number of music workers |
| `MUSIC_MAX_QUEUE` | No | 50 | Max tracks in queue |
| `MUSIC_MAX_DURATION` | No | 3600 | Max track duration (seconds) |
| `MUSIC_IDLE_TIMEOUT` | No | 180 | Seconds before leaving VC when idle |
| `MUSIC_DEFAULT_VOLUME` | No | 100 | Default volume (0-200) |
| `MUSIC_DOWNLOAD_DIR` | No | /tmp/nexus_music | Temp audio storage |
| `PYROGRAM_MAX_ACTIVE` | No | 10 | Max simultaneous userbots |
| `LAZY_UNLOAD_TIMEOUT` | No | 1800 | Seconds before unloading idle userbot |
| `SECRET_KEY` | Yes | - | Fernet key for encrypting session strings |

---

## Need Help?

- Check the main [README.md](../README.md) for general bot setup
- Check [MUSIC_SYSTEM_README.md](./MUSIC_SYSTEM_README.md) for advanced features
- Review logs with `[MUSIC]` prefix for debugging
- Make sure FFmpeg is properly installed: `ffmpeg -version`
