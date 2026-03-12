"""
bot/handlers/clone.py

Conversational bot cloning — runs ONLY on the primary Nexus Bot.
Clone bots never see these handlers (controlled in factory.py).

CONVERSATION STATES:
  idle                → user sends /clone
  WAITING_FOR_TOKEN   → user pastes token
  AWAITING_CONFIRM    → user taps Confirm or Cancel

SECURITY LAYERS (applied in this exact order):
  1. CLONE_ACCESS check (owner_only vs open)
  2. Rate limit (5 attempts per hour per user)
  3. Token format validation (regex, no API call)
  4. Deduplication (token_hash lookup in DB)
  5. Live Telegram API validation (getMe)
  6. Confirmation step (user must explicitly confirm)

LOGGING REQUIREMENTS:
  Every step logs: [CLONE] step_name | user_id={id} | result={ok/fail} | reason={...}
  Never log raw tokens — always mask_token() or hash_token()

AUTH NOTE:
  initData in the Mini App is always validated against PRIMARY bot token.
  Clone bots are never used for auth. This is enforced in api/auth.py.
"""

import re
import asyncio
import logging
import httpx
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.registry import register as registry_register, deregister as registry_deregister
from bot.factory import create_application
from bot.utils.crypto import encrypt_token, hash_token, mask_token, validate_token_format, decrypt_token
from db.ops.bots import (
    get_bot_by_id, get_bot_by_token_hash,
    get_bots_by_owner, insert_bot,
    update_bot_status, delete_bot,
    count_recent_clone_attempts, log_clone_attempt
)
from config import settings

logger = logging.getLogger(__name__)

CLONE_RATE_LIMIT = 5
WEBHOOK_RETRY_COUNT = 3
WEBHOOK_RETRY_DELAY = 5


# ─── /clone ───────────────────────────────────────────────────────────────────

async def clone_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"[CLONE] /clone initiated | user_id={user.id} username=@{user.username}")

    # Access control
    if settings.CLONE_ACCESS == "owner_only" and user.id != settings.OWNER_ID:
        logger.warning(f"[CLONE] Access denied | user_id={user.id} | reason=not_owner")
        await update.message.reply_text("⛔ Cloning is restricted to the bot owner.")
        return

    context.user_data["clone_state"] = "WAITING_FOR_TOKEN"
    logger.debug(f"[CLONE] State set to WAITING_FOR_TOKEN | user_id={user.id}")

    await update.message.reply_text(
        "🔁 *Clone Nexus Bot*\n\n"
        "To create a clone:\n\n"
        "1\\. Open @BotFather\n"
        "2\\. Send `/newbot` and finish setup\n"
        "3\\. Copy the token BotFather gives you\n"
        "4\\. Paste it here\n\n"
        "_Your new bot keeps its own name, username and photo\\._\n\n"
        "⚠️ Only paste tokens for bots *you own*\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel")
        ]])
    )


# ─── Token input ──────────────────────────────────────────────────────────────

