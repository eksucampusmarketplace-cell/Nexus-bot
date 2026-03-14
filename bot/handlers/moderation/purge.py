import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import ERRORS, check_permissions, log_action


async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Check if invoker is admin
    from bot.handlers.moderation.utils import RANK_ADMIN, get_user_rank

    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    message = update.effective_message
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

    # Batch delete
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
                    pass

    confirm = await update.message.reply_text(f"🗑️ Purged {count_deleted} messages")
    await asyncio.sleep(5)
    try:
        await confirm.delete()
    except Exception:
        pass

    await log_action(
        chat_id,
        "purge",
        None,
        None,
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
