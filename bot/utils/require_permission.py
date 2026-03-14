"""
bot/utils/require_permission.py

Permission decorator for custom roles.
Checks if user has required permission through custom roles or is Telegram admin.
"""

from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

# Permission constants
PERMISSIONS = {
    # Moderation
    "warn_members",
    "mute_members",
    "kick_members",
    "ban_members",
    "unban_members",
    "purge_messages",
    # Content
    "pin_messages",
    "post_channel",
    "schedule_posts",
    # Admin
    "manage_roles",
    "view_analytics",
    "export_data",
    "manage_webhooks",
    "manage_automod",
    "manage_games",
}


async def has_permission(user_id: int, chat_id: int, perm: str) -> bool:
    """
    Check if user has a specific permission through custom roles.

    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        perm: Permission name from PERMISSIONS

    Returns:
        True if user has permission through roles
    """
    try:
        from db.client import db
        import json

        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.permissions 
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                WHERE ur.user_id = $1 AND ur.chat_id = $2
                  AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
            """,
                user_id,
                chat_id,
            )

            for row in rows:
                perms = json.loads(row["permissions"] or "{}")
                if perms.get(perm):
                    return True
            return False
    except Exception:
        return False


def require_permission(perm: str):
    """
    Decorator to require a specific permission for a command handler.

    Telegram admins (creator/administrator) automatically pass.
    Non-admins are checked against custom roles.

    Usage:
        @require_permission('ban_members')
        async def ban_command(update, context):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            chat = update.effective_chat

            if not user or not chat:
                return

            # Telegram admins always have all permissions
            try:
                member = await context.bot.get_chat_member(chat.id, user.id)
                if member.status in ("administrator", "creator"):
                    return await func(update, context)
            except Exception:
                pass

            # Check custom roles
            if await has_permission(user.id, chat.id, perm):
                return await func(update, context)

            # Permission denied
            await update.message.reply_text(f"⛔ You need the `{perm}` permission for this.")

        return wrapper

    return decorator


def require_any_permission(*perms: str):
    """
    Decorator that allows any of the specified permissions.

    Usage:
        @require_any_permission('mute_members', 'ban_members')
        async def restrict_command(update, context):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            chat = update.effective_chat

            if not user or not chat:
                return

            # Telegram admins always pass
            try:
                member = await context.bot.get_chat_member(chat.id, user.id)
                if member.status in ("administrator", "creator"):
                    return await func(update, context)
            except Exception:
                pass

            # Check any permission
            for perm in perms:
                if await has_permission(user.id, chat.id, perm):
                    return await func(update, context)

            # Permission denied
            perms_str = ", ".join(f"`{p}`" for p in perms)
            await update.message.reply_text(f"⛔ You need one of these permissions: {perms_str}")

        return wrapper

    return decorator
