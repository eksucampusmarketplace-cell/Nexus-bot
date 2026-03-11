# GroupGuard - Production-Ready Telegram Management Bot

A powerful group management bot with a integrated Telegram Mini App for easy configuration.

## 🚀 Features
- **Moderation**: Warn, Ban, Mute, Kick, Purge.
- **AutoMod**: Anti-flood, Anti-spam, Anti-link, Captcha, Anti-bot.
- **Mini App**: Manage all group settings via a beautiful dashboard.
- **Bot Cloning**: Supports running multiple bot tokens simultaneously.
- **Production-Ready**: Webhook-based, deployed on Render, powered by Supabase.

## 🛠️ Setup Guide

### 1. Database Setup (Supabase)
1. Create a project at [supabase.com](https://supabase.com).
2. Go to Project Settings -> Database.
3. Copy the **Connection String** (Transaction mode recommended for Render).
4. Go to Project Settings -> API.
5. Copy **Project URL** and **service_role API Key**.

### 2. Bot Setup (BotFather)
1. Create a bot with [@BotFather](https://t.me/BotFather).
2. Save the API Token.
3. Use `/setmenubutton` to point to `https://YOUR_URL.onrender.com/webapp`.
4. (Optional) Create more bots for cloning.

### 3. Deploy to Render
1. Connect your GitHub repository.
2. Render will automatically detect `render.yaml`.
3. Set the required Environment Variables:
   - `PRIMARY_BOT_TOKEN`: Main bot token.
   - `SUPABASE_URL`: Your Supabase URL.
   - `SUPABASE_SERVICE_KEY`: Your Supabase Service Key.
   - `SUPABASE_CONNECTION_STRING`: Your Postgres Connection String.
   - `RENDER_EXTERNAL_URL`: Your Render app URL (e.g., `https://myapp.onrender.com`).

### 4. Local Testing
1. Install dependencies: `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and fill the values.
3. Set `SKIP_AUTH=true` for easier Mini App testing.
4. Run: `python main.py`.
5. Use ngrok to test webhooks locally: `ngrok http 8000`.

## 🐛 Debugging
- Visit `/` for health check.
- Use `/debug/db-ping` to check DB latency.
- Enable `DEBUG=true` for more verbose logging.
