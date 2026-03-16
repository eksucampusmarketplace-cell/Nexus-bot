# Billing V2 Implementation

This document describes the implementation of the updated plan tiers, trial system, and billing for Nexus Bot.

## Overview

The billing system has been completely redesigned with the following key changes:

- **5 Plan Tiers**: Free, Basic, Starter, Pro, Unlimited
- **15-Day Trial System**: New clone bots get Starter features for 15 days
- **Properties = Groups + Channels**: Both counted together under plan limits
- **Hard Limits Enforced**: Clone bots never get unlimited properties (max 500)
- **Trial Expiration**: Bot stops working entirely after trial ends

## Database Changes

### New Tables

1. **billing_subscriptions**: Tracks owner's paid subscriptions
   - `plan`: 'basic', 'starter', 'pro', 'unlimited'
   - `plan_expires_at`: When subscription renews or ends
   - `auto_renew`: Whether to auto-renew

2. **payment_events**: Audit trail of all payments
   - `event_type`: 'subscription', 'trial_reminder', etc.
   - `item_type`: Plan key or feature type
   - `stars_paid`: Amount paid

3. **stars_purchases**: Individual feature purchases (legacy support)
   - `item_type`: 'feat_analytics', 'group_slot', etc.
   - `expires_at`: When feature expires

4. **promo_codes**: Promotional codes for bonuses
   - `reward_type`: 'bonus_stars', 'feature_unlock', etc.
   - `max_uses`: Max number of uses

5. **promo_redemptions**: Tracks who redeemed which codes

6. **referrals**: Referral system
   - `referrer_id`, `referred_id`
   - `bonus_stars`: Amount earned
   - `rewarded`: Whether reward was given

7. **bonus_stars_balance**: Owner's bonus stars balance

8. **bonus_stars**: Ledger of all bonus star transactions

### Column Additions

**bots table:**
- `plan`: 'primary', 'free', 'trial', 'trial_expired', 'basic', 'starter', 'pro', 'unlimited'
- `plan_expires_at`: Subscription expiry
- `trial_ends_at`: When trial ends (for trial plan)
- `trial_used`: Whether owner has used their trial

**groups table:**
- `chat_type`: 'group', 'supergroup', 'channel'

## Plan Tiers

| Plan        | Price/mo | Clones | Per-Clone | Total | Trial |
|-------------|-----------|--------|------------|--------|-------|
| Free        | 0 ⭐      | 1      | 5          | 10     | No    |
| Basic       | 300 ⭐    | 2      | 15         | 25     | No    |
| Starter     | 700 ⭐    | 5      | 30         | 75     | No    |
| Pro         | 2,000 ⭐  | 20     | 100        | 500    | No    |
| Unlimited   | 8,000 ⭐  | ∞      | 500        | ∞*     | No    |
| Trial       | Free      | —      | 30         | 75     | 15 days |

* Unlimited properties on PRIMARY BOT only. Clone bots always capped at 500.

## Hard Rules

1. **Clone bots NEVER get unlimited properties**
   - `properties_per_clone` is always 1-500
   - Even Unlimited plan clone bots are capped at 500

2. **Primary bot follows owner's plan**
   - `total_properties=0` means unlimited for PRIMARY BOT only
   - Otherwise limited by owner's plan

3. **Properties = groups + channels combined**
   - A bot in 3 groups and 2 channels = 5 properties used

4. **Limits are enforced at:**
   - Bot join event (before registration)
   - API config save (before writing limits)
   - Clone bot creation (before insertion)
   - All queries count live from groups table

## Trial System

### 15-Day Trial Period

- **Trial Level**: Starter plan features and limits
  - 5 clone bots
  - 75 total properties
  - 30 properties per clone

- **What happens after trial ends:**
  - Bot's plan set to 'trial_expired'
  - Bot ignores ALL incoming messages
  - Bot stays in groups silently (does not leave)
  - No response, no enforcement (complete silent mode)
  - Owner gets DM with instructions

