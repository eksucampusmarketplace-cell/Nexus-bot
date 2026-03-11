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

## ⚠️ Troubleshooting

### "Network is unreachable" Error
If you see this error in your Render logs:
```
OSError: [Errno 101] Network is unreachable
```

This means the application cannot connect to your Supabase database. Common causes:

1. **Missing Environment Variables**: Make sure all required environment variables are set in your Render dashboard:
   - `SUPABASE_CONNECTION_STRING` - Must be a valid PostgreSQL connection string
   - `SUPABASE_URL` - Your Supabase project URL
   - `SUPABASE_SERVICE_KEY` - Your Supabase service role key

2. **Invalid Connection String**: The `SUPABASE_CONNECTION_STRING` should look like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
   - Replace `[YOUR-PASSWORD]` with your actual database password
   - Replace `[PROJECT-REF]` with your Supabase project reference

3. **Connection Pooler**: On free Render plans, use Supabase's Connection Pooler (Transaction mode) for better stability:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?pgbouncer=true
   ```

4. **IPv6 vs IPv4**: If you have network issues, ensure your connection uses IPv4 addresses.

### Application Starts Without Database
If the app starts but shows `"db": "disconnected"` in the health check:
- Check that your Supabase database is active (not paused due to inactivity)
- Verify your connection string credentials
- Check Render's environment variable settings
