# Billing Code Examples

Quick code snippets for billing system implementation.

## 1. Check if Bot Can Add More Properties

```python
from bot.billing.billing_helpers import check_property_limit
from bot.utils.crypto import hash_token

token_hash = hash_token(bot.token)
can_add, error_msg = await check_property_limit(
    db_pool=db.pool,
    bot_id=bot.id,
    token_hash=token_hash,
    adding=1
)

if not can_add:
    await update.message.reply_text(error_msg)
    return
```

## 2. Get Owner's Current Plan

```python
from bot.billing.billing_helpers import get_owner_plan
from bot.billing.plans import get_plan

plan_key = await get_owner_plan(db.pool, owner_id)
plan_config = get_plan(plan_key)

print(f"Owner is on {plan_config['name']} plan")
print(f"Can have {plan_config['clone_bots']} clone bots")
print(f"Total properties: {plan_config['total_properties']}")
```

## 3. Enforce Trial Limits in Message Handler

```python
from bot.billing.billing_helpers import enforce_trial_limits

async def handle_my_command(update, context):
    # Check trial expiration at the TOP
    if not await enforce_trial_limits(context.bot_data.get("db_pool"), context.bot.id, context):
        return

    # ... rest of handler
```

## 4. Send Trial Reminders Manually

```python
from bot.billing.trial_reminders import check_and_send_reminders

# Call this periodically (e.g., every 6 hours via scheduler)
await check_and_send_reminders(db.pool, primary_bot)
```

## 5. Get Trial Days Remaining

```python
from bot.billing.subscriptions import get_trial_days_remaining

days = await get_trial_days_remaining(db.pool, bot_id)
if days is not None:
    print(f"Trial expires in {days} days")
else:
    print("Bot is not on trial")
```

## 6. Create and Send Invoice

```python
from telegram import LabeledPrice

async def send_subscription_invoice(bot, chat_id, plan_key):
    from bot.billing.plans import get_plan

    plan = get_plan(plan_key)

    invoice_link = await bot.create_invoice_link(
        title=f"{plan['name']} Plan",
        description=f"Monthly subscription to {plan['name']} plan",
        payload=f"subscribe_{plan_key}",
        provider_token="",  # Empty for Stars
        currency="XTR",
        prices=[LabeledPrice(plan['price_display'], plan['price_stars'])],
        max_tip_amount=100,
        suggested_tip_amounts=[10, 50, 100],
    )

    return invoice_link
```

## 7. Handle Pre-Checkout Query

```python
from telegram import PreCheckoutQueryHandler

async def pre_checkout_handler(update, context):
    query = update.pre_checkout_query

    # Validate plan
    if query.invoice_payload.startswith("subscribe_"):
        plan_key = query.invoice_payload.replace("subscribe_", "")

        from bot.billing.plans import get_plan
        plan = get_plan(plan_key)

        if not plan or plan_key not in ["basic", "starter", "pro", "unlimited"]:
            await query.answer(ok=False, error_message="Invalid plan")
            return

        # Check if already on this plan
        from bot.billing.billing_helpers import get_owner_plan
        current_plan = await get_owner_plan(context.bot_data.get("db_pool"), query.from_user.id)

        if current_plan == plan_key:
            await query.answer(ok=False, error_message="You already have this plan")
            return

        # All good, proceed
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Invalid payment")

application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
```

## 8. Handle Successful Payment

```python
from telegram import MessageHandler, filters

async def successful_payment_handler(update, context):
    payment = update.message.successful_payment
    user_id = update.effective_user.id

    # Parse payload
    if payment.invoice_payload.startswith("subscribe_"):
        plan_key = payment.invoice_payload.replace("subscribe_", "")
        charge_id = f"stars_{user_id}_{payment.telegram_payment_charge_id}"

        # Create subscription
        from bot.billing.subscriptions import create_subscription
        result = await create_subscription(
            db_pool=context.bot_data.get("db_pool"),
            owner_id=user_id,
            plan_key=plan_key,
            charge_id=charge_id,
            stars_paid=payment.total_amount
        )

        # Send confirmation
        if result.get("ok"):
            await update.message.reply_text(
                f"✅ Payment successful!\n\n"
                f"You're now on {plan_key.upper()} plan.\n"
                f"Expires: {result['expires_at'][:10]}"
            )

application.add_handler(MessageHandler(successful_payment_handler, filters.SUCCESSFUL_PAYMENT))
```

## 9. Check Property Usage for Owner

```python
from bot.billing.billing_helpers import check_owner_total_properties

within_limit, prop_count, error_msg = await check_owner_total_properties(
    db_pool=db.pool,
    owner_id=owner_id
)

print(f"Owner has {prop_count} properties")
print(f"Within limit: {within_limit}")

if not within_limit:
    print(f"Error: {error_msg}")
```