- **NO FREE FALLBACK:**
  - No automatic downgrade to free tier
  - Only paths after expiry:
    - A. Owner pays → bot reactivates
    - B. Owner deletes clone bot

### Trial Status Values

- `plan = 'trial'` → Active trial
- `plan = 'trial_expired'` → Trial ended, bot inactive
- `plan = 'free'` → Never on trial, or owner paid for free
- `plan = 'basic'/'starter'/'pro'/'unlimited'` → Paid plans
- `plan = 'primary'` → Primary bot (never expires)

### Trial Enforcement

In every message handler, at the very top:

```python
from bot.billing.billing_helpers import enforce_trial_limits

async def handle_message(update, context):
    if not await enforce_trial_limits(db_pool, bot_id, context):
        return  # Bot is trial_expired, ignore message
    # ... rest of handler
```

In `bot/handlers/group_lifecycle.py` when bot joins a group:

```python
if await is_trial_expired(db_pool, bot_id):
    await bot.leave_chat(chat_id)
    return
```

### Trial Reminders

DM to owner via primary bot on:

- **Day 1** (on creation):
  - "🚀 @botname is live! You have 15 days of Starter features free.
     It manages {n} properties. After trial: bot goes inactive unless you upgrade."

- **Day 8** (halfway):
  - "⏳ 7 days left on @botname's trial.
     Upgrade now to keep it running after {expiry_date}."

- **Day 12** (3 days left):
  - "⚠️ 3 days left for @botname.
     After {expiry_date} this bot will stop working completely."

- **Day 14** (1 day left):
  - "🚨 FINAL WARNING: @botname stops working TOMORROW ({expiry_date})."

- **Day 15** (on expiry):
  - "⛔ @botname has expired and is now inactive.
     It is still in {n} properties but doing nothing.
     Upgrade to reactivate it."

## API Endpoints

### Plan Endpoints

- `GET /api/billing/plans` - Get all available plans
- `GET /api/billing/owner-info` - Get owner's plan and usage

### Subscription Endpoints

- `POST /api/billing/subscribe` - Subscribe to a plan
- `POST /api/billing/cancel` - Cancel auto-renewal

### Trial Endpoints

- `GET /api/billing/trials` - Get all active trials
- `GET /api/billing/trial-days?bot_id=X` - Get days remaining

### Bonus Stars (existing)

- `GET /api/billing/bonus-balance` - Get bonus stars balance
- `POST /api/billing/redeem-promo` - Redeem promo code
- `POST /api/billing/spend-bonus` - Spend bonus stars

### Owner/Admin

- `POST /api/billing/grant-bonus` - Grant bonus stars (owner only)
- `POST /api/billing/create-promo` - Create promo code (owner only)
- `GET /api/billing/referral-stats` - Get referral stats

## Code Organization

### New Files

- `bot/billing/plans.py` - Plan tier definitions and lookup functions
- `bot/billing/billing_helpers.py` - Plan checking, limit validation, trial enforcement
- `bot/billing/subscriptions.py` - Subscription management and trial lifecycle
- `bot/billing/trial_reminders.py` - Trial reminder system
- `db/migrations/add_billing_v2.sql` - Bots/groups table updates
- `db/migrations/add_billing_tables.sql` - Billing tables creation
- `run_billing_migrations.py` - Migration runner script

### Modified Files

- `bot/handlers/group_lifecycle.py` - Added chat_type tracking, property limit checks, trial enforcement
- `bot/handlers/clone.py` - Auto-start trial on clone creation
- `api/routes/billing.py` - Added plan/subscription endpoints
- `db/ops/groups.py` - Added chat_type parameter to upsert_group

## Running Migrations

```bash
# Run billing migrations
python3 run_billing_migrations.py
```

This will:
1. Add billing columns to bots and groups tables
2. Create all billing tables
3. Backfill existing bots with appropriate plan values

