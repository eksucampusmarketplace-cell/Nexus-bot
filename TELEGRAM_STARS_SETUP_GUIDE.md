# Telegram Stars Payment Setup Guide

This guide explains how to integrate Telegram Stars payments with the Nexus Bot billing system.

## Overview

Telegram Stars are an in-app currency that users can purchase through Telegram. Bot developers can accept Stars as payment for:
- Subscriptions (recurring monthly payments)
- One-time purchases (features, upgrades)
- Tips/donations

## Prerequisites

1. **Bot Must Be Verified**
   - Your bot must be verified by Telegram to accept payments
   - Apply for verification via [@BotFather](https://t.me/BotFather)
   - Verification requirements: 100+ users, active for 7+ days

2. **Payment Provider**
   - Telegram Stars use Telegram's built-in payment system
   - No external payment provider needed
   - Stars are stored in user's Telegram account

3. **Test Mode**
   - Use test payments during development
   - Test Stars are different from real Stars
   - You get unlimited test Stars for testing

## Setting Up Payments

### Step 1: Check Bot Payment Status

```bash
# Check with BotFather
/msg @BotFather
# Choose: /payments
```

BotFather will show:
- Whether your bot can accept payments
- Your bot's payment status
- Any requirements you're missing

### Step 2: Generate Payment Invoice

When a user wants to subscribe, create a payment invoice:

```python
from telegram import LabeledPrice, Invoice

async def send_payment_invoice(bot, chat_id, plan_key):
    """Send a payment invoice to user."""
    from bot.billing.plans import get_plan

    plan = get_plan(plan_key)

    # Create payment invoice
    await bot.send_invoice(
        chat_id=chat_id,
        title=f"{plan['name']} Plan",
        description=f"Monthly subscription to {plan['name']} plan",
        payload=f"subscribe_{plan_key}",  # Unique payload
        provider_token="",  # Empty for Stars
        currency="XTR",  # Telegram Stars currency code
        prices=[LabeledPrice(plan['price_display'], plan['price_stars'])],
        start_parameter="billing",  # Deep link parameter
        max_tip_amount=100,  # Optional: allow tips
        suggested_tip_amounts=[10, 50, 100],
        provider_data=None,
        photo_url=None,
        photo_size=None,
        photo_width=None,
        photo_height=None,
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        send_phone_number_to_provider=False,
        send_email_to_provider=False,
        is_flexible=False,
    )
```

### Step 3: Handle Pre-Checkout Query

This confirms payment details before user confirms:

```python
from telegram import PreCheckoutQuery

async def pre_checkout_query(update, context):
    """Handle pre-checkout query (payment confirmation)."""
    query = update.pre_checkout_query

    # Validate payload
    if query.invoice_payload.startswith("subscribe_"):
        plan_key = query.invoice_payload.replace("subscribe_", "")

        # Check if plan is valid
        from bot.billing.plans import get_plan
        plan = get_plan(plan_key)

        if not plan:
            await query.answer(ok=False, error_message="Invalid plan")
            return

        # Answer with OK to proceed
        await query.answer(ok=True)

    else:
        await query.answer(ok=False, error_message="Invalid payment")
```

### Step 4: Handle Successful Payment

After successful payment, update user's subscription:

```python
from telegram import SuccessfulPayment

async def successful_payment(update, context):
    """Handle successful payment."""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    db_pool = context.bot_data.get("db_pool")

    # Parse payload
    if payment.invoice_payload.startswith("subscribe_"):
        plan_key = payment.invoice_payload.replace("subscribe_", "")
        charge_id = f"stars_{user_id}_{payment.telegram_payment_charge_id}"

        # Create subscription
        from bot.billing.subscriptions import create_subscription
        result = await create_subscription(
            db_pool=db_pool,
            owner_id=user_id,
            plan_key=plan_key,
            charge_id=charge_id,
            stars_paid=payment.total_amount
        )

        # Send confirmation
        if result.get("ok"):
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Payment successful!\n\n"
                      f"You're now on the {plan_key.upper()} plan.\n"
                      f"Expires: {result['expires_at'][:10]}"
            )
```

## API Implementation

### Update Subscribe Endpoint

Modify `/api/billing/subscribe` to generate payment invoice:

```python
@router.post("/api/billing/subscribe")
async def subscribe_endpoint(request: Request, req: SubscribeRequest):
    """Subscribe to a paid plan via Telegram Stars."""
    owner_id = request.state.user_id
    db_pool = request.app.state.db
    bot = request.app.state.bot

    # Validate plan
    plan = get_plan(req.plan)
    if not plan or req.plan in ("free", "trial", "primary", "trial_expired"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    # Check if already on this plan
    current_plan = await get_owner_plan(db_pool, owner_id)
    if current_plan == req.plan:
        raise HTTPException(status_code=400, detail="You already have this plan")

    # Generate payment invoice URL
    try:
        invoice_url = await bot.create_invoice_link(
            title=f"{plan['name']} Plan",
            description=f"Monthly subscription to {plan['name']} plan",
            payload=f"subscribe_{req.plan}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(plan['price_display'], plan['price_stars'])],
            max_tip_amount=100,
            suggested_tip_amounts=[10, 50, 100],
        )

        return {
            "ok": True,
            "plan": req.plan,
            "plan_name": plan["name"],
            "price_stars": plan["price_stars"],
            "invoice_url": invoice_url
        }
    except Exception as e:
        logger.error(f"[Billing] Failed to create invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Update Mini App to Use Invoice URL

In the Mini App upgrade modal:

```javascript
async function handlePlanUpgrade(planKey) {
    const response = await apiFetch('/api/billing/subscribe', {
        method: 'POST',
        body: JSON.stringify({ plan: planKey })
    });

    if (response.ok && response.invoice_url) {
        // Open Telegram Stars payment
        Telegram.WebApp.openInvoiceLink(response.invoice_url);
    } else {
        alert('Failed to create payment invoice');
    }
}
```

## Payment Flow Summary

```
1. User clicks "Upgrade" in Mini App
   ↓
2. Mini App calls POST /api/billing/subscribe
   ↓
3. Server generates invoice URL via bot.create_invoice_link()
   ↓
4. Mini App opens invoice via Telegram.WebApp.openInvoiceLink()
   ↓
5. User sees payment UI in Telegram
   ↓
6. User confirms payment → Pre-checkout query sent to bot
   ↓
7. Bot validates and answers pre-checkout query
   ↓
8. User completes payment → Successful payment sent to bot
   ↓
9. Bot handles successful payment, creates subscription
   ↓
10. Bot sends confirmation message
```

## Testing Payments

### Test Mode

1. **Get Test Stars** (from BotFather):
   ```
   /teststars
   ```
   - Gives you unlimited test Stars
   - Can be used to test all payment flows

2. **Use Test Environment**:
   ```python
   # In development, use test mode
   if not settings.PRODUCTION:
       # Test mode automatically uses test Stars
       pass
   ```

### Test Checklist

- [ ] Create invoice for each plan tier
- [ ] Complete test payment process
- [ ] Verify pre-checkout query handler works
- [ ] Verify successful payment handler works
- [ ] Check subscription created in database
- [ ] Verify plan limits updated
- [ ] Test with insufficient Stars
- [ ] Test with expired payment

## Handling Failed Payments

### Pre-Checkout Query Rejection

```python
# In pre_checkout_query handler
if insufficient_funds:
    await query.answer(
        ok=False,
        error_message="Insufficient Stars. Please add Stars to your account."
    )
```

### Payment Expiry

```python
# In successful_payment handler, check for expiry
if payment.total_amount < required_amount:
    await bot.send_message(
        chat_id=user_id,
        text="Payment failed: Insufficient amount."
    )
    return
```

## Refunds

### Processing Refunds

```python
async def refund_payment(db_pool, owner_id, subscription_id):
    """Refund a subscription payment."""
    # Note: Telegram Stars refunds are not directly supported
    # You can only cancel future renewals

    # Cancel auto-renewal
    await cancel_subscription(db_pool, owner_id)

    # Optionally, grant bonus Stars as compensation
    from bot.billing.stars_economy import grant_bonus_stars
    refund_amount = 100  # Partial refund
    await grant_bonus_stars(
        db_pool,
        owner_id,
        refund_amount,
        reason="Refund for cancelled subscription",
        granted_by=0
    )
```

## Webhooks (Optional)

For server-side payment processing:

### Set Up Webhook

```python
from telegram import Update, Bot

bot = Bot(token=settings.BOT_TOKEN)

# Set webhook to receive payment updates
await bot.set_webhook(
    url=f"{settings.WEBHOOK_URL}/webhook",
    allowed_updates=['pre_checkout_query', 'successful_payment']
)
```

### Webhook Handler

```python
@app.post("/webhook/payment")
async def payment_webhook(request: Request):
    """Handle payment webhook from Telegram."""
    data = await request.json()

    update = Update.de_json(data, bot=app_bot)

    # Process pre-checkout query
    if update.pre_checkout_query:
        await pre_checkout_query(update, context)

    # Process successful payment
    if update.message and update.message.successful_payment:
        await successful_payment(update, context)

    return {"ok": True}
```

## Subscription Management

### Check Expiry

Run periodically (e.g., daily):

```python
async def check_subscriptions():
    """Check and expire old subscriptions."""
    async with db_pool.acquire() as conn:
        # Get expired subscriptions
        expired = await conn.fetch("""
            UPDATE billing_subscriptions
            SET auto_renew = FALSE
            WHERE plan_expires_at < NOW()
              AND auto_renew = TRUE
            RETURNING owner_id, plan
        """)

        for sub in expired:
            # Notify user
            await bot.send_message(
                chat_id=sub["owner_id"],
                text=f"⚠️ Your {sub['plan']} subscription has expired.\n"
                      f"Upgrade to continue using premium features."
            )

            # Downgrade to free
            await downgrade_to_free(db_pool, sub["owner_id"])
```

### Auto-Renewal

Note: Telegram Stars do not support automatic recurring payments. You must:

1. Send reminder 3 days before expiry
2. User manually renews via invoice
3. Create new subscription record

```python
async def send_renewal_reminder(db_pool, owner_id, expires_at):
    """Send renewal reminder before expiry."""
    from bot.billing.plans import get_plan

    plan_key = await get_owner_plan(db_pool, owner_id)
    plan = get_plan(plan_key)

    await bot.send_message(
        chat_id=owner_id,
        text=f"⏰ Your {plan['name']} subscription expires on {expires_at.date()}.\n\n"
              f"Renew now to keep your benefits:\n"
              f"Price: {plan['price_display']}/month",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Renew", callback_data=f"renew_{plan_key}")
        ]])
    )
