# GroupGuard - Production-Ready Telegram Management Bot

A powerful group management bot with an integrated Telegram Mini App for easy configuration.

## 🚀 Features
- **Moderation**: Warn, Ban, Mute, Kick, Purge.
- **AutoMod**: Anti-flood, Anti-spam, Anti-link, Captcha, Anti-bot.
- **Mini App**: Manage all group settings via a beautiful dashboard.
- **Bot Cloning**: Run multiple bot instances from a single server.
- **Production-Ready**: Webhook-based, deployed on Render, powered by Supabase.

## 🛠️ Setup Guide

### 1. Database Setup (Supabase)

1. Create a project at [supabase.com](https://supabase.com).
2. Go to Project Settings → Database.
3. Copy the **Connection String** (Transaction mode recommended for Render).
4. Go to Project Settings → API.
5. Copy **Project URL** and **service_role API Key**.

### 2. Bot Setup (BotFather)

1. Create a bot with [@BotFather](https://t.me/BotFather).
2. Save the API Token.
3. Use `/setmenubutton` to point to `https://YOUR_URL.onrender.com/webapp`.
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

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PRIMARY_BOT_TOKEN` | Main bot token from BotFather | Yes |
| `SECRET_KEY` | Fernet key for token encryption | Yes |
| `SUPABASE_URL` | Your Supabase project URL | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Yes |
| `SUPABASE_CONNECTION_STRING` | PostgreSQL connection string | Yes |
| `OWNER_ID` | Your Telegram user ID | Yes |
| `CLONE_ACCESS` | `owner_only` or `anyone` | No (default: owner_only) |
| `SKIP_AUTH` | Skip auth for local dev | No |
| `DEBUG` | Enable debug routes | No |

## 🔐 Troubleshooting

### Clone Errors

1. **RATE_LIMITED**: Wait an hour before trying again.
2. **INVALID_FORMAT**: Token must be in format `1234567890:ABCdef...`.
3. **ALREADY_REGISTERED**: This token is already used by another clone.
4. **TELEGRAM_REJECTED**: The token was revoked or is invalid.
5. **WEBHOOK_FAILED**: Could not register webhook - check your `RENDER_EXTERNAL_URL`.
6. **NETWORK_ERROR**: Could not reach Telegram API.

### Network Issues

If you see "Network is unreachable" in logs:
- Check your Supabase database is active
- Verify connection string format
- Consider using Supabase Connection Pooler for free plans

### Token Decryption Failed

This happens if `SECRET_KEY` was rotated. Generate a new key and update your environment. **Note**: Tokens encrypted with the old key cannot be recovered.

## 📊 Debug Routes

When `DEBUG=true`:

- `GET /debug/health` - Full system status
- `GET /debug/webhook-info?bot_id=123` - Webhook info from Telegram
- `GET /debug/send-test?bot_id=123&chat_id=456` - Send test message
- `GET /debug/registry` - List all registered bots
- `GET /debug/db-ping` - Database latency check
