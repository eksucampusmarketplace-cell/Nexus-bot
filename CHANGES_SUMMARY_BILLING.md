# Summary of Changes - Billing V2 Implementation

## Ticket: NEXUS BOT — UPDATED PLAN TIERS, TRIAL SYSTEM & BILLING PROMPT

This implementation completely restructures the billing system with new plan tiers, trial system, and property limits.

## Files Created

### Database Migrations
1. `db/migrations/add_billing_v2.sql` - Adds plan/trial columns to bots and groups tables
2. `db/migrations/add_billing_tables.sql` - Creates billing tables (subscriptions, payments, referrals, etc.)
3. `run_billing_migrations.py` - Script to run all billing migrations

### Billing Core
4. `bot/billing/plans.py` - Plan tier definitions (Free, Basic, Starter, Pro, Unlimited, Trial)
5. `bot/billing/billing_helpers.py` - Plan checking, limit validation, trial enforcement functions
6. `bot/billing/subscriptions.py` - Subscription management, trial lifecycle, webhook handling
7. `bot/billing/trial_reminders.py` - Trial reminder system (Day 1, 8, 12, 14, 15)

### Documentation
8. `BILLING_V2_IMPLEMENTATION.md` - Comprehensive implementation guide
9. `CHANGES_SUMMARY_BILLING.md` - This file

## Files Modified

### Bot Handlers
1. `bot/handlers/group_lifecycle.py`
   - Added trial expiration check on bot add/remove
   - Added chat_type tracking ('group', 'supergroup', 'channel')
   - Added property limit checking before allowing bot to join
   - Added `_leave_with_limit_message()` helper for property limit enforcement

2. `bot/handlers/clone.py`
   - Added automatic trial start when new clone bot is created
   - Updated success message to include trial information
   - Sends Day 1 trial reminder after creation

### API Routes
3. `api/routes/billing.py`
   - Added `/api/billing/plans` - Get all available plans
   - Added `/api/billing/owner-info` - Get owner's plan and usage statistics
   - Added `/api/billing/subscribe` - Subscribe to a plan
   - Added `/api/billing/cancel` - Cancel subscription auto-renewal
   - Added `/api/billing/trials` - Get active trials
   - Added `/api/billing/trial-days` - Get trial days remaining

### Database Operations
4. `db/ops/groups.py`
   - Updated `upsert_group()` to accept `chat_type` parameter
   - Modified SQL query to handle chat_type in INSERT/ON CONFLICT

## Key Features Implemented

### 1. Plan Tiers (5 Plans)
- **Free**: 1 clone bot, 5 properties/clone, 10 total properties
- **Basic**: 300 ⭐/mo, 2 clones, 15 properties/clone, 25 total
- **Starter**: 700 ⭐/mo, 5 clones, 30 properties/clone, 75 total
- **Pro**: 2,000 ⭐/mo, 20 clones, 100 properties/clone, 500 total
- **Unlimited**: 8,000 ⭐/mo, ∞ clones, 500 properties/clone, ∞ total properties

### 2. Trial System
- **15-day trial period** for all new clone bots
- **Starter plan features** during trial (5 clones, 75 total properties)
- **Trial expiration** causes bot to stop working entirely
- **Trial reminders** sent on Day 1, 8, 12, 14, 15
- **No free fallback** - bot inactive until upgrade or deletion

### 3. Property Limits
- **Properties = groups + channels** combined
- **Clone bots capped at 500 properties** max (even on Unlimited plan)
- **Primary bot unlimited** only if owner has Unlimited plan
- **Live counting** - always queries groups table for current usage

### 4. Chat Type Tracking
- **groups.chat_type** column added ('group', 'supergroup', 'channel')
- **Set automatically** when bot joins a group/channel
- **Used in property counting** - both types count as properties

### 5. Trial Enforcement
- **Message handler check** - `enforce_trial_limits()` at top of every handler
- **Group join check** - bot leaves immediately if trial expired
- **Silent mode** - expired bots don't respond to any messages
- **Exception** - `/start` and `/help` work in DM with owner only

### 6. Billing Tables
- **billing_subscriptions** - Owner's paid plans
- **payment_events** - Audit trail of all payments
- **stars_purchases** - Individual feature purchases (legacy)
- **promo_codes** - Promotional codes system
- **referrals** - Referral tracking
- **bonus_stars_balance** - Bonus stars balance
- **bonus_stars** - Transaction ledger