```

## Security Considerations

### 1. Validate Payloads

Always validate payment payload to prevent tampering:

```python
# In successful_payment handler
expected_payloads = [f"subscribe_{p}" for p in PLANS.keys()]

if payment.invoice_payload not in expected_payloads:
    logger.warning(f"Invalid payload: {payment.invoice_payload}")
    return
```

### 2. Check Duplicate Payments

Prevent duplicate subscription creation:

```python
# Create unique charge_id
charge_id = f"stars_{user_id}_{payment.telegram_payment_charge_id}_{int(time.time())}"

# Use ON CONFLICT in database to prevent duplicates
await db.execute("""
    INSERT INTO billing_subscriptions (owner_id, plan, telegram_charge_id, ...)
    VALUES ($1, $2, $3, ...)
    ON CONFLICT (telegram_charge_id) DO NOTHING
""", ...)
```

### 3. Verify Payment Amount

Ensure correct amount was paid:

```python
plan = get_plan(plan_key)
if payment.total_amount != plan['price_stars']:
    logger.error(f"Amount mismatch: expected {plan['price_stars']}, got {payment.total_amount}")
    return
```

## Troubleshooting

### Bot Cannot Accept Payments

**Symptom**: "Bot cannot accept payments"

**Solution**:
1. Check with @BotFather: `/payments`
2. Ensure bot has 100+ users
3. Ensure bot is active for 7+ days
4. Apply for verification if needed

### Payment Fails

**Symptom**: "Payment failed" or "Insufficient funds"

**Solution**:
1. Check user has enough Stars in their account
2. Verify invoice amount is correct
3. Check network connectivity

### Pre-Checkout Query Not Received

**Symptom**: User confirms payment but no pre-checkout query

**Solution**:
1. Ensure webhook or polling is active
2. Check bot is receiving updates
3. Verify handler is registered in Application

### Subscription Not Created

**Symptom**: Payment successful but subscription not in database

**Solution**:
1. Check database connection
2. Verify successful_payment handler runs
3. Check logs for errors
4. Verify ON CONFLICT doesn't silently fail

## Additional Resources

- [Telegram Stars Documentation](https://core.telegram.org/bots/payments#stars)
- [BotFather Commands](https://core.telegram.org/bots#botfather)
- [Python Telegram Bot Library Docs](https://docs.python-telegram-bot.org/)
- [Telegram API: Payments](https://core.telegram.org/bots/payments)

## Next Steps

1. **Verify bot** with @BotFather
2. **Get test Stars** for development
3. **Implement payment handlers** (pre-checkout, successful payment)
4. **Update API endpoint** to generate invoice links
5. **Update Mini App** to open invoice links
6. **Test full flow** with test Stars
7. **Deploy to production**
8. **Monitor payments** and handle issues

## Example Complete Flow

```python
# 1. Handler registration
application.add_handler(CallbackQueryHandler(plan_upgrade_handler, pattern="^upgrade_"))
application.add_handler(PreCheckoutQueryHandler(pre_checkout_query))
application.add_handler(MessageHandler(successful_payment, filters.SUCCESSFUL_PAYMENT))

# 2. Mini App button
<button onclick="upgradeToPlan('starter')">
    Upgrade to Starter (700 ⭐/mo)
</button>

# 3. API call
async function upgradeToPlan(plan) {
    const res = await fetch('/api/billing/subscribe', { ... });
    Telegram.WebApp.openInvoiceLink(res.invoice_url);
}

# 4. Backend generates invoice
invoice_url = await bot.create_invoice_link(...)

# 5. User pays
# (Telegram handles this automatically)

# 6. Bot handles payment
async def successful_payment(update, context):
    # Create subscription in DB
    await create_subscription(...)

    # Send confirmation
    await bot.send_message(..., "✅ Subscribed!")
```

This completes the Telegram Stars payment setup guide!
