# Webhook Bot ID Fix

## Problem
The bot was receiving webhook updates for `bot_id=0`, indicating the bot initialization was failing and returning an invalid bot ID. The logs showed:
```
%Y-%m-%d %H:%M:%S [WARNING] main | [WEBHOOK] Update for unregistered bot | bot_id=0 | registered_bots=[]
```

## Root Causes
1. **Race Condition**: The code was calling `get_me()` immediately after `initialize()` and `start()`, without giving the bot time to fully connect to Telegram servers
2. **Missing Validation**: No validation was performed to ensure `get_me()` returned a valid bot object with a non-zero ID
3. **Poor Error Messages**: When initialization failed, the error messages were not descriptive enough to diagnose the issue
4. **Invalid Token Detection**: No validation of the token format before attempting to use it

## Changes Made

### 1. Token Format Validation (main.py lines 73-80)
Added regex validation to ensure the bot token follows the correct format before attempting to initialize the bot:
```python
token_pattern = r'^\d{8,10}:[\w-]{35}$'
if not re.match(token_pattern, primary_token):
    logger.error("[STARTUP] ❌ Invalid PRIMARY_BOT_TOKEN format...")
    raise ValueError("Invalid bot token format...")
```

This catches invalid tokens early and provides a clear error message.

### 2. Improved Bot Initialization (main.py lines 82-117)
- Added detailed logging at each step
- Added a brief sleep (0.5s) after starting the bot to ensure it's fully ready
- Try async `get_me()` first (PTB 20+), fall back to sync method if not available
- Explicit validation that `get_me()` returns a valid bot object with a non-zero ID

```python
# Brief pause to ensure bot is fully ready
await asyncio.sleep(0.5)

# Verify bot is properly initialized
try:
    primary_me = await primary_app.bot.get_me()
except AttributeError:
    primary_me = primary_app.bot.get_me()

if not primary_me or primary_me.id == 0:
    raise ValueError(
        f"Bot initialization failed: get_me() returned invalid bot object..."
    )
```

### 3. Clone Bot Recovery Improvements (main.py lines 169-182)
- Added verification that the bot ID from `get_me()` matches what's in the database
- Added brief sleep after initializing clone bots
- Better error messages for debugging

```python
# Brief pause to ensure bot is fully ready
await asyncio.sleep(0.3)

# Verify bot ID matches what's in the database
try:
    clone_me = await clone_app.bot.get_me()
except AttributeError:
    clone_me = clone_app.bot.get_me()

if not clone_me or clone_me.id != clone["bot_id"]:
    raise ValueError(
        f"Clone bot ID mismatch: expected {clone['bot_id']}, got..."
    )
```

### 4. Webhook Endpoint Bot ID Validation (main.py lines 269-276)
Added explicit check for `bot_id=0` (invalid) with a detailed error message:

```python
# Validate bot_id - reject obviously invalid IDs like 0
if bot_id == 0:
    logger.error(
        f"[WEBHOOK] Received webhook for invalid bot_id=0. "
        f"This usually means the bot token is invalid or webhook was misconfigured. "
        f"Please check PRIMARY_BOT_TOKEN environment variable and ensure webhook is set correctly."
    )
    return {"ok": True, "note": "invalid_bot_id_zero"}
```

## Expected Behavior After Fix

1. **Startup**: When the bot starts, it will now:
   - Validate the token format before attempting to connect
   - Wait for the bot to fully initialize before calling `get_me()`
   - Verify the bot ID is valid (non-zero) before setting the webhook
   - Log detailed progress information at each step

2. **Error Handling**: If initialization fails, the error message will clearly indicate:
   - Whether the token format is invalid
   - Whether `get_me()` returned an invalid bot object
   - Whether there's a connection issue with Telegram

3. **Webhook**: If an invalid webhook request comes in (bot_id=0), it will log a detailed error message explaining what might be wrong

## Troubleshooting

If you still see `bot_id=0` errors after this fix:

1. Check the startup logs - they should show where the initialization failed
2. Verify your `PRIMARY_BOT_TOKEN` environment variable is correct
3. Ensure the token follows the format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
4. Check that the bot can connect to Telegram (network issues, firewall, etc.)
5. Verify the bot hasn't been deleted or banned by Telegram