## 10. Check if Owner Can Add Clone Bot

```python
from bot.billing.billing_helpers import can_owner_add_clone_bot

can_add, error_msg = await can_owner_add_clone_bot(
    db_pool=db.pool,
    owner_id=owner_id
)

if not can_add:
    print(f"Cannot add clone: {error_msg}")
else:
    print("Can add more clone bots")
```

## 11. Cancel Subscription

```python
from bot.billing.subscriptions import cancel_subscription

result = await cancel_subscription(db.pool, owner_id)

if result.get("ok"):
    await bot.send_message(
        chat_id=owner_id,
        text="✅ Subscription cancelled. Your plan will remain active until expiry."
    )
```

## 12. Get All Available Plans

```python
from bot.billing.plans import get_plans_for_display

plans = get_plans_for_display()

for plan in plans:
    print(f"{plan['name']}: {plan['price_display']}")
    print(f"  Clones: {plan['clone_bots']}")
    print(f"  Total properties: {plan['total_properties']}")
```

## 13. Mini App: Display Plan Cards

```javascript
async function renderPlanCards() {
    const response = await apiFetch('/api/billing/plans');
    const plans = response.plans;

    const container = document.getElementById('plans-container');
    container.innerHTML = plans.map(plan => `
        <div class="plan-card ${plan.key === currentPlan ? 'current' : ''}">
            <h3>${plan.name}</h3>
            <p class="price">${plan.price_display}/month</p>
            <div class="stats">
                <span>${plan.clone_bots} bots</span>
                <span>·</span>
                <span>${plan.total_properties} properties</span>
            </div>
            <ul>
                ${plan.features.slice(0, 4).map(f => `<li>${f}</li>`).join('')}
            </ul>
            ${plan.key !== 'free' ? `
                <button onclick="subscribeToPlan('${plan.key}')">
                    Upgrade
                </button>
            ` : `
                <button disabled class="disabled">
                    Current Plan ✓
                </button>
            `}
        </div>
    `).join('');
}
```

## 14. Mini App: Subscribe to Plan

```javascript
async function subscribeToPlan(planKey) {
    const response = await apiFetch('/api/billing/subscribe', {
        method: 'POST',
        body: JSON.stringify({ plan: planKey })
    });

    if (response.ok && response.invoice_url) {
        // Open Telegram Stars payment
        Telegram.WebApp.openInvoiceLink(response.invoice_url);
    } else {
        alert(response.error || 'Failed to create payment invoice');
    }
}
```

## 15. Mini App: Display Owner Info

```javascript
async function loadOwnerInfo() {
    const info = await apiFetch('/api/billing/owner-info');

    // Display plan
    document.getElementById('plan-name').textContent = info.plan_name;

    // Display clone usage
    document.getElementById('clones-used').textContent = info.clone_bots_used;
    document.getElementById('clones-allowed').textContent = info.clone_bots_allowed;

    // Display property usage
    document.getElementById('props-used').textContent = info.total_properties_used;
    document.getElementById('props-allowed').textContent = info.total_properties_allowed;

    // Display active trials
    if (info.active_trials && info.active_trials.length > 0) {
        document.getElementById('trials').innerHTML = info.active_trials.map(trial => `
            <div class="trial-card">
                <h4>@${trial.username}</h4>
                <p>Expires: ${new Date(trial.trial_ends_at).toLocaleDateString()}</p>
            </div>
        `).join('');
    }
}
```

## 16. Mini App: Show Trial Status Banner

```javascript
function renderTrialBanner(bot) {
    if (bot.plan === 'trial') {
        const daysRemaining = getDaysRemaining(bot.trial_ends_at);
        const progress = (15 - daysRemaining) / 15 * 100;

        return `
            <div class="trial-banner trial-active">
                <p>🕐 Trial active — ${daysRemaining} days remaining</p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progress}%"></div>
                </div>
                <p>Expires: ${new Date(bot.trial_ends_at).toLocaleDateString()}</p>
            </div>
        `;
    } else if (bot.plan === 'trial_expired') {
        return `
            <div class="trial-banner trial-expired">
                <p>⛔ Trial expired — bot is INACTIVE</p>
                <div class="actions">
                    <button onclick="upgradeBot(${bot.bot_id})">
                        ⬆️ Upgrade to Reactivate
                    </button>
                    <button onclick="deleteBot(${bot.bot_id})">
                        🗑️ Delete Bot
                    </button>
                </div>
            </div>
        `;
    }
    return '';
}

function getDaysRemaining(expiresAt) {
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diff = expiry - now;
    return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}
```

## 17. Database: Count Bot Properties

