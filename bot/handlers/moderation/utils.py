import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from telegram import Bot, Update, User
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from db.client import db

log = logging.getLogger("[MOD]")

RANK_OWNER = 4
RANK_ADMIN = 3
RANK_MEMBER = 2
RANK_RESTRICTED = 1
RANK_BANNED = 0


def _make_fake_user(row) -> User:
    """Create minimal User-like object from DB row for banned/left users."""
    from telegram import User as TGUser

    return TGUser(
        id=row["user_id"],
        first_name=row.get("first_name") or "Unknown",
        is_bot=False,
        username=row.get("username"),
    )


async def resolve_target(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Tuple[Optional[User], Optional[str]]:
    """
    Resolve target user from:
    1. Reply to message -> return replied-to user
    2. First argument as @username -> resolve via bot.get_chat_member
    3. First argument as numeric ID -> resolve via bot.get_chat_member
    4. No target -> return None, show usage

    Returns (user, remaining_args_as_reason)
    """
    message = update.effective_message
    args = context.args
    chat_id = update.effective_chat.id

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        reason = " ".join(args) if args else ""
        return target_user, reason

    if not args:
        return None, None

    target_str = args[0]
    reason = " ".join(args[1:]) if len(args) > 1 else ""

    # Try as ID
    if target_str.isdigit() or (target_str.startswith("-") and target_str[1:].isdigit()):
        try:
            user_id = int(target_str)
            member = await context.bot.get_chat_member(chat_id, user_id)
            return member.user, reason
        except BadRequest:
            pass

    # Resolve @username via DB lookup
    if target_str.startswith("@"):
        username = target_str[1:]  # Remove the @ prefix
        try:
            row = await db.fetchrow(
                "SELECT user_id, first_name, username FROM users WHERE LOWER(username) = LOWER($1)",
                username,
            )
            if row:
                try:
                    member = await context.bot.get_chat_member(chat_id, row["user_id"])
                    return member.user, reason
                except BadRequest:
                    # User left but we have their ID — return a synthetic user object
                    # by fetching from users table
                    user_row = await db.fetchrow(
                        "SELECT user_id, first_name, username FROM users WHERE user_id=$1",
                        row["user_id"],
                    )
                    if user_row:
                        return _make_fake_user(user_row), reason
                    return None, f"@{username} is not in this group"
            else:
                return None, f"@{username} not found in bot database"
        except Exception as e:
            log.warning(f"resolve_target username lookup failed: {e}")
            return None, f"Could not resolve @{username}"

    return None, "User not found or invalid format."


async def get_user_rank(bot: Bot, chat_id: int, user_id: int) -> int:
    """Returns RANK_OWNER/ADMIN/MEMBER/RESTRICTED/BANNED"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status == "creator":
            return RANK_OWNER
        if member.status == "administrator":
            return RANK_ADMIN
        if member.status == "restricted":
            return RANK_RESTRICTED
        if member.status in ["left", "kicked"]:
            return RANK_BANNED
        return RANK_MEMBER
    except BadRequest:
        return RANK_MEMBER


async def check_permissions(
    bot: Bot, chat_id: int, invoker_id: int, target_id: int
) -> Tuple[bool, str]:
    """
    Full permission check.
    Returns (allowed, reason_if_not_allowed)
    """
    if invoker_id == target_id:
        return False, "cant_act_self"

    if target_id == bot.id:
        return False, "cant_act_bot"

    invoker_rank = await get_user_rank(bot, chat_id, invoker_id)
    if invoker_rank < RANK_ADMIN:
        # Check if they are a promoted admin in our DB if not Telegram admin
        # For now, stick to Telegram ranks
        return False, "no_permission"

    target_rank = await get_user_rank(bot, chat_id, target_id)

    if target_rank == RANK_OWNER:
        return False, "cant_act_owner"

    if target_rank == RANK_ADMIN and invoker_rank != RANK_OWNER:
        return False, "cant_act_admin"

    return True, ""


async def mention_user(user: User) -> str:
    """Returns @username or [Name](tg://user?id=ID) markdown link"""
    if user.username:
        return f"@{user.username}"
    return f"[{user.first_name}](tg://user?id={user.id})"


async def log_action(
    chat_id: int,
    action: str,
    target_id: int,
    target_name: str,
    admin_id: int,
    admin_name: str,
    reason: str,
    duration: str = None,
):
    """Write to mod_logs table"""
    query = """
    INSERT INTO mod_logs (
        chat_id, action, target_id, target_name, admin_id, admin_name, reason, duration
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    """
    await db.execute(
        query, chat_id, action, target_id, target_name, admin_id, admin_name, reason, duration
    )


async def notify_log_channel(
    bot: Bot,
    chat_id: int,
    action: str,
    target_user: User,
    admin_user: User,
    reason: str,
    duration: str = None,
):
    """If group has a log channel set, send formatted mod action there."""
    # Check if log channel is set in the settings JSONB
    row = await db.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
    if not row or not row["settings"]:
        return

    group_settings = row["settings"]
    if isinstance(group_settings, str):
        try:
            group_settings = json.loads(group_settings)
        except Exception:
            return
    if not isinstance(group_settings, dict):
        return
    log_channel_id = group_settings.get("log_channel")
    if not log_channel_id:
        return
    chat = await bot.get_chat(chat_id)

    text = f"🔨 {action.upper()} | {chat.title}\n"
    username = target_user.username or "N/A"
    admin_username = admin_user.username or "N/A"
    text += f"👤 User: {target_user.full_name} (@{username}) [{target_user.id}]\n"
    text += f"👮 Admin: {admin_user.full_name} (@{admin_username})\n"
    text += f"📋 Reason: {reason}\n"
    if duration:
        text += f"⏱ Duration: {duration}\n"
    else:
        text += "⏱ Duration: permanent\n"
    text += f"🕐 Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    try:
        await bot.send_message(log_channel_id, text)
    except Exception as e:
        log.error(f"Failed to send to log channel: {e}")


def parse_time(time_str: str) -> Optional[timedelta]:
    """
    Parse time strings like:
    "30m" -> timedelta(minutes=30)
    "1h" -> timedelta(hours=1)
    "7d" -> timedelta(days=7)
    "1w" -> timedelta(weeks=1)
    "1mo" -> timedelta(days=30)
    Returns None if invalid
    """
    if not time_str:
        return None

    match = re.match(r"^(\d+)(m|h|d|w|mo)$", time_str.lower())
    if not match:
        return None

    value, unit = match.groups()
    value = int(value)

    if unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    elif unit == "mo":
        return timedelta(days=value * 30)

    return None


async def send_and_auto_delete(message, text: str, delay: int = 30):
    """Send message then delete it after delay seconds."""
    import asyncio

    sent_msg = await message.reply_text(text, parse_mode="Markdown")

    # Bug #6 fix: Actually schedule auto-deletion
    async def _delete_later():
        await asyncio.sleep(delay)
        try:
            await sent_msg.delete()
        except Exception:
            pass  # Message may already be deleted or bot lacks permission

    asyncio.create_task(_delete_later())
    return sent_msg


class EventBus:
    """In-memory event bus for single-process deployments without Redis."""

    _handlers = {}

    @classmethod
    def subscribe(cls, chat_id: int, handler):
        if chat_id not in cls._handlers:
            cls._handlers[chat_id] = []
        cls._handlers[chat_id].append(handler)

    @classmethod
    def unsubscribe(cls, chat_id: int, handler):
        if chat_id in cls._handlers:
            cls._handlers[chat_id] = [h for h in cls._handlers[chat_id] if h != handler]

    @classmethod
    async def publish(cls, chat_id: int, event_type: str, data: dict):
        payload = {
            "type": event_type,
            "chat_id": chat_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        if chat_id in cls._handlers:
            for handler in cls._handlers[chat_id]:
                try:
                    await handler(payload)
                except Exception:
                    pass
        return payload


async def publish_event(chat_id: int, event_type: str, data: dict):
    """
    Publish event to Redis pubsub channel.
    Miniapp SSE endpoint picks it up and forwards to browser.
    Falls back to in-memory EventBus if Redis is not available.
    """
    payload = {
        "type": event_type,
        "chat_id": chat_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **data,
    }

    # Try Redis first
    if db.redis:
        try:
            await db.redis.publish(f"nexus:events:{chat_id}", json.dumps(payload))
            return
        except Exception as e:
            log.debug(f"[EVENTS] Redis publish failed: {e}")

    # Fall back to in-memory event bus
    try:
        await EventBus.publish(chat_id, event_type, data)
    except Exception as e:
        log.debug(f"[EVENTS] Failed to publish event: {e}")


from bot.utils.localization import get_locale

def get_error(key: str, lang: str = 'en', **kwargs) -> str:
    """Get a localized error message."""
    locale = get_locale(lang)
    return locale.get(key, **kwargs)