## Hard Rules Enforced

1. **Clone bots NEVER get unlimited properties**
   - `properties_per_clone` min 1, max 500
   - `group_limit=0` REJECTED for all clones
   - Unlimited plan clones capped at 500

2. **Primary bot follows owner's plan**
   - `total_properties=0` = unlimited for PRIMARY BOT only
   - Otherwise limited by owner's paid plan

3. **Properties = groups + channels**
   - 3 groups + 2 channels = 5 properties used

4. **Limits checked at:**
   - Bot join event (before registration)
   - API config save (before writing)
   - Clone creation (before insertion)
   - Always counted live from DB (no caching)

## Trial Reminder Messages

### Day 1 (Creation)
"🚀 @botname is live! You have 15 days of Starter features free. It manages {n} properties. After trial: bot goes inactive unless you upgrade."

### Day 8 (Halfway)
"⏳ 7 days left on @botname's trial. Upgrade now to keep it running after {expiry_date}."

### Day 12 (3 Days Left)
"⚠️ 3 days left for @botname. After {expiry_date} this bot will stop working completely."

### Day 14 (1 Day Left)
"🚨 FINAL WARNING: @botname stops working TOMORROW ({expiry_date})."

### Day 15 (Expiry)
"⛔ @botname has expired and is now inactive. It is still in {n} properties but doing nothing. Upgrade to reactivate it."

## API Response Examples

### GET /api/billing/plans
```json
{
  "plans": [
    {
      "key": "free",
      "name": "Free",
      "price_stars": 0,
      "price_display": "Free forever",
      "clone_bots": 1,
      "properties_per_clone": 5,
      "total_properties": 10,
      "features": [...]
    },
    ...
  ]
}
```

### GET /api/billing/owner-info
```json
{
  "plan": "basic",
  "plan_name": "Basic",
  "clone_bots_allowed": 2,
  "clone_bots_used": 1,
  "can_add_clone": true,
  "clone_error": null,
  "total_properties_allowed": 25,
  "total_properties_used": 15,
  "properties_within_limit": true,
  "property_error": null,
  "active_trials": [...]
}
```

## Database Backfill

Existing bots are backfilled:
- **Primary bots**: `plan='primary'`, `trial_used=TRUE`
- **Existing clones**: `plan='free'`, `trial_used=TRUE`
  - Created before trial system, so they're on free tier

## Deployment Steps

1. **Run migrations**
   ```bash
   python3 run_billing_migrations.py
   ```

2. **Restart bot application**
   - Ensure new billing modules are loaded
   - Trial reminders will start working

3. **Test cloning a bot**
   - Verify trial started automatically
   - Check Day 1 reminder sent

4. **Test limits**
   - Add bot to groups until limit reached
   - Verify bot leaves with message

5. **Monitor trial expiration**
   - Wait or manually advance trial_ends_at
   - Verify bot goes silent

## Integration Points

### For Mini App

1. **Display trial status** on bot cards
2. **Show upgrade modal** with 5 plan cards
3. **Call `/api/billing/plans`** to get plan options
4. **Call `/api/billing/subscribe`** when user selects plan
5. **Display property usage** progress bars

### For Bot Handlers

1. **Add trial check** at top of every message handler:
   ```python
   if not await enforce_trial_limits(db_pool, bot_id, context):
       return
   ```

2. **Check property limits** before allowing bot to join
3. **Send trial reminders** via primary bot
4. **Handle trial_expired** bots with silent mode

## Known Limitations

1. **Payment integration** - Endpoints created but Telegram Stars payment flow needs implementation
2. **Scheduled expiry check** - Needs background task to check expired trials hourly
3. **Mini App UI** - Needs to display trial status and upgrade modal
4. **Trial reminder scheduling** - Currently manual, needs automated scheduler

## Testing Checklist

- [ ] Database migrations run successfully
- [ ] New clone bots get 15-day trial
- [ ] Trial expiration stops bot from working
- [ ] Property limits enforced at join time
- [ ] Trial reminders sent on correct days
- [ ] Owner info API returns correct plan
- [ ] Chat type stored in groups table
- [ ] Primary bot follows owner's plan

## Next Steps

1. **Implement Telegram Stars payment** in `/api/billing/subscribe`
2. **Add scheduled task** for checking expired trials
3. **Update Mini App** to display trial status and upgrade modal
4. **Add analytics** for tracking trial conversion rates
5. **Implement webhook handler** for payment confirmations
