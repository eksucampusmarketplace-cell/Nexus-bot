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
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
from telegram.constants import ParseMode

from bot.registry import register as registry_register, deregister as registry_deregister
from bot.factory import create_application
from bot.utils.crypto import encrypt_token, hash_token, mask_token, validate_token_format, decrypt_token
from db.ops.bots import (
    get_bot_by_id, get_bot_by_token_hash,
    get_bots_by_owner, insert_bot,
    update_bot_status, update_bot_token, delete_bot,
    count_recent_clone_attempts, log_clone_attempt
)
from config import settings

logger = logging.getLogger(__name__)

CLONE_RATE_LIMIT = 5
WEBHOOK_RETRY_COUNT = 3
WEBHOOK_RETRY_DELAY = 5

# Conversation states
(
    WAITING_FOR_TOKEN,
    WAITING_FOR_LIMIT,
    WAITING_FOR_POLICY,
    WAITING_FOR_NOTIFICATIONS,
    WAITING_FOR_CONFIRM,
    REAUTH_WAITING_FOR_TOKEN,
) = range(6)


# ─── Entry point: /clone ──────────────────────────────────────────────────────

async def clone_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"[CLONE] /clone initiated | user_id={user.id} username=@{user.username}")

    # Access control
    if settings.CLONE_ACCESS == "owner_only" and user.id != settings.OWNER_ID:
        logger.warning(f"[CLONE] Access denied | user_id={user.id} | reason=not_owner")
        await update.message.reply_text("⛔ Cloning is restricted to the bot owner.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🔁 *Clone Nexus Bot*\n\n"
        "To create a clone:\n\n"
        "1\. Open @BotFather\n"
        "2\. Send `/newbot` and finish setup\n"
        "3\. Copy the token BotFather gives you\n"
        "4\. Paste it here\n\n"
        "_Your new bot keeps its own name, username and photo\._\n\n"
        "⚠️ Only paste tokens for bots *you own*\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel")
        ]])
    )
    return WAITING_FOR_TOKEN


# ─── State: WAITING_FOR_TOKEN ─────────────────────────────────────────────────