## Testing Checklist

### 1. Database Migration
- [ ] Run `run_billing_migrations.py`
- [ ] Verify tables created in database
- [ ] Check bots table has new columns
- [ ] Check groups table has chat_type column

### 2. Clone Bot Creation
- [ ] Clone a new bot
- [ ] Verify bot has `plan='trial'`
- [ ] Verify `trial_ends_at` is set to 15 days from now
- [ ] Verify Day 1 reminder is sent

### 3. Trial Enforcement
- [ ] Wait for trial to expire or manually set `trial_ends_at` to past
- [ ] Verify bot plan changes to 'trial_expired'
- [ ] Send message in group - verify bot does nothing
- [ ] Send /start command to bot in DM - verify it works
- [ ] Add bot to new group - verify it leaves immediately

### 4. Property Limits
- [ ] Create bot on Free plan
- [ ] Add to 5 groups - verify success
- [ ] Add to 6th group - verify bot leaves with limit message
- [ ] Check groups table for chat_type values

### 5. Plan Upgrades
- [ ] Call `/api/billing/subscribe` with plan='basic'
- [ ] Verify subscription created in database
- [ ] Verify property limits increased
- [ ] Check trial bots reactivated

### 6. Trial Reminders
- [ ] Create trial bot
- [ ] Verify Day 1 reminder sent
- [ ] Manually advance time to Day 8 - verify reminder sent
- [ ] Manually advance time to Day 14 - verify warning sent
- [ ] Manually advance time to Day 15 - verify expiry message sent

## Migration Notes

### Backfill Behavior

Existing bots are backfilled as follows:

- **Primary bots**: `plan='primary'`, `trial_used=TRUE`
- **Existing clones**: `plan='free'`, `trial_used=TRUE`
  - They were created before trial system, so they're on free tier

### New Clone Bots

All new clone bots automatically:
- Start with `plan='trial'`
- Get `trial_ends_at = now() + 15 days`
- Get `trial_used=TRUE`
- Receive Day 1 creation reminder

## Upgrade Modal UI (Mini App)

### Display Logic

For `plan === 'trial'` AND `trial_ends_at > now`:
- Show green→yellow gradient banner:
  - "🕐 Trial active — {N} days remaining (expires {date})"
- Progress bar: `days_elapsed / 15`

For `plan === 'trial_expired'`:
- Show red banner:
  - "⛔ Trial expired — bot is INACTIVE"
- Show "⬆️ Upgrade to Reactivate" button
- Show "🗑️ Delete Bot" button
- Grey out the entire bot card

For `plan === 'free'`:
- No trial banner
- Show normal Free plan badge

### Upgrade Modal

Show 5 cards (Free, Basic, Starter, Pro, Unlimited):
- Current plan highlighted with "✓ Current Plan" badge
- Free plan shows "Free — no payment needed" with no upgrade button
- Paid plans show:
  - Plan name + price per month in Stars
  - Key numbers: `{clone_bots} bots · {total_properties} properties`
  - Feature bullet list (3-4 most important)
  - "Upgrade" button

Note under pricing:
- "Paid with Telegram Stars. Billed monthly. Cancel anytime."
- "Clone bots are always capped — unlimited applies to your primary bot only."

## Future Enhancements

1. **Telegram Stars Payment Integration**
   - Generate payment links via `/api/billing/subscribe`
   - Handle payment webhooks
   - Verify payments via Telegram API

2. **Automatic Trial Expiry Checking**
   - Scheduled task to check for expired trials hourly
   - Mark expired trials as 'trial_expired'
   - Send Day 15 expiry reminders

3. **Mini App UI Updates**
   - Add trial status banners to bot cards
   - Add upgrade modal with 5 plan cards
   - Show property usage visualization
   - Display trial countdown timer

4. **Analytics Dashboard**
   - Track trial conversion rates
   - Monitor plan distribution
   - Property usage analytics
