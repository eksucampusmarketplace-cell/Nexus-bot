# Quick Fix: "Webhooks 4/5 Active"

## TL;DR

Your System Health shows "4/5 active" because **1 of your 5 bot instances (main bot + 4 clones) has an inactive Telegram webhook**. This means that bot won't receive any messages or commands.

## Immediate Action

Run the diagnostic script:

```bash
cd /home/engine/project
python diagnose_webhooks.py
```

Follow the prompts to:
1. See which bot has the inactive webhook
2. Read the error/reason
3. Fix it automatically (or manually)

## What the Script Does

✅ Checks webhook status for all 5 bots
✅ Queries Telegram API for live webhook info
✅ Shows pending updates and errors
✅ Re-registers webhooks if you approve
✅ Updates database and clears errors

## If Script Fails

Check these 3 things:

1. **Database connection** - Make sure `.env` has valid database credentials
2. **Server URL** - Verify `RENDER_EXTERNAL_URL` is set and accessible
3. **Bot token** - Make sure the bot token is still valid (not revoked in BotFather)

## Manual Fix (Last Resort)

```bash
# Get bot_id and token from database
# Then register webhook manually:

curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com/webhook/{SECRET}",
    "drop_pending_updates": true
  }'
```

## After Fixing

- ✅ Check System Health again - should show "5/5 active"
- ✅ Test the bot by sending a message
- ✅ Verify AutoMod and moderation functions work

## Prevention

- Don't regenerate bot tokens unless necessary
- Keep your deployment URL stable
- Monitor System Health dashboard regularly
- Check logs for webhook errors

---

Need more details? Read the complete guide in `WEBHOOK_INACTIVE_EXPLANATION.md`