async def token_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    token = update.message.text.strip()

    logger.info(
        f"[CLONE] Token received | user_id={user.id} | "
        f"masked={mask_token(token)}"
    )

    processing = await update.message.reply_text("🔍 Checking token\.\.\.", parse_mode=ParseMode.MARKDOWN_V2)
    db_pool = context.bot_data["db_pool"]

    # ── Layer 1: Rate limit ────────────────────────────────────────────────
    attempts = await count_recent_clone_attempts(db_pool, user.id, window_minutes=60)
    logger.debug(f"[CLONE] Rate limit check | user_id={user.id} | attempts_last_hour={attempts}")

    if attempts >= CLONE_RATE_LIMIT:
        await log_clone_attempt(db_pool, user.id, False, "rate_limited")
        logger.warning(f"[CLONE] Rate limited | user_id={user.id} | attempts={attempts}")
        await processing.edit_text(
            f"⏱ Too many attempts\. Max {CLONE_RATE_LIMIT} per hour\. Try again later\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

    # ── Layer 2: Format check ──────────────────────────────────────────────
    if not validate_token_format(token):
        await log_clone_attempt(db_pool, user.id, False, "invalid_format")
        logger.warning(f"[CLONE] Invalid format | user_id={user.id} | masked={mask_token(token)}")
        await processing.edit_text(
            "❌ Invalid token format\.\n\n"
            "It should look like: `1234567890:ABCdef\.\.\.`\n\n"
            "Send /clone to try again\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

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
                f"⚠️ @{existing['username']} is already registered but its token was revoked\.\n\n"
                f"Send /myclones and use *Re\-authenticate* to fix it\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await processing.edit_text(
                f"⚠️ This token belongs to @{existing['username']} which is already a registered clone\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        return ConversationHandler.END

    # ── Layer 4: Live Telegram validation ──────────────────────────────────
    await processing.edit_text("🔍 Verifying with Telegram\.\.\.", parse_mode=ParseMode.MARKDOWN_V2)
    logger.info(f"[CLONE] Calling getMe | masked={mask_token(token)}")

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            tg_data = resp.json()
    except httpx.TimeoutException:
        await log_clone_attempt(db_pool, user.id, False, "telegram_timeout", token_hash)
        logger.error(f"[CLONE] getMe timed out | user_id={user.id} | masked={mask_token(token)}")
        await processing.edit_text(
            "⏱ Telegram didn't respond\. Please try again\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END
    except Exception as e:
        await log_clone_attempt(db_pool, user.id, False, f"network_error: {e}", token_hash)
        logger.error(f"[CLONE] getMe network error | user_id={user.id} | error={e}")
        await processing.edit_text("❌ Network error\. Please try again\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    if not tg_data.get("ok"):
        err_desc = tg_data.get("description", "Unknown error")
        await log_clone_attempt(db_pool, user.id, False, f"telegram_rejected: {err_desc}", token_hash)
        logger.warning(f"[CLONE] Token rejected by Telegram | user_id={user.id} | reason={err_desc}")
        await processing.edit_text(
            f"❌ Telegram rejected this token:\n_{err_desc}_\n\nSend /clone to try again\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

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

    # Check if this is a reauth for an existing dead bot
    reauth_bot_id = context.user_data.get("reauth_bot_id")
    if reauth_bot_id:
        existing_bot = await get_bot_by_id(db_pool, reauth_bot_id)
        if existing_bot and existing_bot["status"] == "dead":
            # Update the existing bot with new token
            from db.ops.bots import update_bot_token
            await update_bot_token(
                db_pool,
                reauth_bot_id,
                encrypt_token(token),
                token_hash
            )
            await update_bot_status(db_pool, reauth_bot_id, "active", webhook_active=False)
            logger.info(f"[CLONE] Reauth token updated | bot_id={reauth_bot_id}")

            # Now set up webhook for the reauthenticated bot
            try:
                render_url = settings.RENDER_EXTERNAL_URL
                webhook_url = f"{render_url}/webhook/{reauth_bot_id}"

                # Clear webhook first
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"https://api.telegram.org/bot{token}/deleteWebhook",
                        json={"drop_pending_updates": True}
                    )

                # Set new webhook
                wh_ok = False
                for attempt in range(1, WEBHOOK_RETRY_COUNT + 1):
                    try:
                        async with httpx.AsyncClient(timeout=15.0) as client:
                            wh_resp = await client.post(
                                f"https://api.telegram.org/bot{token}/setWebhook",
                                json={
                                    "url": webhook_url,
                                    "allowed_updates": ["message", "callback_query", "chat_member", "new_chat_members"],
                                    "drop_pending_updates": True
                                }
                            )
                            wh_data = wh_resp.json()
                            if wh_data.get("ok"):
                                wh_ok = True
                                break
                    except Exception:
                        pass
                    if attempt < WEBHOOK_RETRY_COUNT:
                        await asyncio.sleep(WEBHOOK_RETRY_DELAY)

                if wh_ok:
                    await update_bot_status(db_pool, reauth_bot_id, "active", webhook_active=True)

                    # Spin up PTB Application for the reactivated bot
                    clone_app = create_application(token, is_primary=False)
                    clone_app.bot_data["db_pool"] = db_pool
                    await clone_app.initialize()
                    await clone_app.start()
                    await registry_register(reauth_bot_id, clone_app)

                    await processing.edit_text(
                        f"✅ *@{cloned_username} re\-authenticated\!*\n\n"
                        f"Your bot is now active again\.",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    logger.info(f"[CLONE] Reauth complete | bot_id={reauth_bot_id}")
                else:
                    await processing.edit_text(
                        f"⚠️ Token updated but webhook setup failed\. Please contact support\.",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
            except Exception as e:
                logger.error(f"[CLONE] Reauth failed | bot_id={reauth_bot_id} | error={e}")
                await processing.edit_text(
                    f"❌ Re\-authentication failed: _{e}_",
                    parse_mode=ParseMode.MARKDOWN_V2
                )

            context.user_data.pop("reauth_bot_id", None)
            return ConversationHandler.END

    # Store pending data for new clone registration
    context.user_data["pending_clone"] = {
        "token":        token,
        "token_hash":   token_hash,
        "bot_id":       cloned_bot_id,
        "username":     cloned_username,
        "display_name": cloned_name,
    }

    await processing.edit_text(
        f"✅ *Token verified\!*\n\n"
        f"🤖 @{cloned_username}\n"
        f"📛 {cloned_name}\n\n"
        f"How many groups should this bot work in? \(1–5\)\n"
        f"Default: 1",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("1", callback_data="clone:limit:1"),
            InlineKeyboardButton("2", callback_data="clone:limit:2"),
            InlineKeyboardButton("3", callback_data="clone:limit:3"),
            InlineKeyboardButton("4", callback_data="clone:limit:4"),
            InlineKeyboardButton("5", callback_data="clone:limit:5"),
        ], [
            InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel")
        ]])
    )
    return WAITING_FOR_LIMIT


# ─── State: WAITING_FOR_LIMIT ─────────────────────────────────────────────────

async def on_limit_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    parts = query.data.split(":")
    limit = int(parts[2])

    logger.info(f"[CLONE] Limit chosen | user_id={user.id} | limit={limit}")

    context.user_data["pending_clone"]["group_limit"] = limit

    await query.edit_message_text(
        "Who can add this bot to groups?\n\n"
        "🔒 *Only me*: Only you can add this bot\.\n"
        "✅ *Anyone \(open\)*: Anyone can add it\. They can use it but won't have owner\-level control\.\n"
        "🔔 *Approval needed*: Anyone can add it, but you'll get a request to approve or deny each group\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔒 Only me", callback_data="clone:policy:blocked")],
            [InlineKeyboardButton("✅ Anyone (open)", callback_data="clone:policy:open")],
            [InlineKeyboardButton("🔔 Approval needed", callback_data="clone:policy:approval")],
            [InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel")]
        ])
    )
    return WAITING_FOR_POLICY


