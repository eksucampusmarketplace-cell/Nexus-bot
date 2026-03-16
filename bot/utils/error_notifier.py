"""
bot/utils/error_notifier.py

Error notification and health check utilities for v22.
Sends DM alerts to bot owner on permission issues or startup problems.
"""

import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def run_startup_health_check(bot: Bot, owner_id: int) -> dict:
    """
    Run health checks at bot startup.
    Returns dict with status info.
    """
    results = {
        "bot_info_ok": False,
        "db_connection_ok": False,
        "permissions_ok": False,
        "errors": []
    }
    
    try:
        me = await bot.get_me()
        results["bot_info_ok"] = bool(me and me.id)
        results["bot_username"] = me.username if me else None
    except Exception as e:
        results["errors"].append(f"Bot info fetch failed: {e}")
    
    return results


async def check_group_permissions(
    bot: Bot, 
    chat_id: int, 
    owner_id: int,
    required_permissions: list = None
) -> dict:
    """
    Check if bot has required permissions in a group.
    Sends DM to owner if permissions are missing.
    
    Args:
        bot: Bot instance
        chat_id: Group chat ID to check
        owner_id: Owner user ID to notify
        required_permissions: List of required permission strings
        
    Returns:
        Dict with permission status
    """
    if required_permissions is None:
        required_permissions = ["can_delete_messages", "can_restrict_members"]
    
    results = {
        "has_permissions": False,
        "missing": [],
        "chat_member": None
    }
    
    try:
        me = await bot.get_me()
        chat_member = await bot.get_chat_member(chat_id, me.id)
        results["chat_member"] = chat_member
        
        # Check admin status
        if chat_member.status not in ["administrator", "creator"]:
            results["missing"].append("administrator")
            await _notify_permission_issue(bot, owner_id, chat_id, results["missing"])
            return results
        
        # Check specific permissions
        for perm in required_permissions:
            if not getattr(chat_member, perm, False):
                results["missing"].append(perm)
        
        results["has_permissions"] = len(results["missing"]) == 0
        
        if results["missing"]:
            await _notify_permission_issue(bot, owner_id, chat_id, results["missing"])
            
    except Exception as e:
        logger.warning(f"Permission check failed for chat {chat_id}: {e}")
        results["error"] = str(e)
    
    return results


async def _notify_permission_issue(
    bot: Bot, 
    owner_id: int, 
    chat_id: int, 
    missing: list
) -> bool:
    """
    Send DM to owner about missing permissions.
    
    Returns True if message was sent successfully.
    """
    perm_descriptions = {
        "administrator": "🔴 <b>Admin Status</b> — Bot is not an admin",
        "can_delete_messages": "🗑 <b>Delete Messages</b> — Cannot delete spam",
        "can_restrict_members": "🔇 <b>Restrict Members</b> — Cannot mute/ban users",
        "can_pin_messages": "📌 <b>Pin Messages</b> — Cannot pin messages",
        "can_invite_users": "➕ <b>Invite Users</b> — Cannot add members",
        "can_promote_members": "⬆️ <b>Promote Members</b> — Cannot manage admins"
    }
    
    missing_text = "\n".join(
        perm_descriptions.get(p, f"❓ {p}") 
        for p in missing
    )
    
    text = (
        f"⚠️ <b>Permission Warning</b>\n\n"
        f"Bot is missing required permissions in group:\n"
        f"<code>{chat_id}</code>\n\n"
        f"<b>Missing:</b>\n{missing_text}\n\n"
        f"To fix:\n"
        f"1. Go to group settings\n"
        f"2. Administrators → Bot\n"
        f"3. Enable the missing permissions"
    )
    
    try:
        await bot.send_message(
            chat_id=owner_id,
            text=text,
            parse_mode=ParseMode.HTML
        )
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
    severity: str = "warning"
) -> bool:
    """
    Send startup error notification to owner.
    
    Args:
        bot: Bot instance
        owner_id: Owner user ID
        error_type: Type of error (e.g., "DB_CONNECTION", "WEBHOOK")
        error_message: Detailed error message
        severity: "warning" or "critical"
        
    Returns:
        True if notification sent successfully
    """
    emoji = "🔴" if severity == "critical" else "⚠️"
    
    text = (
        f"{emoji} <b>Startup {severity.upper()}</b>\n\n"
        f"<b>Error Type:</b> {error_type}\n"
        f"<b>Message:</b>\n<code>{error_message[:500]}</code>"
    )
    
    try:
        await bot.send_message(
            chat_id=owner_id,
            text=text,
            parse_mode=ParseMode.HTML
        )
        return True
    except Exception as e:
        logger.error(f"[NOTIFIER] Failed to send startup error: {e}")
        return False
