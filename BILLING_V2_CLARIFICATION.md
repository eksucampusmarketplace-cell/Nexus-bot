# Billing V2 - How It Works (Important Clarifications)

## You Don't Need to Set Up Payments Yet!

The billing system works **without** Telegram Stars payments for now. Here's what you need to know:

---

## Primary Bot Status

✅ **Primary bot is FREE and NEVER expires**

The primary bot has `plan='primary'` in the database, which means:
- **No subscription needed** - it's always active
- **Follows owner's plan** - but only for property limits
- **Never expires** - doesn't have trial or expiry

### Example: Owner on Free Plan
```sql
owner.plan = 'free'
primary_bot.plan = 'primary'

Result:
- Primary bot has 10 total properties (from Free plan)
- Clone bots limited to 1 total
- Everything works, no payment needed
```

### Example: Owner on Unlimited Plan
```sql
owner.plan = 'unlimited'
primary_bot.plan = 'primary'

Result:
- Primary bot has UNLIMITED properties
- Clone bots limited to 20 total
- Premium features enabled via owner's subscription
```

---

## What You DO Need to Do

### 1. Run the Migrations (ONCE)

```bash
cd /home/engine/project
python3 run_billing_migrations.py
```

This sets up the database structure. That's it!

### 2. Restart Your Bot

Just restart the bot application. The billing system will:
- Auto-start trials for new clone bots
- Enforce property limits when bots join groups
- Handle trial expiration automatically
- Track chat types (group vs channel)

### 3. No API Input Required

All the API endpoints are **already created** in `api/routes/billing.py`:
- `/api/billing/plans` - Returns plan definitions
- `/api/billing/owner-info` - Returns owner's current usage
- `/api/billing/subscribe` - For when you DO want payments later

You don't need to add any API code. It's all there!

---

## How Plans Work Right Now (Without Payments)

### For Testing/Development

You can manually set owner plans in the database:

```sql
-- Set owner to Pro plan
UPDATE billing_subscriptions
SET plan = 'pro',
    plan_expires_at = NOW() + INTERVAL '1 month'
WHERE owner_id = 123456789;

-- Or check current plan
SELECT * FROM billing_subscriptions
WHERE owner_id = 123456789
ORDER BY created_at DESC
LIMIT 1;
```

### Default Behavior

If no subscription record exists for an owner:
```python
# In billing_helpers.py, get_owner_plan() does this:
if no_subscription:
    return "free"  # Default to Free plan
```

So without any payment system:
- All owners start on Free plan (1 clone bot, 10 total properties)
- Primary bot always works (plan='primary')
- Clone bots get 15-day trial then become inactive
- Everything enforces limits automatically

---

## Trial System (No Payment Needed!)

When you clone a bot:

1. **Trial starts automatically** (in `bot/handlers/clone.py`)
2. **Bot gets Starter features** for 15 days (75 total properties)
3. **After 15 days**: Bot becomes inactive (plan='trial_expired')

No payment required for any of this! The trial system works independently.

---

## When Would You Need Telegram Stars?

### ONLY If You Want to Charge Users

You only need to set up Telegram Stars payments if:

1. **You want users to pay for premium plans**
2. **You want to accept payments via Mini App**
3. **You're in production** and monetizing the bot

### If NOT Monetizing

For now, you can:
- ✅ Use the billing system as-is (Free plan for everyone)
- ✅ Manually upgrade users in the database (if you want)
- ✅ Test everything with trials and limits
- ✅ Skip payment integration entirely

### Manual Plan Upgrades

Instead of payments, you can upgrade users manually:

```python
# In Python, upgrade an owner to Pro
from bot.billing.subscriptions import create_subscription
from datetime import datetime, timedelta

await create_subscription(
    db_pool=db.pool,
    owner_id=123456789,
    plan_key="pro",
    charge_id="manual_upgrade",  # Not from Telegram
    stars_paid=2000  # For tracking purposes
)
```

This works without any Telegram Stars setup!

---

## Quick Start - What to Do Today

### Step 1: Run Migrations
```bash
python3 run_billing_migrations.py
```

### Step 2: Restart Bot
```bash
# Restart your bot application
# The billing system will be active
```

### Step 3: Test Cloning
```bash
# Clone a bot in Telegram with /clone
# It should automatically get 15-day trial
```

### Step 4: Test Limits
```bash
# Add the clone bot to groups
# After 75 groups, it should stop accepting new ones
```

### Step 5: Done!
That's it. Everything else happens automatically.

---

## What's Working Right Now

✅ **Automatic Trial System**
- New clone bots get 15-day trial
- Trial enforces Starter plan limits
- Trial expires automatically

✅ **Property Limit Enforcement**
- Counts groups + channels together
- Enforces plan limits at join time
- Bot leaves if limit exceeded

✅ **Trial Expiration**
- Bot stops working after 15 days
- Bot stays in groups (silent mode)
- Owner gets expiry notifications

✅ **Primary Bot**
- Always active (plan='primary')
- Follows owner's plan for limits
- Never expires

✅ **Chat Type Tracking**
- Groups and channels counted together
- Stored in database
- Used for property counting

---

## What's NOT Working (Until You Add It)

❌ **Telegram Stars Payments**
- Need to implement payment handlers
- Need to verify bot with BotFather
- See `TELEGRAM_STARS_SETUP_GUIDE.md` when ready

❌ **Auto-Renewal**
- Requires payment system
- Telegram Stars don't support auto-renew
- Manual renewal only

❌ **Mini App Upgrade UI**
- Need to add upgrade modal
- Need to integrate with API
- See `BILLING_CODE_EXAMPLES.md` for examples

---

## Summary

### You DON'T Need:
- ❌ Input any API keys
- ❌ Set up payments (unless you want to monetize)
- ❌ Create new API endpoints (already done)
- ❌ Modify existing code (migrations only)

### You DO Need:
- ✅ Run `python3 run_billing_migrations.py`
- ✅ Restart your bot application
- ✅ Test the trial system
- ✅ Test property limits
- ✅ Optionally: Manually upgrade owners in database

---

## The Primary Bot is ALWAYS Free

```
Primary Bot:
├── Plan: 'primary'
├── Expires: NEVER
├── Properties: Follows owner's subscription
└── Required Payment: NONE
```

The primary bot doesn't need a subscription. It's the **admin bot** that:
- Manages clone bots
- Handles payments (when you add them)
- Sends trial reminders
- Manages the Mini App

It's like the "dashboard bot" - always there, always working.

---

## Questions?

### Q: Do I need to set up payments now?
**A**: No! The system works without payments. Set them up only when you want to charge users.

### Q: Does the primary bot expire?
**A**: Never! It has plan='primary' which never expires.

### Q: What if I want to test different plans?
**A**: Manually insert a subscription record in the database for the owner:
```sql
INSERT INTO billing_subscriptions
(owner_id, plan, telegram_charge_id, stars_paid, plan_expires_at)
VALUES
(123456789, 'pro', 'manual_test', 2000, NOW() + INTERVAL '1 month');
```

### Q: Do I need to modify API code?
**A**: No! All endpoints are already in `api/routes/billing.py`.

### Q: When should I set up Telegram Stars?
**A**: Only when:
1. You're ready to monetize
2. You have 100+ users
3. You've tested everything else

---

## Ready to Go!

You can use the billing system right now without any payments. Just:
1. Run migrations
2. Restart bot
3. Everything works!

Payment setup is optional and can be done later.
