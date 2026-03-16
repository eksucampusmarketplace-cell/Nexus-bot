"""
bot/utils/error_notifier.py

Error notification and health check utilities for v22.
Sends DM alerts to bot owner on permission issues or startup problems.
Implements the Error Catalogue with 16 error types, deduplication,
and owner preferences support.

SECURITY: Error messages sent to clone owners are sanitized to avoid
leaking infrastructure details, tech stack, or internal API paths.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# Global cache for warnings time column detection
_WARNINGS_TIME_COL = None

# In-memory fallback deduplication cache (Bug #8 fix)
# Used when database write fails - ensures dedup still works
_dedup_cache: dict[tuple, datetime] = {}

# ═══════════════════════════════════════════════════════════════════════════════
# ERROR CATALOG - 16 error types with title, why, fix steps, and send_to
# ═══════════════════════════════════════════════════════════════════════════════

# Full catalog with detailed steps - used for main owner only
ERROR_CATALOG: Dict[str, Dict[str, Any]] = {
    "PRIVACY_MODE_ON": {
        "title": "⚠️ Privacy Mode Is ON",
        "why": "Your bot can only see messages starting with / — automod, filters, flood detection will NOT work.",
        "steps": [
            "Open Telegram → @BotFather",
            "Send /mybots and select your bot",
            "Tap Bot Settings → Group Privacy → Turn OFF",
            "Restart bot or send /sync in each group",
        ],
        "send_to": "clone_owner",
    },
    "WEBHOOK_FAILED": {
        "title": "🔴 Webhook Setup Failed",
        "why": "The bot could not register its webhook with Telegram. Updates may not be received.",
        "steps": [
            "Check RENDER_EXTERNAL_URL is set correctly",
            "Verify the bot token is valid",
            "Check Render service is running and accessible",
            "Try restarting the bot",
        ],
        "send_to": "clone_owner",
    },
    "WEBHOOK_MISSING_UPDATES": {
        "title": "⚠️ Webhook Registered But No Updates",
        "why": "The webhook is set but no updates are arriving from Telegram.",
        "steps": [
            "Check webhook URL is publicly accessible",
            "Verify SSL certificate is valid",
            "Check Telegram can reach your server (use getWebhookInfo)",
            "Try deleting and re-setting the webhook",
        ],
        "send_to": "clone_owner",
    },
    "BOT_NOT_ADMIN": {
        "title": "🔴 Bot Is Not Admin",
        "why": "The bot was added to a group but doesn't have admin rights.",
        "steps": [
            "Go to the group settings",
            "Administrators → Add Administrator",
            "Select your bot and grant all permissions",
            "Bot will automatically detect the change",
        ],
        "send_to": "clone_owner",
    },
    "BOT_CANT_DELETE": {
        "title": "⚠️ Bot Cannot Delete Messages",
        "why": "The bot is admin but missing the 'Delete Messages' permission.",
        "steps": [
            "Go to group settings → Administrators",
            "Find your bot in the list",
            "Enable 'Delete Messages' permission",
            "Save changes",
        ],
        "send_to": "clone_owner",
    },
    "BOT_CANT_RESTRICT": {
        "title": "⚠️ Bot Cannot Restrict Members",
        "why": "The bot is admin but missing the 'Restrict Members' permission needed for mutes/bans.",
        "steps": [
            "Go to group settings → Administrators",
            "Find your bot in the list",
            "Enable 'Restrict Members' permission",
            "Save changes",
        ],
        "send_to": "clone_owner",
    },
    "BOT_KICKED": {
        "title": "👢 Bot Was Removed From Group",
        "why": "Your bot was kicked from a group. All settings for that group are preserved.",
        "steps": [
            "Contact the group admin if this was accidental",
            "Re-add the bot if needed",
            "Bot will restore previous settings automatically",
        ],
        "send_to": "clone_owner",
    },
    "GROUPS_NOT_APPEARING": {
        "title": "⚠️ Groups Missing From Dashboard",
        "why": "Some groups aren't showing in the Mini App dashboard.",
        "steps": [
            "Send /sync in the missing group",
            "Ensure bot is still admin in that group",
            "Check the bot hasn't been blocked",
            "Wait a few minutes for cache to refresh",
        ],
        "send_to": "clone_owner",
    },
    "FED_BAN_PROPAGATION_FAILED": {
        "title": "⚠️ TrustNet Ban Could Not Be Enforced",
        "why": "A federation ban was issued but could not be applied in all groups.",
        "steps": [
            "Check the bot is still admin in affected groups",
            "Verify federation membership is active",
            "The ban will retry automatically",
            "Manually ban if urgent",
        ],
        "send_to": "clone_owner",
    },
    "CAPTCHA_WEBAPP_URL_MISSING": {
        "title": "🔴 Captcha WebApp URL Not Set",
        "why": "Captcha is set to WebApp mode but RENDER_EXTERNAL_URL is not configured.",
        "steps": [
            "Set RENDER_EXTERNAL_URL in your environment",
            "Should be: https://your-service.onrender.com",
            "Restart the bot",
            "Or switch captcha to 'button' mode instead",
        ],
        "send_to": "clone_owner",
    },
    "INVALID_TOKEN": {
        "title": "🔴 Invalid Bot Token",
        "why": "Telegram rejected the bot token. The bot cannot start.",
        "steps": [
            "Verify token format: 123456789:ABCdef...",
            "Get a new token from @BotFather if needed",
            "Update the token in your environment",
            "Restart the bot",
        ],
        "send_to": "clone_owner",
    },
    "MISSING_ENV_VAR": {
        "title": "🔴 Missing Required Environment Variable",
        "why": "A required environment variable is not set. Bot cannot start.",
        "steps": [
            "Check the error message for the missing variable",
            "Add it to your Render environment variables",
            "Common: PRIMARY_BOT_TOKEN, SUPABASE_URL, SECRET_KEY",
            "Restart the bot after adding",
        ],
        "send_to": "main_owner",
    },
    "SUPABASE_CONNECTION_FAILED": {
        "title": "🔴 Database Connection Failed",
        "why": "Cannot connect to Supabase/PostgreSQL. Bot cannot start.",
        "steps": [
            "Check SUPABASE_CONNECTION_STRING is correct",
            "Verify Supabase is running (check status page)",
            "Check firewall/network settings",
            "Contact support if persistent",
        ],
        "send_to": "main_owner",
    },
    "ML_TRAINING_COMPLETE": {
        "title": "✅ ML Training Complete",
        "why": "The spam classifier has been successfully trained.",
        "steps": [
            "New model is now active",
            "Spam detection accuracy improved",
            "No action needed",
        ],
        "send_to": "main_owner",
    },
    "ML_TRAINING_FAILED": {
        "title": "🔴 ML Training Failed",
        "why": "Could not train the spam classifier. Insufficient data or error.",
        "steps": [
            "Need at least 100 labeled samples (spam + ham)",
            "Use /report to mark more messages",
            "Wait for more group activity",
            "Retry training later",
        ],
        "send_to": "main_owner",
    },
    "ANALYTICS_ERROR": {
        "title": "🔴 Analytics Job Persistent Errors",
        "why": "The hourly/daily analytics aggregation has failed multiple times.",
        "steps": [
            "Check database connection",
            "Verify analytics tables exist",
            "Check logs for specific errors",
            "Contact support if persistent",
        ],
        "send_to": "main_owner",
    },
}

# Sanitized catalog for clone owners - removes infrastructure details
CLONE_OWNER_CATALOG: Dict[str, Dict[str, Any]] = {
    "PRIVACY_MODE_ON": {
        "title": "⚠️ Privacy Mode Is ON",
        "why": "Your bot can only see messages starting with /. Most features will NOT work.",
        "steps": [
            "Open Telegram → @BotFather",
            "Send /mybots and select your bot",
            "Tap Bot Settings → Group Privacy → Turn OFF",
            "Re-add the bot to your groups",
        ],
        "send_to": "clone_owner",
    },
    "WEBHOOK_FAILED": {
        "title": "🔴 Webhook Setup Failed",
        "why": "The bot could not receive updates from Telegram.",
        "steps": [
            "Verify your bot token is valid",
            "Check the bot service is running",
            "Try restarting the bot",
        ],
        "send_to": "clone_owner",
    },
    "WEBHOOK_MISSING_UPDATES": {
        "title": "⚠️ No Updates Received",
        "why": "The bot is registered but not receiving messages.",
        "steps": [
            "Verify your service URL is accessible publicly",
            "Check SSL certificate is valid",
            "Try re-adding the bot",
        ],
        "send_to": "clone_owner",
    },
    "BOT_NOT_ADMIN": {
        "title": "🔴 Bot Is Not Admin",
        "why": "The bot was added to a group but doesn't have admin rights.",
        "steps": [
            "Go to the group settings",
            "Administrators → Add Administrator",
            "Select your bot and grant all permissions",
        ],
        "send_to": "clone_owner",
    },
    "BOT_CANT_DELETE": {
        "title": "⚠️ Cannot Delete Messages",
        "why": "The bot is admin but missing delete permission.",
        "steps": [
            "Go to group settings → Administrators",
            "Find your bot",
            "Enable 'Delete Messages' permission",
        ],
        "send_to": "clone_owner",
    },
    "BOT_CANT_RESTRICT": {
        "title": "⚠️ Cannot Restrict Members",
        "why": "The bot is admin but missing restriction permission.",
        "steps": [
            "Go to group settings → Administrators",
            "Find your bot",
            "Enable 'Restrict Members' permission",
        ],
        "send_to": "clone_owner",
    },
    "BOT_KICKED": {
        "title": "👢 Bot Was Removed From Group",
        "why": "Your bot was kicked from a group. Settings are preserved.",
        "steps": ["Contact the group admin if this was accidental", "Re-add the bot if needed"],
        "send_to": "clone_owner",
    },
    "GROUPS_NOT_APPEARING": {
        "title": "⚠️ Groups Missing From Dashboard",
        "why": "Some groups aren't showing in your dashboard.",
        "steps": ["Send /sync in the missing group", "Ensure bot is still admin in that group"],
        "send_to": "clone_owner",
    },
    "FED_BAN_PROPAGATION_FAILED": {
        "title": "⚠️ Federation Ban Incomplete",
        "why": "A ban could not be applied in all federated groups.",
        "steps": ["Check the bot is admin in affected groups", "Manually ban if urgent"],
        "send_to": "clone_owner",
    },
    "CAPTCHA_WEBAPP_URL_MISSING": {
        "title": "🔴 Captcha WebApp Not Available",
        "why": "WebApp captcha mode is enabled but not configured.",
        "steps": ["Switch captcha to 'button' mode", "Or contact bot owner to configure"],
        "send_to": "clone_owner",
    },
    "INVALID_TOKEN": {
        "title": "🔴 Invalid Bot Token",
        "why": "Telegram rejected the bot token.",
        "steps": ["Get a new token from @BotFather", "Update your bot configuration"],
        "send_to": "clone_owner",
    },
}

# Sensitive patterns to redact from context when sending to clone owners
SENSITIVE_PATTERNS = [
    (r"render\.com", "[HOST]"),
    (r"onrender\.com", "[HOST]"),
    (r"supabase\.co", "[DB_SERVICE]"),
    (r"postgres[^\s]*", "[DATABASE]"),
    (r"redis[^\s]*", "[CACHE]"),
    (r"/api/[a-z_]+", "[API_ENDPOINT]"),
    (r"PRIMARY_BOT_TOKEN", "[TOKEN]"),
    (r"SUPABASE_[A-Z_]+", "[DB_CONFIG]"),
    (r"SECRET_KEY", "[SECRET]"),
    (r"RENDER_EXTERNAL_URL", "[URL_CONFIG]"),
    (r"[a-z0-9]{20,}\@[a-z0-9]", "[EMAIL]"),
]


def _sanitize_for_clone(text: str) -> str:
    """
    Remove sensitive infrastructure details from text sent to clone owners.
    This prevents leaking deployment details, tech stack, and internal paths.
    """
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    return sanitized


def _format_error_message(
    error_type: str, context: Dict[str, Any] = None, for_clone_owner: bool = False
) -> str:
    """
    Format error message from catalog with context substitution.

    Args:
        error_type: Key from ERROR_CATALOG
        context: Optional additional context details
        for_clone_owner: If True, use sanitized catalog for clone owners
    """
    # Use clone owner catalog if requested, otherwise full catalog
    catalog = CLONE_OWNER_CATALOG if for_clone_owner else ERROR_CATALOG

    catalog_entry = catalog.get(
        error_type,
        {
            "title": f"⚠️ {error_type}",
            "why": "An error occurred.",
            "steps": ["Check logs for details."],
            "send_to": "clone_owner" if for_clone_owner else "main_owner",
        },
    )

    text = f"<b>{catalog_entry['title']}</b>\n\n"
    text += f"<b>Why:</b> {catalog_entry['why']}\n\n"
    text += "<b>How to fix:</b>\n"
    for i, step in enumerate(catalog_entry["steps"], 1):
        # Sanitize step text for clone owners
        step_text = _sanitize_for_clone(step) if for_clone_owner else step
        text += f"{i}. {step_text}\n"

    # Add context if provided (sanitize if sending to clone owner)
    if context:
        text += "\n<b>Details:</b>\n"
        for key, value in context.items():
            value_str = str(value)
            # Sanitize context values for clone owners
            if for_clone_owner:
                value_str = _sanitize_for_clone(value_str)
            text += f"• {key}: {value_str}\n"

    text += "\n<i>This message won't repeat for 24 hours.</i>"
    return text


async def _should_send_notification(pool, bot_id: int, error_type: str, owner_id: int) -> bool:
    """
    Check if we should send this notification based on:
    1. Owner preferences (muted types)
    2. Deduplication (same error+bot in last 24h)

    Bug #6 fix: Includes bot_id in dedup check to prevent cross-bot suppression.
    For system-level errors (bot_id is None), dedups by owner_id + error_type only.
    """
    # Check in-memory cache first (Bug #8 - fallback when DB fails)
    cache_key = (owner_id, error_type, bot_id)
    if cache_key in _dedup_cache:
        sent_at = _dedup_cache[cache_key]
        if datetime.now(timezone.utc) - sent_at < timedelta(hours=24):
            return False

    try:
        async with pool.acquire() as conn:
            # Check owner preferences
            pref = await conn.fetchrow(
                """SELECT notify_dm FROM owner_error_prefs
                   WHERE owner_id = $1 AND error_type = $2""",
                owner_id,
                error_type,
            )
            # If preference exists and notify_dm is False, don't send
            if pref and not pref["notify_dm"]:
                return False

            # Check deduplication - Bug #6 fix: include bot_id
            yesterday = datetime.now(timezone.utc) - timedelta(hours=24)

            # For system-level errors (bot_id is None), use owner_id + error_type only
            # For bot-specific errors, use owner_id + error_type + bot_id
            if bot_id is None or bot_id == 0:
                # System-level error: dedup by owner + error_type only
                recent = await conn.fetchrow(
                    """SELECT 1 FROM error_notifications
                       WHERE owner_id = $1 AND error_type = $2
                       AND bot_id IS NULL AND sent_at > $3""",
                    owner_id,
                    error_type,
                    yesterday,
                )
            else:
                # Bot-specific error: dedup by owner + error_type + bot_id
                recent = await conn.fetchrow(
                    """SELECT 1 FROM error_notifications
                       WHERE owner_id = $1 AND error_type = $2
                       AND bot_id = $3 AND sent_at > $4""",
                    owner_id,
                    error_type,
                    bot_id,
                    yesterday,
                )
            if recent:
                return False

            return True
    except Exception as e:
        logger.warning(f"[NOTIFIER] Failed to check notification rules: {e}")
        # Default to sending if we can't check
        return True


async def _record_notification(
    pool, owner_id: int, error_type: str, message: str, bot_id: Optional[int] = None
) -> None:
    """Record that a notification was sent for deduplication."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO error_notifications (owner_id, error_type, message, bot_id)
                   VALUES ($1, $2, $3, $4)""",
                owner_id,
                error_type,
                message[:1000],
                bot_id,
            )
    except Exception as e:
        logger.warning(f"[NOTIFIER] Failed to record notification: {e}")


async def notify_owner(
    bot: Bot,
    owner_id: int,
    error_type: str,
    bot_id: Optional[int] = None,
    context: Dict[str, Any] = None,
    pool=None,
    for_clone_owner: bool = False,
) -> bool:
    """
    Send error notification to main bot owner.

    Args:
        bot: Bot instance to send message with
        owner_id: Owner user ID
        error_type: Key from ERROR_CATALOG
        bot_id: Optional bot ID for context
        context: Optional additional context
        pool: Database pool for deduplication and prefs
        for_clone_owner: If True, sanitize message for clone owners

    Returns:
        True if notification was sent successfully
    """
    # Skip if not in catalog
    if error_type not in ERROR_CATALOG and error_type not in CLONE_OWNER_CATALOG:
        logger.warning(f"[NOTIFIER] Unknown error type: {error_type}")

    # Check deduplication and preferences if pool available
    if pool:
        should_send = await _should_send_notification(pool, bot_id or 0, error_type, owner_id)
        if not should_send:
            logger.debug(f"[NOTIFIER] Skipping {error_type} for {owner_id} (dedup or muted)")
            return False

    # Use sanitized formatting for clone owners
    text = _format_error_message(error_type, context, for_clone_owner=for_clone_owner)

    try:
        await bot.send_message(chat_id=owner_id, text=text, parse_mode=ParseMode.HTML)
        logger.info(
            f"[NOTIFIER] Sent {error_type} to owner {owner_id} (clone_owner={for_clone_owner})"
        )

        # Bug #8 fix: Update in-memory cache immediately after successful send
        # This ensures deduplication works even if DB write fails
        cache_key = (owner_id, error_type, bot_id)
        _dedup_cache[cache_key] = datetime.now(timezone.utc)

        # Record notification
        if pool:
            try:
                await _record_notification(pool, owner_id, error_type, text, bot_id)
            except Exception as e:
                # Bug #8 fix: Log ERROR (not WARNING) when dedup is broken due to DB failure
                logger.error(
                    f"[NOTIFIER] CRITICAL: Notification sent but DB write failed. "
                    f"Deduplication may not work for {error_type} until restart. Error: {e}"
                )

        return True
    except Exception as e:
        logger.warning(f"[NOTIFIER] Failed to notify owner {owner_id}: {e}")
        return False


async def notify_clone_owner(
    bot: Bot, clone_bot_id: int, error_type: str, context: Dict[str, Any] = None, pool=None
) -> bool:
    """
    Send error notification to a clone bot's owner.
    Looks up owner from bots table.

    SECURITY: Messages are sanitized to prevent leaking infrastructure details.

    Args:
        bot: Bot instance to send message with
        clone_bot_id: The clone bot's Telegram ID
        error_type: Key from ERROR_CATALOG
        context: Optional additional context
        pool: Database pool for owner lookup and deduplication

    Returns:
        True if notification was sent successfully
    """
    if not pool:
        logger.warning("[NOTIFIER] No pool available for clone owner lookup")
        return False

    try:
        async with pool.acquire() as conn:
            # Look up clone owner - bots table uses 'id' or 'bot_id' for Telegram ID
            row = await conn.fetchrow(
                """SELECT owner_user_id FROM bots
                   WHERE (id = $1 OR bot_id = $1) AND is_primary = FALSE""",
                clone_bot_id,
            )

            if not row:
                logger.warning(f"[NOTIFIER] No clone found for bot_id {clone_bot_id}")
                return False

            owner_id = row["owner_user_id"]
            if not owner_id:
                logger.warning(f"[NOTIFIER] Clone {clone_bot_id} has no owner_user_id")
                return False

            # Send to the clone owner with sanitization enabled
            return await notify_owner(
                bot, owner_id, error_type, clone_bot_id, context, pool, for_clone_owner=True
            )

    except Exception as e:
        logger.warning(f"[NOTIFIER] Failed to notify clone owner: {e}")
        return False


async def notify_privacy_mode_on(bot: Bot, clone_bot_id: int, username: str, pool=None) -> bool:
    """
    Specialized notification for privacy mode being ON.
    Routes to clone owner, not main owner.
    """
    context = {"bot_username": username}
    return await notify_clone_owner(bot, clone_bot_id, "PRIVACY_MODE_ON", context, pool)


async def run_startup_health_check(bot: Bot, owner_id: int, pool=None) -> dict:
    """
    Run health checks at bot startup.
    Returns dict with status info.
    """
    results = {
        "bot_info_ok": False,
        "db_connection_ok": False,
        "permissions_ok": False,
        "errors": [],
    }

    try:
        me = await bot.get_me()
        results["bot_info_ok"] = bool(me and me.id)
        results["bot_username"] = me.username if me else None
    except Exception as e:
        results["errors"].append(f"Bot info fetch failed: {e}")

    return results


async def check_group_permissions(
    bot: Bot, chat_id: int, owner_id: int, required_permissions: list = None, pool=None
) -> dict:
    """
    Check if bot has required permissions in a group.
    Sends DM to owner if permissions are missing.

    Args:
        bot: Bot instance
        chat_id: Group chat ID to check
        owner_id: Owner user ID to notify
        required_permissions: List of required permission strings
        pool: Database pool for notifications

    Returns:
        Dict with permission status
    """
    if required_permissions is None:
        required_permissions = ["can_delete_messages", "can_restrict_members"]

    results = {"has_permissions": False, "missing": [], "chat_member": None}

    try:
        me = await bot.get_me()
        chat_member = await bot.get_chat_member(chat_id, me.id)
        results["chat_member"] = chat_member

        # Check admin status
        if chat_member.status not in ["administrator", "creator"]:
            results["missing"].append("administrator")
            await _notify_permission_issue(bot, owner_id, chat_id, results["missing"], pool)
            return results

        # Check specific permissions
        for perm in required_permissions:
            if not getattr(chat_member, perm, False):
                results["missing"].append(perm)

        results["has_permissions"] = len(results["missing"]) == 0

        if results["missing"]:
            await _notify_permission_issue(bot, owner_id, chat_id, results["missing"], pool)

    except Exception as e:
        logger.warning(f"Permission check failed for chat {chat_id}: {e}")
        results["error"] = str(e)

    return results


async def _notify_permission_issue(
    bot: Bot, owner_id: int, chat_id: int, missing: list, pool=None, is_clone_owner: bool = False
) -> bool:
    """
    Send DM to owner about missing permissions using error catalog.

    Args:
        bot: Bot instance
        owner_id: Owner user ID to notify
        chat_id: Group chat ID
        missing: List of missing permissions
        pool: Database pool
        is_clone_owner: If True, sanitize messages for clone owner

    Returns True if message was sent successfully.
    """
    # Map missing permissions to error types
    error_type = None
    if "administrator" in missing:
        error_type = "BOT_NOT_ADMIN"
    elif "can_delete_messages" in missing:
        error_type = "BOT_CANT_DELETE"
    elif "can_restrict_members" in missing:
        error_type = "BOT_CANT_RESTRICT"

    if error_type and pool:
        return await notify_owner(
            bot,
            owner_id,
            error_type,
            context={"chat_id": chat_id},
            pool=pool,
            for_clone_owner=is_clone_owner,
        )

    # Fallback to legacy message format if not in catalog - sanitize chat_id for clone owners
    perm_descriptions = {
        "administrator": "🔴 <b>Admin Status</b> — Bot is not an admin",
        "can_delete_messages": "🗑 <b>Delete Messages</b> — Cannot delete spam",
        "can_restrict_members": "🔇 <b>Restrict Members</b> — Cannot mute/ban users",
        "can_pin_messages": "📌 <b>Pin Messages</b> — Cannot pin messages",
        "can_invite_users": "➕ <b>Invite Users</b> — Cannot add members",
        "can_promote_members": "⬆️ <b>Promote Members</b> — Cannot manage admins",
    }

    missing_text = "\n".join(perm_descriptions.get(p, f"❓ {p}") for p in missing)

    # Sanitize chat_id for clone owners (still show it for permission issues though)
    chat_id_display = str(chat_id) if not is_clone_owner else "[GROUP_ID]"

    text = (
        f"⚠️ <b>Permission Warning</b>\n\n"
        f"Bot is missing required permissions in group:\n"
        f"<code>{chat_id_display}</code>\n\n"
        f"<b>Missing:</b>\n{missing_text}\n\n"
        f"To fix:\n"
        f"1. Go to group settings\n"
        f"2. Administrators → Bot\n"
        f"3. Enable the missing permissions"
    )

    try:
        await bot.send_message(chat_id=owner_id, text=text, parse_mode=ParseMode.HTML)
        logger.info(f"[NOTIFIER] Sent permission warning to owner {owner_id} for chat {chat_id}")
        return True
    except Exception as e:
        logger.warning(f"[NOTIFIER] Failed to notify owner {owner_id}: {e}")
        return False


async def notify_startup_error(
    bot: Bot,
    owner_id: int,
    error_type: str,
    error_message: str,
    severity: str = "warning",
    pool=None,
) -> bool:
    """
    Send startup error notification to owner.

    Args:
        bot: Bot instance
        owner_id: Owner user ID
        error_type: Type of error (e.g., "DB_CONNECTION", "WEBHOOK")
        error_message: Detailed error message
        severity: "warning" or "critical"
        pool: Database pool for deduplication

    Returns:
        True if notification sent successfully
    """
    # Use catalog if available
    if error_type in ERROR_CATALOG:
        return await notify_owner(
            bot, owner_id, error_type, context={"message": error_message}, pool=pool
        )

    # Fallback format
    emoji = "🔴" if severity == "critical" else "⚠️"

    text = (
        f"{emoji} <b>Startup {severity.upper()}</b>\n\n"
        f"<b>Error Type:</b> {error_type}\n"
        f"<b>Message:</b>\n<code>{error_message[:500]}</code>"
    )

    try:
        await bot.send_message(chat_id=owner_id, text=text, parse_mode=ParseMode.HTML)
        return True
    except Exception as e:
        logger.error(f"[NOTIFIER] Failed to send startup error: {e}")
        return False
