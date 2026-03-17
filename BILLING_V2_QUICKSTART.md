# Billing V2 Quick Start Guide

Get the billing system up and running quickly.

## Step 1: Run Database Migrations

```bash
cd /home/engine/project
python3 run_billing_migrations.py
```

This will:
- Add plan/trial columns to bots table
- Add chat_type column to groups table
- Create all billing tables (subscriptions, payments, referrals, etc.)
- Backfill existing bots with appropriate plan values

## Step 2: Verify Migrations

Check that tables were created:

```bash
# Check billing tables exist in database
# You should see:
# - billing_subscriptions
# - payment_events
# - stars_purchases
# - promo_codes
# - referrals
# - bonus_stars_balance
# - bonus_stars
```

## Step 3: Test Clone Bot Creation

Clone a new bot and verify:

```bash
# In Telegram with primary bot:
/clone

# Paste a valid bot token
# Confirm the clone
```

Verify in database:
```sql
-- Check bot has trial status
SELECT bot_id, username, plan, trial_ends_at, trial_used
FROM bots
WHERE username = '@your_clone_bot';
-- Should show: plan='trial', trial_ends_at = 15 days from now
```

## Step 4: Test Property Limits

Add the clone bot to groups and verify limits:

```bash
# Add bot to groups via Telegram
# Check when limit is reached
```

Expected behavior:
- Trial bot can be added to 75 properties (groups + channels)
- After 75th property, bot leaves with message
- Owner gets notification about limit

## Step 5: Test Trial Expiration

Manually expire a trial to test enforcement:

```sql
-- Set trial to expire immediately
UPDATE bots
SET trial_ends_at = NOW() - INTERVAL '1 day'
WHERE username = '@your_clone_bot';
```

Then test:
- Send message in a group with the bot → Should get no response
- Add bot to new group → Bot should leave immediately
- Send /start to bot in DM → Should work (owner only)

## Step 6: Check Trial Enforcement

Verify bot plan changed to expired:

```sql
SELECT bot_id, username, plan
FROM bots
WHERE username = '@your_clone_bot';
-- Should show: plan='trial_expired'
```

## Step 7: Set Up Telegram Stars (Optional)

Follow the detailed guide: `TELEGRAM_STARS_SETUP_GUIDE.md`

Quick steps:
1. Verify bot with @BotFather (`/payments`)
2. Get test Stars (`/teststars`)
3. Implement payment handlers in your bot
4. Update API to generate invoice links
5. Update Mini App to open invoice links

## Step 8: Test Trial Reminders

Send test reminders manually:

```python
# In Python REPL
from db.client import db
from bot.billing.trial_reminders import check_and_send_reminders
import asyncio

asyncio.run(db.connect())

# Send reminders for all trials
await check_and_send_reminders(db.pool, primary_bot)
```

## Step 9: Monitor Logs

Check logs for billing operations:

```bash
# View recent logs
tail -f logs/nexus-bot.log | grep -E "\[BILLING\]|\[TRIAL\]|\[SUBSCRIPTION\]"

# Expected log prefixes:
# [BILLING] - Billing operations
# [TRIAL] - Trial lifecycle
# [SUBSCRIPTION] - Subscription management
# [TRIAL_REMINDERS] - Trial reminders
```

## Step 10: Verify API Endpoints

Test the new API endpoints:

```bash
# Get all plans
curl http://localhost:8000/api/billing/plans

# Get owner info (requires auth)
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/billing/owner-info

# Get active trials (requires auth)
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/billing/trials
```

## Common Issues

### Migration Fails

**Issue**: "column already exists" error

**Solution**: Run with `IF NOT EXISTS` (already in migration SQL)

### Trial Not Started

**Issue**: New clone bot doesn't have trial status

**Solution**: Check `bot/handlers/clone.py` has trial start call
- Look for `await start_trial(db_pool, bot_id)` around line 956

### Property Limits Not Enforced

**Issue**: Bot joins more groups than limit allows

**Solution**: Check `bot/handlers/group_lifecycle.py` has property limit check
- Look for `await check_property_limit()` call around line 161

### Trial Bot Still Responds After Expiry

**Issue**: Bot processes messages after trial ends

**Solution**: Add trial enforcement to message handlers:
```python
from bot.billing.billing_helpers import enforce_trial_limits

async def handle_message(update, context):
    if not await enforce_trial_limits(db_pool, bot_id, context):
        return  # Bot is expired, stop processing
```

## Next Steps

### For Testing
1. Test all plan tiers
2. Test property limits for each plan
3. Test trial expiration and reminders
4. Test upgrade/downgrade flows
5. Test payment flow (if implementing Stars)

### For Production
1. Set up automated trial expiry checking (scheduler)
2. Set up automated trial reminders (scheduler)
3. Implement Telegram Stars payment (if ready)
4. Monitor billing metrics
5. Set up alerts for payment failures

### For Mini App
1. Display trial status on bot cards
2. Show upgrade modal with 5 plan cards
3. Display property usage visualization
4. Add trial countdown timer
5. Handle payment completion

## Reference Guides

- `BILLING_V2_IMPLEMENTATION.md` - Full implementation details
- `TELEGRAM_STARS_SETUP_GUIDE.md` - Stars payment setup
- `BILLING_CODE_EXAMPLES.md` - Code snippet reference
- `CHANGES_SUMMARY_BILLING.md` - Summary of all changes

## Support

If you encounter issues:

1. Check logs for error messages
2. Review implementation guides
3. Check code examples for similar patterns
4. Verify database migrations ran successfully
5. Ensure bot has proper permissions

## Quick Reference

| Plan | Price | Clones | Properties/Clone | Total |
|-------|--------|---------|------------------|--------|
| Free | 0 ⭐ | 1 | 5 | 10 |
| Basic | 300 ⭐ | 2 | 15 | 25 |
| Starter | 700 ⭐ | 5 | 30 | 75 |
| Pro | 2,000 ⭐ | 20 | 100 | 500 |
| Unlimited | 8,000 ⭐ | ∞ | 500 | ∞* |

*Unlimited properties on PRIMARY BOT only. Clone bots capped at 500.

**Trial**: 15 days, Starter features (75 total properties), then INACTIVE.

You're ready to go! 🚀