# ─── State: WAITING_FOR_POLICY ────────────────────────────────────────────────

async def on_policy_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    parts = query.data.split(":")
    policy = parts[2]

    logger.info(f"[CLONE] Policy chosen | user_id={user.id} | policy={policy}")

    context.user_data["pending_clone"]["group_access_policy"] = policy

    if policy == "approval":
        # For approval, notifications are forced ON
        context.user_data["pending_clone"]["bot_add_notifications"] = True
        # Skip to confirmation
        await _show_final_confirmation(query, context)
        return WAITING_FOR_CONFIRM
    else:
        await query.edit_message_text(
            "Notify me when someone adds my bot to a group?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Yes, notify me", callback_data="clone:notify:yes")],
                [InlineKeyboardButton("No thanks", callback_data="clone:notify:no")],
                [InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel")]
            ])
        )
        return WAITING_FOR_NOTIFICATIONS


# ─── State: WAITING_FOR_NOTIFICATIONS ─────────────────────────────────────────

async def on_notify_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    parts = query.data.split(":")
    notify = (parts[2] == "yes")

    logger.info(f"[CLONE] Notify chosen | user_id={user.id} | notify={notify}")

    context.user_data["pending_clone"]["bot_add_notifications"] = notify
    await _show_final_confirmation(query, context)
    return WAITING_FOR_CONFIRM


# ─── State: WAITING_FOR_CONFIRM ───────────────────────────────────────────────

async def on_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    db_pool = context.bot_data["db_pool"]

    pending = context.user_data.pop("pending_clone", None)

    if not pending:
        logger.warning(f"[CLONE] Confirm with no pending data | user_id={user.id}")
        await query.edit_message_text("❌ Session expired\. Send /clone to try again\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    await query.edit_message_text(
        f"⚙️ Registering @{pending['username']}\.\.\.",
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
            f"❌ Registration failed:\n_{e}_\n\nSend /clone to try again\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

    return ConversationHandler.END


# ─── Cancel handler ───────────────────────────────────────────────────────────

async def on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    context.user_data.pop("pending_clone", None)
    context.user_data.pop("reauth_bot_id", None)

    logger.info(f"[CLONE] Cancelled | user_id={user.id}")
    await query.edit_message_text("❎ Clone cancelled\.", parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END


# ─── Helper: Show final confirmation ──────────────────────────────────────────

async def _show_final_confirmation(query, context):
    pending = context.user_data.get("pending_clone", {})
    cloned_username = pending["username"]
    cloned_bot_id = pending["bot_id"]

    await query.edit_message_text(
        f"✅ *Settings saved\!*\n\n"
        f"🤖 @{cloned_username}\n"
        f"🆔 `{cloned_bot_id}`\n\n"
        f"*Summary:*\n"
        f"👥 Group limit: {pending.get('group_limit', 1)}\n"
        f"🛡️ Policy: {pending.get('group_access_policy', 'blocked')}\n"
        f"🔔 Notify: {'Yes' if pending.get('bot_add_notifications') else 'No'}\n\n"
        f"Confirm to register this bot as a Nexus clone?",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirm", callback_data="clone:confirm"),
            InlineKeyboardButton("❌ Cancel",  callback_data="clone:cancel")
        ]])
    )


