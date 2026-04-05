#!/usr/bin/env python3
"""
Script to diagnose and fix inactive Telegram bot webhooks.
Run this to check which bot has an inactive webhook and fix it.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from db.client import db
from db.ops.bots import get_bot_by_id, get_bots_by_owner, update_bot_status
from bot.utils.crypto import decrypt_token, hash_token
from config import settings
import httpx


async def check_webhook_status():
    """Check webhook status for all bots and identify inactive ones."""
    print("=" * 70)
    print("TELEGRAM BOT WEBHOOK DIAGNOSTIC")
    print("=" * 70)
    print()

    await db.connect()

    try:
        # Get all bots from database
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM bots ORDER BY is_primary DESC")
            bots = [dict(r) for r in rows]

        if not bots:
            print("❌ No bots found in database.")
            return

        print(f"Found {len(bots)} bot(s):\n")

        active_count = 0
        inactive_bots = []

        for i, bot in enumerate(bots, 1):
            bot_type = "PRIMARY" if bot.get("is_primary") else "CLONE"
            status = bot.get("status", "unknown")
            webhook_active = bot.get("webhook_active", False)
            webhook_url = bot.get("webhook_url", "N/A")
            death_reason = bot.get("death_reason", "")

            status_icon = "🟢" if webhook_active else "🔴"
            print(f"[{i}] {bot_type}: @{bot.get('username', bot.get('bot_id'))}")
            print(f"    Status: {status}")
            print(f"    Webhook: {status_icon} {'Active' if webhook_active else 'INACTIVE'}")
            print(f"    URL: {webhook_url[:60]}...")
            if death_reason:
                print(f"    Death Reason: {death_reason}")

            # Check live webhook info from Telegram
            print(f"    Checking Telegram API...")
            try:
                token = decrypt_token(bot["token_encrypted"])
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"https://api.telegram.org/bot{token}/getWebhookInfo"
                    )
                    wh_info = resp.json().get("result", {})

                    telegram_url = wh_info.get("url", "")
                    pending = wh_info.get("pending_update_count", 0)
                    last_error = wh_info.get("last_error_message", "")

                    if telegram_url:
                        print(f"    ✓ Telegram webhook URL: {telegram_url[:60]}...")
                    else:
                        print(f"    ✗ No webhook registered in Telegram!")

                    if pending > 0:
                        print(f"    ⚠️  Pending updates: {pending}")

                    if last_error:
                        print(f"    ⚠️  Last error: {last_error[:100]}")

                    # Compare DB vs Telegram
                    if webhook_active and not telegram_url:
                        print(f"    ❌ MISMATCH: DB says active, Telegram has no webhook")
                        inactive_bots.append(bot)
                    elif not webhook_active and telegram_url:
                        print(f"    ⚠️  MISMATCH: DB says inactive, Telegram has webhook")

                if webhook_active:
                    active_count += 1
                else:
                    inactive_bots.append(bot)

            except Exception as e:
                print(f"    ❌ Error checking Telegram: {e}")
                if not webhook_active:
                    inactive_bots.append(bot)

            print()

        print("=" * 70)
        print(f"Summary: {active_count}/{len(bots)} webhooks active")
        print("=" * 70)
        print()

        if inactive_bots:
            print(f"⚠️  Found {len(inactive_bots)} bot(s) with inactive webhooks:\n")

            for bot in inactive_bots:
                print(f"  • @{bot.get('username', bot.get('bot_id'))}")
                print(f"    Status: {bot.get('status')}")
                if bot.get("death_reason"):
                    print(f"    Reason: {bot['death_reason']}")
                print()

            print("Would you like to fix these webhooks? (y/n): ", end="", flush=True)

            try:
                # Only prompt in interactive mode
                if sys.stdin.isatty():
                    response = input().strip().lower()
                    if response == "y":
                        await fix_inactive_webhooks(inactive_bots)
                else:
                    print("Run this script interactively to fix the webhooks.")
                    print("\nOr call fix_inactive_webhooks() directly in the code.")
            except EOFError:
                print("\nRun this script interactively to fix the webhooks.")
        else:
            print("✅ All webhooks are active!")

    finally:
        await db.close()


async def fix_inactive_webhooks(bots):
    """Attempt to fix inactive webhooks for the given bots."""
    print("\n" + "=" * 70)
    print("ATTEMPTING TO FIX WEBHOOKS")
    print("=" * 70)
    print()

    render_url = settings.RENDER_EXTERNAL_URL

    for bot in bots:
        bot_id = bot["bot_id"]
        username = bot.get("username", str(bot_id))
        print(f"🔧 Fixing @{username}...")

        try:
            # Get token and re-register webhook
            token = decrypt_token(bot["token_encrypted"])
            token_hash = hash_token(token)
            webhook_secret = token_hash[:32]
            webhook_url = f"{render_url}/webhook/{webhook_secret}"

            print(f"    Setting webhook to: {webhook_url[:60]}...")

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/setWebhook",
                    json={
                        "url": webhook_url,
                        "allowed_updates": [
                            "message",
                            "callback_query",
                            "chat_member",
                            "my_chat_member",
                            "inline_query",
                        ],
                        "drop_pending_updates": True,
                    },
                )
                result = resp.json()

                if result.get("ok"):
                    print(f"    ✅ Webhook registered successfully!")
                    # Update database
                    await update_bot_status(
                        db.pool, bot_id, bot.get("status", "active"), webhook_active=True
                    )
                    # Clear death reason
                    await db.pool.execute(
                        "UPDATE bots SET death_reason = NULL WHERE bot_id = $1", bot_id
                    )
                else:
                    error = result.get("description", "Unknown error")
                    print(f"    ❌ Failed: {error}")
                    # Log the error
                    await db.pool.execute(
                        "UPDATE bots SET death_reason = $1 WHERE bot_id = $2",
                        f"Webhook fix failed: {error}",
                        bot_id,
                    )

        except Exception as e:
            print(f"    ❌ Error: {e}")
            # Update death reason
            await db.pool.execute(
                "UPDATE bots SET death_reason = $1 WHERE bot_id = $2",
                f"Webhook fix error: {str(e)}",
                bot_id,
            )

        print()

    print("=" * 70)
    print("✨ Done! Run this script again to verify the fixes.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(check_webhook_status())
