# Nexus - Production-Ready Telegram Management Bot

A powerful group management bot with an integrated Telegram Mini App for easy configuration.

## 🚀 Features
- **Moderation**: Warn, Ban, Mute, Kick, Purge.
- **AutoMod**: Anti-flood, Anti-spam, Anti-link, Captcha, Anti-bot.
- **Music Player**: Play audio files and voice messages in groups with queue management.
- **Mini App**: Manage all group settings via a beautiful dashboard.
- **Bot Cloning**: Run multiple bot instances from a single server.
- **Production-Ready**: Webhook-based, deployed on Render, powered by Supabase.
- **Triple Prefix System**: Use `!`, `!!`, and `/` for different types of actions.
- **Channel Management**: Link your group to a channel and post/schedule messages directly from Nexus.
- **Trust Score**: Automated behavioral analysis to grant or restrict user permissions.
- **Privacy**: Comprehensive GDPR-compliant privacy policy with `/privacy` command.

## 🛠️ Setup Guide

### 1. Database Setup (Supabase)

1. Create a project at [supabase.com](https://supabase.com).
2. Go to Project Settings → Database.
3. Copy **Connection String** (Transaction mode recommended for Render).
4. Go to Project Settings → API.
5. Copy **Project URL** and **service_role API Key**.

### 2. Bot Setup (BotFather)

1. Create a bot with [@BotFather](https://t.me/BotFather).
2. Save the API Token.
3. Use `/setmenubutton` to point to `https://YOUR_URL.onrender.com/miniapp`.
4. (Optional) Create more bots for cloning via Mini App.

### 3. Deploy to Render

1. Connect your GitHub repository.
2. Render will automatically detect `render.yaml`.
3. Set the required Environment Variables:
   - `PRIMARY_BOT_TOKEN`: Main bot token.
   - `SUPABASE_URL`: Your Supabase URL.
   - `SUPABASE_SERVICE_KEY`: Your Supabase Service Key.
   - `SUPABASE_CONNECTION_STRING`: Your Postgres Connection String.
   - `SECRET_KEY`: Fernet encryption key.
   - `RENDER_EXTERNAL_URL`: Your Render app URL (e.g., `https://myapp.onrender.com`).
   - `OWNER_ID`: Your Telegram user ID.

### 4. Generate SECRET_KEY

Generate a Fernet key for token encryption:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 5. Local Testing

1. Install dependencies: `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and fill the values.
3. Set `SKIP_AUTH=true` for easier Mini App testing.
4. Run: `python main.py`.
5. Use ngrok to test webhooks locally: `ngrok http 8000`.

## 🤖 Bot Cloning System

The cloning system allows you to run multiple bot instances from a single server. Here's how it works:

### Architecture

- **Primary Bot**: The main bot registered with `PRIMARY_BOT_TOKEN`. This is the only bot that can clone other bots.
- **Clone Bots**: Additional bot instances created through `/clone` command or Mini App.
- **Webhook Routing**: Each bot has its own webhook endpoint (`/webhook/{bot_id}`).
- **Token Encryption**: All bot tokens are encrypted with Fernet before storage.

### Commands (Primary Bot Only)

- `/clone` - Start the cloning process in private chat
- `/myclones` - View and manage your cloned bots

### Security Features

1. **Rate Limiting**: Max 5 clone attempts per hour per user
2. **Token Validation**: Format check before API call
3. **Deduplication**: Prevents same token from being registered twice
4. **Telegram Validation**: Live `getMe` call to verify token
5. **Confirmation Step**: User must explicitly confirm registration

### Mini App Bot Manager

Access the Bot Manager tab in the Mini App to:
- View all your bots (primary + clones)
- See bot status (active/dead)
- Check webhook status
- Clone new bots
- Remove clones
- Re-authenticate dead bots

### Music Player

Nexus includes a powerful music player for groups with advanced features! Use these commands:

**Basic Commands:**
- `/play` - Play music (reply to an audio/voice message or send an audio file)
- `/skip` - Skip the current track
- `/queue` - View the music queue
- `/stop` - Stop playing and clear the queue
- `/pause` - Pause playback
- `/resume` - Resume playback
- `/nowplaying` - Show current track with controls

**Advanced Commands:**
- `/play_youtube <url>` - Play audio from a YouTube video
- `/volume <0-200>` - Set the playback volume
- `/repeat <none|one|all>` - Set the repeat mode
- `/shuffle` - Toggle shuffle mode
- `/playlist_create <name>` - Create a custom playlist
- `/playlist_list` - List your playlists
- `/playlist_play <name>` - Play a custom playlist
- `/playlist_delete <name>` - Delete a playlist
- `/history` - Show play history
- `/search <query>` - Search for music online
- `/sync` - Sync music to all clone bots
- `/music_settings` - Open the music settings panel

## 📢 Channel Management

Nexus can manage your Telegram channels!

1. Add @NexusBot (or your clone) as admin to your channel.
2. Grant permissions: Post Messages, Edit Messages, Delete Messages.
3. In Mini App → Channel tab → Link Channel → paste channel username or ID.
4. Nexus will confirm the link.

**Channel Commands:**
- `/channelpost <text>` - Post text or media (if replied) to the linked channel.
- `/schedulepost <YYYY-MM-DD HH:MM> <text>` - Schedule a post for later.
- `/approvepost` - (Reply to a message) Copies the message to the channel.
- `/cancelpost <post_id>` - Cancel a scheduled post.
- `/editpost <post_id> <new_text>` - Edit a sent or scheduled post.
- `/deletepost <post_id>` - Delete a sent post from the channel.

## 🛡️ Trust Score System

Nexus automatically calculates a Trust Score (0-100) for every member based on:
- **Activity**: Messages sent, days active.
- **History**: Warnings, bans, mutes.
- **Engagement**: Reactions, poll participation.

Low-trust users face extra scrutiny, while high-trust users may be exempt from certain restrictions like anti-flood.

## 🔒 Privacy

Nexus is committed to protecting your privacy. We comply with GDPR regulations and provide transparent information about data collection.

**View Privacy Policy:**
- Bot command: `/privacy` (displays the full policy inline)
- Web version: `https://YOUR_URL.onrender.com/privacy`
- GitHub: `PRIVACY_POLICY.md` in the repository

**Key Privacy Features:**
- EU-based data storage (Supabase, Render)
- Fernet encryption for sensitive data (bot tokens, auth tokens)
- Minimal data collection - only what's necessary for group management
- GDPR-compliant with full user rights (access, correction, deletion, portability)
- Group admins can only see data for their own groups
- No selling or sharing of personal data with third parties

For complete details, see `PRIVACY_POLICY.md` or use `/privacy` in any bot.