# ─── Non-conversation callbacks (outside ConversationHandler) ─────────────────

async def clone_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles myclones management callbacks (new, remove, confirm_remove, reauth)."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    parts = query.data.split(":")
    action = parts[1]

    logger.info(f"[CLONE] Management callback | user_id={user.id} | action={action} | data={query.data}")

    db_pool = context.bot_data["db_pool"]

    # ── new (from myclones add button) ────────────────────────────────────
    if action == "new":
        await query.edit_message_text(
            "Paste your new bot token from @BotFather:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel_entry")
            ]])
        )
        return WAITING_FOR_TOKEN

    # ── remove (show confirm prompt) ──────────────────────────────────────
    if action == "remove":
        target_bot_id = int(parts[2])
        bot_record = await get_bot_by_id(db_pool, target_bot_id)

        if not bot_record or bot_record["owner_user_id"] != user.id:
            logger.warning(f"[CLONE] Remove denied | user_id={user.id} | target={target_bot_id}")
            await query.edit_message_text("❌ Bot not found or you don't own it\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        await query.edit_message_text(
            f"⚠️ *Remove @{bot_record['username']}?*\n\n"
            f"This stops the bot, deletes its webhook, and removes all data\. Cannot be undone\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑️ Yes, remove", callback_data=f"clone:confirm_remove:{target_bot_id}"),
                InlineKeyboardButton("↩️ Keep it",     callback_data="clone:keep")
            ]])
        )
        return

    # ── confirm_remove ────────────────────────────────────────────────────
    if action == "confirm_remove":
        target_bot_id = int(parts[2])
        bot_record = await get_bot_by_id(db_pool, target_bot_id)

        if not bot_record or bot_record["owner_user_id"] != user.id:
            await query.edit_message_text("❌ Bot not found or you don't own it\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        if bot_record.get("is_primary"):
            logger.warning(f"[CLONE] Attempt to remove primary bot | user_id={user.id}")
            await query.edit_message_text("❌ You cannot remove the primary bot\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

        await query.edit_message_text(
            f"🗑️ Removing @{bot_record['username']}\.\.\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

        try:
            await _remove_clone(db_pool, target_bot_id, bot_record)
            logger.info(f"[CLONE] Removed | bot_id={target_bot_id} | username=@{bot_record['username']} | by=user_id={user.id}")
            await query.edit_message_text(
                f"✅ @{bot_record['username']} has been removed\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logger.error(f"[CLONE] Removal failed | bot_id={target_bot_id} | error={e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Removal failed: _{e}_",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        return

    # ── keep (cancel remove) ──────────────────────────────────────────────
    if action == "keep":
        await query.edit_message_text("✅ Keep it is.")
        return

    # ── reauth (dead bot re-authentication) ───────────────────────────────
    if action == "reauth":
        target_bot_id = int(parts[2])
        context.user_data["reauth_bot_id"] = target_bot_id
        await query.edit_message_text(
            f"Paste the new token for this bot from @BotFather:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="clone:cancel_entry")
            ]])
        )
        return WAITING_FOR_TOKEN

    # ── cancel_entry (cancel from entry point) ────────────────────────────
    if action == "cancel_entry":
        context.user_data.pop("reauth_bot_id", None)
        await query.edit_message_text("❎ Cancelled\.")
        return ConversationHandler.END


# ─── /myclones ────────────────────────────────────────────────────────────────

async def myclones_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_pool = context.bot_data["db_pool"]

    logger.info(f"[CLONE] /myclones | user_id={user.id}")

    clones = await get_bots_by_owner(db_pool, user.id)

    if not clones:
        await update.message.reply_text(
            "You have no clones yet\.\n\nSend /clone to add your first one\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    text = f"🤖 *Your Bots* \({len(clones)}\)\n\n"
    keyboard = []

    for bot in clones:
        status_icon  = "👑" if bot["is_primary"] else ("🟢" if bot["status"] == "active" else "🔴")
        webhook_icon = "🔗" if bot["webhook_active"] else "⚠️"
        label        = " \(Primary\)" if bot["is_primary"] else ""

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


# ─── /cloneset ────────────────────────────────────────────────────────────────

async def cloneset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cloneset limit <1-5>          → update group_limit
    /cloneset policy open|approval|blocked  → update group_access_policy
    /cloneset notify on|off        → update bot_add_notifications
    """
    user = update.effective_user
    args = context.args
    db_pool = context.bot_data["db_pool"]

    if not args or len(args) < 2:
        await update.message.reply_text(
            "📖 *Usage:*\n"
            "`/cloneset limit <1-5>`\n"
            "`/cloneset policy open|approval|blocked`\n"
            "`/cloneset notify on|off`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    subcommand = args[0].lower()
    value = args[1].lower()

    clones = await get_bots_by_owner(db_pool, user.id)
    clones_only = [c for c in clones if not c["is_primary"]]

    if not clones_only:
        await update.message.reply_text("❌ You don't have any clone bots.")
        return

    target_bot = clones_only[0]
    bot_id = target_bot["bot_id"]

    from db.ops.bots import update_bot_access_settings

    if subcommand == "limit":
        if not value.isdigit() or not (1 <= int(value) <= 20):
            await update.message.reply_text("❌ Limit must be between 1 and 20.")
            return
        await update_bot_access_settings(db_pool, bot_id, group_limit=int(value))
        await update.message.reply_text(f"✅ Group limit updated to {value} for @{target_bot['username']}.")

    elif subcommand == "policy":
        if value not in ["open", "approval", "blocked"]:
            await update.message.reply_text("❌ Policy must be: open, approval, or blocked.")
            return
        await update_bot_access_settings(db_pool, bot_id, group_access_policy=value)
        await update.message.reply_text(f"✅ Access policy updated to {value} for @{target_bot['username']}.")

    elif subcommand == "notify":
        if value not in ["on", "off"]:
            await update.message.reply_text("❌ Notify must be: on or off.")
            return
        notify = (value == "on")
        await update_bot_access_settings(db_pool, bot_id, bot_add_notifications=notify)
        await update.message.reply_text(f"✅ Notifications turned {value} for @{target_bot['username']}.")

    else:
        await update.message.reply_text("❌ Unknown subcommand.")


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
        "group_limit":     pending.get("group_limit", 1),
        "group_access_policy": pending.get("group_access_policy", "blocked"),
        "bot_add_notifications": pending.get("bot_add_notifications", False),
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
        f"🚀 *@{username} is live\!*\n\n"
        f"📛 {pending['display_name']}\n"
        f"🆔 `{bot_id}`\n"
        f"🔗 Webhook: active\n\n"
        f"Add it to any group as admin — it will appear in your Mini App dashboard\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Open Mini App", web_app={"url": f"{render_url}/miniapp"})
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


# ─── ConversationHandler export ───────────────────────────────────────────────

clone_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("clone", clone_command_handler),
        CallbackQueryHandler(clone_management_callback, pattern=r"^clone:(new|reauth):")
    ],
    states={
        WAITING_FOR_TOKEN: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d{8,12}:[\w-]{35,50}$"),
                token_input_handler
            ),
            CallbackQueryHandler(on_cancel, pattern=r"^clone:cancel$"),
            CallbackQueryHandler(on_cancel, pattern=r"^clone:cancel_entry$"),
        ],
        WAITING_FOR_LIMIT: [
            CallbackQueryHandler(on_limit_chosen, pattern=r"^clone:limit:\d+$"),
            CallbackQueryHandler(on_cancel, pattern=r"^clone:cancel$"),
        ],
        WAITING_FOR_POLICY: [
            CallbackQueryHandler(on_policy_chosen, pattern=r"^clone:policy:(blocked|open|approval)$"),
            CallbackQueryHandler(on_cancel, pattern=r"^clone:cancel$"),
        ],
        WAITING_FOR_NOTIFICATIONS: [
            CallbackQueryHandler(on_notify_chosen, pattern=r"^clone:notify:(yes|no)$"),
            CallbackQueryHandler(on_cancel, pattern=r"^clone:cancel$"),
        ],
        WAITING_FOR_CONFIRM: [
            CallbackQueryHandler(on_confirm, pattern=r"^clone:confirm$"),
            CallbackQueryHandler(on_cancel, pattern=r"^clone:cancel$"),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", lambda u, c: ConversationHandler.END),
    ],
    per_chat=True,
)