async def token_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    token = update.message.text.strip()

    logger.info(
        f"[CLONE] Token received | user_id={user.id} | "
        f"masked={mask_token(token)} | "
        f"state={context.user_data.get('clone_state', 'none')}"
    )

    if context.user_data.get("clone_state") != "WAITING_FOR_TOKEN":
        logger.debug(f"[CLONE] Token ignored — not in WAITING_FOR_TOKEN state | user_id={user.id}")
        return

    # Clear state immediately — prevent double processing
    context.user_data.pop("clone_state", None)

    processing = await update.message.reply_text("🔍 Checking token\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
    db_pool = context.bot_data["db_pool"]

    # ── Layer 1: Rate limit ────────────────────────────────────────────────
    attempts = await count_recent_clone_attempts(db_pool, user.id, window_minutes=60)
    logger.debug(f"[CLONE] Rate limit check | user_id={user.id} | attempts_last_hour={attempts}")

    if attempts >= CLONE_RATE_LIMIT:
        await log_clone_attempt(db_pool, user.id, False, "rate_limited")
        logger.warning(f"[CLONE] Rate limited | user_id={user.id} | attempts={attempts}")
        await processing.edit_text(
            f"⏱ Too many attempts\\. Max {CLONE_RATE_LIMIT} per hour\\. Try again later\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    # ── Layer 2: Format check ──────────────────────────────────────────────
    if not validate_token_format(token):
        await log_clone_attempt(db_pool, user.id, False, "invalid_format")
        logger.warning(f"[CLONE] Invalid format | user_id={user.id} | masked={mask_token(token)}")
        await processing.edit_text(
            "❌ Invalid token format\\.\n\n"
            "It should look like: `1234567890:ABCdef\\.\\.\\.`\n\n"
            "Send /clone to try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    # ── Layer 3: Deduplication ─────────────────────────────────────────────
    token_hash = hash_token(token)
    logger.debug(f"[CLONE] Dedup check | token_hash={token_hash[:12]}...")

    existing = await get_bot_by_token_hash(db_pool, token_hash)
    if existing:
        reason = "already_registered_dead" if existing["status"] == "dead" else "already_registered"
        await log_clone_attempt(db_pool, user.id, False, reason, token_hash)
        logger.info(f"[CLONE] Duplicate token | user_id={user.id} | existing_bot=@{existing['username']} | status={existing['status']}")

        if existing["status"] == "dead":
            await processing.edit_text(
                f"⚠️ @{existing['username']} is already registered but its token was revoked\\.\n\n"
                f"Send /myclones and use *Re\\-authenticate* to fix it\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await processing.edit_text(
                f"⚠️ This token belongs to @{existing['username']} which is already a registered clone\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        return

    # ── Layer 4: Live Telegram validation ──────────────────────────────────
    await processing.edit_text("🔍 Verifying with Telegram\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
    logger.info(f"[CLONE] Calling getMe | masked={mask_token(token)}")

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            tg_data = resp.json()
    except httpx.TimeoutException:
        await log_clone_attempt(db_pool, user.id, False, "telegram_timeout", token_hash)
        logger.error(f"[CLONE] getMe timed out | user_id={user.id} | masked={mask_token(token)}")
        await processing.edit_text(
            "⏱ Telegram didn't respond\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    except Exception as e:
        await log_clone_attempt(db_pool, user.id, False, f"network_error: {e}", token_hash)
        logger.error(f"[CLONE] getMe network error | user_id={user.id} | error={e}")
        await processing.edit_text("❌ Network error\\. Please try again\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if not tg_data.get("ok"):
        err_desc = tg_data.get("description", "Unknown error")
        await log_clone_attempt(db_pool, user.id, False, f"telegram_rejected: {err_desc}", token_hash)
        logger.warning(f"[CLONE] Token rejected by Telegram | user_id={user.id} | reason={err_desc}")
        await processing.edit_text(
            f"❌ Telegram rejected this token:\n_{err_desc}_\n\nSend /clone to try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    bot_info = tg_data["result"]
    cloned_bot_id   = bot_info["id"]
    cloned_username = bot_info["username"]
    cloned_name     = bot_info["first_name"]

    logger.info(
        f"[CLONE] Token valid | "
        f"cloned_bot_id={cloned_bot_id} | "
        f"username=@{cloned_username} | "
        f"display_name={cloned_name} | "
        f"owner_user_id={user.id}"
    )

    # Store pending data for confirmation step
    context.user_data["pending_clone"] = {
        "token":        token,
        "token_hash":   token_hash,
        "bot_id":       cloned_bot_id,
        "username":     cloned_username,
        "display_name": cloned_name,
    }

    await processing.edit_text(
        f"✅ *Token verified\\!*\n\n"
        f"🤖 @{cloned_username}\n"
        f"📛 {cloned_name}\n"
        f"🆔 `{cloned_bot_id}`\n\n"
        f"Confirm to register this bot as a Nexus clone?",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirm", callback_data=f"clone:confirm:{cloned_bot_id}"),
            InlineKeyboardButton("❌ Cancel",  callback_data="clone:cancel")
        ]])
    )


# ─── Callbacks ────────────────────────────────────────────────────────────────

async def clone_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user  = update.effective_user
    parts = query.data.split(":")
    action = parts[1]

    logger.info(f"[CLONE] Callback | user_id={user.id} | action={action} | data={query.data}")

    db_pool = context.bot_data["db_pool"]

    # ── cancel ────────────────────────────────────────────────────────────
    if action == "cancel":
        context.user_data.pop("pending_clone", None)
        context.user_data.pop("clone_state", None)
        logger.info(f"[CLONE] Cancelled | user_id={user.id}")
        await query.edit_message_text("❎ Clone cancelled\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    # ── new (from myclones add button) ────────────────────────────────────
    if action == "new":
        context.user_data["clone_state"] = "WAITING_FOR_TOKEN"
        await query.edit_message_text(
            "Paste your new bot token from @BotFather:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel")
            ]])
        )
        return

    # ── confirm ───────────────────────────────────────────────────────────
    if action == "confirm":
        pending = context.user_data.pop("pending_clone", None)
        confirm_bot_id = int(parts[2])

        if not pending:
            logger.warning(f"[CLONE] Confirm with no pending data | user_id={user.id}")
            await query.edit_message_text("❌ Session expired\\. Send /clone to try again\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        if pending["bot_id"] != confirm_bot_id:
            logger.error(f"[CLONE] bot_id mismatch | expected={pending['bot_id']} | got={confirm_bot_id}")
            await query.edit_message_text("❌ Confirmation mismatch\\. Send /clone to try again\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        await query.edit_message_text(
            f"⚙️ Registering @{pending['username']}\\.\\.\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

        try:
            await _complete_clone_registration(
                db_pool=db_pool,
                pending=pending,
                owner_user_id=user.id,
                edit_message=query.message
            )
            await log_clone_attempt(db_pool, user.id, True, None, pending["token_hash"])
        except Exception as e:
            await log_clone_attempt(db_pool, user.id, False, str(e), pending.get("token_hash"))
            logger.error(f"[CLONE] Registration failed | user_id={user.id} | error={e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Registration failed:\n_{e}_\n\nSend /clone to try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        return

    # ── remove (show confirm prompt) ──────────────────────────────────────
    if action == "remove":
        target_bot_id = int(parts[2])
        bot_record = await get_bot_by_id(db_pool, target_bot_id)

        if not bot_record or bot_record["owner_user_id"] != user.id:
            logger.warning(f"[CLONE] Remove denied | user_id={user.id} | target={target_bot_id}")
            await query.edit_message_text("❌ Bot not found or you don't own it\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        await query.edit_message_text(
            f"⚠️ *Remove @{bot_record['username']}?*\n\n"
            f"This stops the bot, deletes its webhook, and removes all data\\. Cannot be undone\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑️ Yes, remove", callback_data=f"clone:confirm_remove:{target_bot_id}"),
                InlineKeyboardButton("↩️ Keep it",     callback_data="clone:cancel")
            ]])
        )
        return

    # ── confirm_remove ────────────────────────────────────────────────────
    if action == "confirm_remove":
        target_bot_id = int(parts[2])
        bot_record = await get_bot_by_id(db_pool, target_bot_id)

        if not bot_record or bot_record["owner_user_id"] != user.id:
            await query.edit_message_text("❌ Bot not found or you don't own it\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        if bot_record.get("is_primary"):
            logger.warning(f"[CLONE] Attempt to remove primary bot | user_id={user.id}")
            await query.edit_message_text("❌ You cannot remove the primary bot\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        await query.edit_message_text(
            f"🗑️ Removing @{bot_record['username']}\\.\\.\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

        try:
            await _remove_clone(db_pool, target_bot_id, bot_record)
            logger.info(f"[CLONE] Removed | bot_id={target_bot_id} | username=@{bot_record['username']} | by=user_id={user.id}")
            await query.edit_message_text(
                f"✅ @{bot_record['username']} has been removed\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logger.error(f"[CLONE] Removal failed | bot_id={target_bot_id} | error={e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Removal failed: _{e}_",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        return

    # ── reauth (dead bot re-authentication) ───────────────────────────────
    if action == "reauth":
        target_bot_id = int(parts[2])
        context.user_data["clone_state"] = "WAITING_FOR_TOKEN"
        context.user_data["reauth_bot_id"] = target_bot_id
        await query.edit_message_text(
            f"Paste the new token for this bot from @BotFather:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel")
            ]])
        )
        return


# ─── /myclones ────────────────────────────────────────────────────────────────

async def myclones_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_pool = context.bot_data["db_pool"]

    logger.info(f"[CLONE] /myclones | user_id={user.id}")

    clones = await get_bots_by_owner(db_pool, user.id)

    if not clones:
        await update.message.reply_text(
            "You have no clones yet\\.\n\nSend /clone to add your first one\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    text = f"🤖 *Your Bots* \\({len(clones)}\\)\n\n"
    keyboard = []

    for bot in clones:
        status_icon  = "👑" if bot["is_primary"] else ("🟢" if bot["status"] == "active" else "🔴")
        webhook_icon = "🔗" if bot["webhook_active"] else "⚠️"
        label        = " \\(Primary\\)" if bot["is_primary"] else ""

        text += (
            f"{status_icon} *@{bot['username']}*{label}\n"
            f"   📛 {bot['display_name']}\n"
            f"   🆔 `{bot['bot_id']}`\n"
            f"   {webhook_icon} Webhook: {'active' if bot['webhook_active'] else 'inactive'}\n"
            f"   👥 Groups: {bot['groups_count']}\n"
            f"   📅 Added: {bot['added_at'].strftime('%b %d %Y')}\n\n"
        )

        if not bot["is_primary"]:
            row = []
            if bot["status"] == "dead":
                row.append(InlineKeyboardButton("🔄 Re-auth", callback_data=f"clone:reauth:{bot['bot_id']}"))
            row.append(InlineKeyboardButton(f"🗑️ Remove", callback_data=f"clone:remove:{bot['bot_id']}"))
            keyboard.append(row)

    keyboard.append([InlineKeyboardButton("➕ Add new clone", callback_data="clone:new")])

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─── Internal: complete registration ─────────────────────────────────────────

async def _complete_clone_registration(
    db_pool, pending: dict, owner_user_id: int, edit_message
):
    """
    The core 5-step registration sequence.
    Steps MUST run in this exact order.
    If any step fails, raises an exception — caller handles messaging.
    """
    token       = pending["token"]
    bot_id      = pending["bot_id"]
    username    = pending["username"]
    render_url  = settings.RENDER_EXTERNAL_URL
    webhook_url = f"{render_url}/webhook/{bot_id}"

    logger.info(
        f"[CLONE][REGISTER] Starting | "
        f"bot_id={bot_id} | username=@{username} | "
        f"owner={owner_user_id} | webhook={webhook_url}"
    )

    # Step 1: Clear any pre-existing webhook
    logger.debug(f"[CLONE][REGISTER] Step 1: Clearing existing webhook | bot_id={bot_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        clear_resp = await client.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook",
            json={"drop_pending_updates": True}
        )
        logger.debug(f"[CLONE][REGISTER] deleteWebhook response: {clear_resp.json()}")

    # Step 2: Save to DB (before webhook — allows retry if webhook step fails)
    logger.debug(f"[CLONE][REGISTER] Step 2: Inserting DB record | bot_id={bot_id}")
    await insert_bot(db_pool, {
        "bot_id":          bot_id,
        "username":        username,
        "display_name":    pending["display_name"],
        "token_encrypted": encrypt_token(token),
        "token_hash":      pending["token_hash"],
        "owner_user_id":   owner_user_id,
        "webhook_url":     webhook_url,
        "is_primary":      False,
        "status":          "active",
        "webhook_active":  False,
    })
    logger.info(f"[CLONE][REGISTER] DB record inserted | bot_id={bot_id}")

    # Step 3: Register webhook with retries
    logger.debug(f"[CLONE][REGISTER] Step 3: Setting webhook | bot_id={bot_id} | url={webhook_url}")
    webhook_ok = False

    for attempt in range(1, WEBHOOK_RETRY_COUNT + 1):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                wh_resp = await client.post(
                    f"https://api.telegram.org/bot{token}/setWebhook",
                    json={
                        "url":             webhook_url,
                        "allowed_updates": ["message","callback_query","chat_member","new_chat_members"],
                        "drop_pending_updates": True
                    }
                )
                wh_data = wh_resp.json()

            logger.debug(f"[CLONE][REGISTER] setWebhook attempt {attempt} | response={wh_data}")

            if wh_data.get("ok"):
                webhook_ok = True
                logger.info(f"[CLONE][REGISTER] Webhook confirmed | bot_id={bot_id} | attempt={attempt}")
                break
            else:
                logger.warning(
                    f"[CLONE][REGISTER] setWebhook failed attempt {attempt}/{WEBHOOK_RETRY_COUNT} | "
                    f"bot_id={bot_id} | reason={wh_data.get('description')}"
                )
        except Exception as e:
            logger.error(f"[CLONE][REGISTER] setWebhook exception attempt {attempt}: {e}")

        if attempt < WEBHOOK_RETRY_COUNT:
            await asyncio.sleep(WEBHOOK_RETRY_DELAY)

    if not webhook_ok:
        await update_bot_status(db_pool, bot_id, "active", webhook_active=False)
        raise RuntimeError(f"Webhook registration failed after {WEBHOOK_RETRY_COUNT} attempts")

    await update_bot_status(db_pool, bot_id, "active", webhook_active=True)

    # Step 4: Spin up PTB Application
    logger.debug(f"[CLONE][REGISTER] Step 4: Spinning up PTB app | bot_id={bot_id}")
    clone_app = create_application(token, is_primary=False)
    clone_app.bot_data["db_pool"] = db_pool
    await clone_app.initialize()
    await clone_app.start()
    await registry_register(bot_id, clone_app)
    logger.info(f"[CLONE][REGISTER] PTB app live | bot_id={bot_id} | @{username}")

    # Step 5: Send success message
    logger.info(f"[CLONE][REGISTER] ✅ Complete | bot_id={bot_id} | @{username}")
    await edit_message.edit_text(
        f"🚀 *@{username} is live\\!*\n\n"
        f"📛 {pending['display_name']}\n"
        f"🆔 `{bot_id}`\n"
        f"🔗 Webhook: active\n\n"
        f"Add it to any group as admin — it will appear in your Mini App dashboard\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Open Mini App", web_app={"url": f"{render_url}/webapp"})
        ]])
    )


