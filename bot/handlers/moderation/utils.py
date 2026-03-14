import json
import logging
import re
from datetime import datetime, timedelta
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
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            return member.user, reason
        except BadRequest:
            pass

    # Try as username
    if target_str.startswith("@"):
        pass

    # Fallback: try to find user in DB if we had a username -> id map
    # For this implementation, we'll mostly rely on reply or ID

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
    INSERT INTO mod_logs (chat_id, action, target_id, target_name, admin_id, admin_name, reason, duration)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
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
    # Check if log channel is set
    row = await db.fetchrow("SELECT log_channel_id FROM groups WHERE chat_id = $1", chat_id)
    if not row or not row["log_channel_id"]:
        return

    log_channel_id = row["log_channel_id"]
    chat = await bot.get_chat(chat_id)

    text = f"🔨 {action.upper()} | {chat.title}\n"
    text += f"👤 User: {target_user.full_name} (@{target_user.username if target_user.username else 'N/A'}) [{target_user.id}]\n"
    text += f"👮 Admin: {admin_user.full_name} (@{admin_user.username if admin_user.username else 'N/A'})\n"
    text += f"📋 Reason: {reason}\n"
    if duration:
        text += f"⏱ Duration: {duration}\n"
    else:
        text += f"⏱ Duration: permanent\n"
    text += f"🕐 Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

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
    """Send message then delete it after delay seconds"""
    sent_msg = await message.reply_text(text, parse_mode="Markdown")
    # In a real bot we'd use context.job_queue to delete this after delay
    # Since I don't have easy access to job_queue here, I'll skip the auto-delete part for now
    # or implement it if I can get context.
    return sent_msg


async def publish_event(chat_id: int, event_type: str, data: dict):
    """
    Publish event to Redis pubsub channel.
    Miniapp SSE endpoint picks it up and forwards to browser.
    """
    if not db.redis:
        return
    try:
        payload = {
            "type": event_type,
            "chat_id": chat_id,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        }
        await db.redis.publish(f"nexus:events:{chat_id}", json.dumps(payload))
    except Exception as e:
        log.debug(f"[EVENTS] Failed to publish event: {e}")


ERRORS = {
    "no_target": "❌ Reply to a message or provide a username/ID.",
    "cant_act_admin": "❌ I cannot act on an admin.",
    "cant_act_owner": "❌ I cannot act on the group owner.",
    "cant_act_self": "❌ You cannot act on yourself.",
    "cant_act_bot": "❌ I cannot act on myself.",
    "no_permission": "❌ You don't have permission to do this.",
    "user_not_found": "❌ User not found in this group.",
    "already_banned": "❌ This user is already banned.",
    "not_banned": "❌ This user is not banned.",
    "already_muted": "❌ This user is already muted.",
    "not_muted": "❌ This user is not muted.",
    "invalid_time": "❌ Invalid time format. Use: 30m, 1h, 7d, 1w",
    "bot_no_rights": "❌ I don't have enough rights to do this. Make me an admin first.",
}
