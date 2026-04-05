import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import ERRORS, log_action

log = logging.getLogger("[MOD_PURGE]")


async def _auto_delete(message, delay: int = 5):
    """Auto-delete a message after delay seconds."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Check if invoker is admin
    from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    message = update.effective_message
    # Get message_thread_id for topic-aware purge (forum groups)
    thread_id = message.message_thread_id

    if message.reply_to_message:
        # Purge from replied message to now
        start_id = message.reply_to_message.message_id
        end_id = message.message_id
        message_ids = list(range(start_id, end_id + 1))
    elif context.args and context.args[0].isdigit():
        count = int(context.args[0])
        count = min(count, 100)
        end_id = message.message_id
        message_ids = list(range(end_id - count, end_id + 1))
    else:
        await update.message.reply_text(
            "❌ Reply to a message or provide a number of messages to purge."
        )
        return

    # Track actual deleted count
    count_deleted = 0

    # Telegram allows deleting max 100 messages at once
    for i in range(0, len(message_ids), 100):
        batch = message_ids[i : i + 100]
        try:
            await context.bot.delete_messages(chat_id, batch)
            count_deleted += len(batch)
        except Exception:
            # Fallback to individual delete if batch fails
            for mid in batch:
                try:
                    await context.bot.delete_message(chat_id, mid)
                    count_deleted += 1
                except Exception:
                    continue  # Message doesn't exist or already deleted

    # Send confirmation with message_thread_id for forum groups
    confirm = await context.bot.send_message(
        chat_id,
        f"🧹 Purged ~{count_deleted} messages.",
        message_thread_id=thread_id,
    )

    # Auto-delete confirmation after 5 seconds
    asyncio.create_task(_auto_delete(confirm, 5))

    await log_action(
        chat_id,
        "purge",
        0,
        "N/A",
        invoker.id,
        invoker.full_name,
        f"Purged {count_deleted} messages",
    )


async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception:
        pass


async def delall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Reply to a message to delete all messages from that user."
        )
        return

    target_user = update.message.reply_to_message.from_user
    if not target_user:
        await update.message.reply_text("❌ Cannot identify user.")
        return

    msg_id = update.message.message_id
    start_id = max(1, msg_id - 200)
    deleted = 0

    for i in range(0, (msg_id - start_id), 100):
        batch = list(range(start_id + i, min(start_id + i + 100, msg_id + 1)))
        try:
            await context.bot.delete_messages(chat_id, batch)
            deleted += len(batch)
        except Exception:
            pass

    confirm = await update.message.reply_text("🗑️ Attempted to delete up to 200 recent messages.")
    await asyncio.sleep(5)
    try:
        await confirm.delete()
    except Exception:
        pass

    await log_action(
        chat_id,
        "delall",
        target_user.id,
        target_user.full_name,
        invoker.id,
        invoker.full_name,
        "Deleted all messages",
    )


async def purgeme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    msg_id = update.message.message_id
    count = 50
    if context.args and context.args[0].isdigit():
        count = min(int(context.args[0]), 100)

    start_id = max(1, msg_id - count)
    message_ids = list(range(start_id, msg_id + 1))

    deleted = 0
    for i in range(0, len(message_ids), 100):
        batch = message_ids[i : i + 100]
        try:
            await context.bot.delete_messages(chat_id, batch)
            deleted += len(batch)
        except Exception:
            for mid in batch:
                try:
                    await context.bot.delete_message(chat_id, mid)
                    deleted += 1
                except Exception:
                    pass

    confirm = await context.bot.send_message(chat_id, f"🗑️ Purged {deleted} of your messages.")
    await asyncio.sleep(5)
    try:
        await confirm.delete()
    except Exception:
        pass