```python
async def count_bot_properties(db_pool, bot_id):
    """Count all properties (groups + channels) for a bot."""
    async with db_pool.acquire() as conn:
        token_hash = await conn.fetchval(
            "SELECT token_hash FROM bots WHERE bot_id = $1",
            bot_id
        )

        count = await conn.fetchval(
            "SELECT COUNT(*) FROM groups WHERE bot_token_hash = $1",
            token_hash
        )

    return count
```

## 18. Database: Get Owner's Active Trials

```python
async def get_owner_trials(db_pool, owner_id):
    """Get all active trial bots for owner."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                bot_id,
                username,
                display_name,
                trial_ends_at,
                plan
            FROM bots
            WHERE owner_user_id = $1
              AND plan = 'trial'
              AND trial_ends_at > NOW()
            ORDER BY trial_ends_at ASC
        """, owner_id)

    return [dict(row) for row in rows]
```

## 19. Scheduler: Check Expired Trials

```python
from bot.billing.subscriptions import check_trial_expiration

async def trial_expiry_task():
    """Run every hour to check for expired trials."""
    while True:
        try:
            expired_count = await check_trial_expiration(db.pool)
            if expired_count > 0:
                print(f"Expired {expired_count} trials")
        except Exception as e:
            print(f"Trial expiry check failed: {e}")

        # Sleep for 1 hour
        await asyncio.sleep(3600)

# Start in main.py
# asyncio.create_task(trial_expiry_task())
```

## 20. Scheduler: Send Trial Reminders

```python
from bot.billing.trial_reminders import check_and_send_reminders

async def trial_reminder_task():
    """Run every 6 hours to send reminders."""
    while True:
        try:
            await check_and_send_reminders(db.pool, primary_bot)
        except Exception as e:
            print(f"Trial reminder check failed: {e}")

        # Sleep for 6 hours
        await asyncio.sleep(21600)

# Start in main.py
# asyncio.create_task(trial_reminder_task())
```

## 21. Migration: Backfill Existing Bots

```sql
-- Add plan columns if not exist
ALTER TABLE bots ADD COLUMN IF NOT EXISTS plan VARCHAR DEFAULT 'free';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMPTZ;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS trial_used BOOLEAN DEFAULT FALSE;

-- Backfill primary bots
UPDATE bots
SET plan = 'primary', trial_used = TRUE
WHERE is_primary = TRUE AND plan IS NULL;

-- Backfill existing clone bots (they're on free tier)
UPDATE bots
SET plan = 'free', trial_used = TRUE
WHERE is_primary = FALSE AND plan IS NULL;
```

## 22. API: Create Subscription Webhook Handler

```python
@router.post("/webhook/payment")
async def payment_webhook(request: Request):
    """Handle payment webhook from Telegram."""
    from telegram import Update

    data = await request.json()
    update = Update.de_json(data, bot=request.app.state.bot)

    # Process pre-checkout query
    if update.pre_checkout_query:
        # TODO: Implement pre-checkout handler
        pass

    # Process successful payment
    if update.message and update.message.successful_payment:
        # TODO: Implement payment handler
        pass

    return {"ok": True}
```

## 23. Test: Create Test Payment

```python
async def test_payment():
    """Create a test payment invoice."""
    from bot.billing.plans import get_plan
    from telegram import LabeledPrice

    plan = get_plan("basic")

    invoice_link = await bot.create_invoice_link(
        title=f"TEST: {plan['name']} Plan",
        description=f"Test payment for {plan['name']} plan",
        payload=f"test_subscribe_basic",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(plan['price_display'], plan['price_stars'])],
    )

    print(f"Test invoice: {invoice_link}")
```

## 24. Helper: Get Bot's Effective Limit

```python
from bot.billing.billing_helpers import get_bot_property_limit

async def get_bot_effective_limit(db_pool, bot_id):
    """Get the actual property limit for a bot."""
    limit = await get_bot_property_limit(db_pool, bot_id)

    if limit == 0:
        return "Unlimited"
    else:
        return limit

# Usage:
# limit = await get_bot_effective_limit(db.pool, bot_id)
# print(f"This bot can have up to {limit} properties")
```

## 25. Error Handling: Insufficient Stars

```python
async def pre_checkout_handler(update, context):
    query = update.pre_checkout_query

    # Check if user has enough Stars (Telegram handles this automatically)
    # But you can provide a custom message

    plan_key = query.invoice_payload.replace("subscribe_", "")
    from bot.billing.plans import get_plan
    plan = get_plan(plan_key)

    # Get user's current Stars balance (requires API call to Telegram)
    # For now, let Telegram handle insufficient funds

    if plan:
        await query.answer(
            ok=True,
            error_message=f"Confirm payment of {plan['price_stars']} Stars?"
        )
    else:
        await query.answer(
            ok=False,
            error_message="Invalid plan selected"
        )
```

These examples cover all major billing operations. Use them as templates for your implementation!