# ─── Internal: remove clone ───────────────────────────────────────────────────

async def _remove_clone(db_pool, bot_id: int, bot_record: dict):
    """
    Full teardown sequence. Order matters.
    1. Delete webhook from Telegram
    2. Stop and remove from registry
    3. Delete from DB
    Logs every step. Never raises silently.
    """
    token = decrypt_token(bot_record["token_encrypted"])

    logger.info(f"[CLONE][REMOVE] Starting teardown | bot_id={bot_id} | @{bot_record['username']}")

    # 1. Delete webhook
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            wr = await client.post(
                f"https://api.telegram.org/bot{token}/deleteWebhook",
                json={"drop_pending_updates": True}
            )
            logger.debug(f"[CLONE][REMOVE] deleteWebhook | bot_id={bot_id} | response={wr.json()}")
    except Exception as e:
        logger.warning(f"[CLONE][REMOVE] deleteWebhook failed (continuing) | bot_id={bot_id} | error={e}")

    # 2. Deregister from memory
    removed = await registry_deregister(bot_id)
    logger.info(f"[CLONE][REMOVE] Registry deregister | bot_id={bot_id} | found={removed}")

    # 3. Delete from DB
    await delete_bot(db_pool, bot_id)
    logger.info(f"[CLONE][REMOVE] DB record deleted | bot_id={bot_id}")
