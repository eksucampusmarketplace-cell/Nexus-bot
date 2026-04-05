# Why Webhooks Show "4/5 Active" - Complete Guide

## What This Means

The "Webhooks: 4/5 active" in your System Health dashboard refers to **Telegram bot webhooks** for your bot instances (main bot + clones). These are NOT the webhook integrations feature for external services like Discord/Zapier.

**"4/5 active" means:**
- You have 5 total bot instances registered (1 primary bot + 4 clones)
- 4 bots have successfully registered and are actively receiving updates from Telegram
- 1 bot's webhook is inactive and NOT receiving updates from Telegram

## How Bot Webhooks Work

1. **Telegram sends updates** to your bot via a webhook URL (your server)
2. **Each bot instance** (main + clones) needs its own webhook URL
3. **Webhook must be registered** with Telegram for each bot
4. **If webhook is inactive**, that bot won't receive ANY messages/commands

## Why a Webhook Becomes Inactive

Common causes:

1. **Initial registration failed** - The `/setWebhook` API call failed during bot clone creation
2. **Token was revoked** - Bot owner regenerated the token in BotFather
3. **Webhook was deleted** - Someone called `/deleteWebhook` on the bot
4. **Server URL changed** - Your deployment URL changed and webhook wasn't re-registered
5. **Network/Telegram errors** - Temporary connectivity issues during registration
6. **PTB app not running** - The bot application crashed and didn't restart

## How to Diagnose Which Bot is Inactive

### Option 1: Use the Diagnostic Script

```bash
cd /home/engine/project
python diagnose_webhooks.py
```

This will:
- Show all 5 bots and their webhook status
- Check live webhook info from Telegram API
- Show pending updates and any errors
- Offer to fix inactive webhooks automatically

### Option 2: Check Manually via Database

```sql
SELECT
    bot_id,
    username,
    is_primary,
    status,
    webhook_active,
    webhook_url,
    death_reason
FROM bots
ORDER BY is_primary DESC;
```

Look for:
- `webhook_active = false`
- `death_reason` column (shows why it became inactive)
- `status != 'active'`

### Option 3: Check via Owner Panel

1. Open Owner Panel in the Mini App
2. Look at the "Clone Status" section
3. Bots with 🔴 (red) or 🟡 (yellow) status may have webhook issues
4. Click on each bot to see the `death_reason` if available

## How to Fix an Inactive Webhook

### Method 1: Using the Diagnostic Script (Recommended)

```bash
python diagnose_webhooks.py
```

When prompted, enter `y` to fix inactive webhooks. The script will:
- Generate the correct webhook URL
- Call Telegram's `/setWebhook` API
- Update database to mark as active
- Clear any death reasons

### Method 2: Re-authenticate a Dead Bot via API

If a bot has `status = 'dead'`:

```bash
# Get the bot_id from the database first
# Then call the reauth API with a NEW token from BotFather

curl -X PUT https://your-app.com/api/bots/{bot_id}/reauth \
  -H "Content-Type: application/json" \
  -d '{
    "token": "NEW_BOT_TOKEN_FROM_BOTFATHER"
  }'
```

### Method 3: Manual Webhook Registration

If you have bot token and server URL:

```bash
# Get webhook info first
curl "https://api.telegram.org/bot{TOKEN}/getWebhookInfo"

# Set webhook (replace with your actual values)
curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com/webhook/{WEBHOOK_SECRET}",
    "allowed_updates": ["message", "callback_query", "chat_member", "my_chat_member", "inline_query"],
    "drop_pending_updates": true
  }'

# Verify it worked
curl "https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
```

### Method 4: Fix via Mini App (If Available)

Some deployments may have a "Reauth" button in the Clone Status section for dead bots.

## Preventing Future Inactive Webhooks

1. **Monitor the dashboard** - Check System Health regularly
2. **Don't regenerate tokens unnecessarily** - This breaks existing webhooks
3. **Keep server URL stable** - Changing deployment URL requires re-registering all webhooks
4. **Monitor bot logs** - Check for webhook-related errors
5. **Use health checks** - Set up monitoring to alert when webhooks fail

## Impact of Inactive Webhook

When a bot's webhook is inactive:
- ❌ The bot won't receive ANY messages
- ❌ Commands won't work
- ❌ AutoMod won't trigger
- ❌ No group moderation functions
- ✅ Database operations may still work (if called directly)
- ✅ Other bot instances remain unaffected

## Related Code Locations

- Dashboard: `/miniapp/src/pages/owner.js` (line 363-398)
- Bot management: `/api/routes/bots.py`
- Database ops: `/db/ops/bots.py`
- Webhook dispatcher: `/bot/utils/webhook_dispatcher.py`

## Common Error Messages

In `death_reason` field:
- `"Webhook registration failed"` - Telegram rejected the webhook URL
- `"Invalid token"` - Token is malformed or revoked
- `"Telegram API timeout"` - Network issue during registration
- `"PTB app not running"` - Bot application crashed

## Still Need Help?

If the diagnostic script doesn't solve the issue:
1. Check server logs for webhook-related errors
2. Verify your server URL is publicly accessible
3. Check Telegram's response to `/getWebhookInfo`
4. Ensure SSL certificate is valid (required for webhooks)
5. Check firewall rules allow Telegram servers (149.154.160.0/20, 91.108.4.0/22)
