"""
bot/handlers/group_approval.py

Handles clone owner tapping [Approve] or [Deny] on a group request.
Registered on the PRIMARY bot only (owner DMs come through primary bot).

Callback data format:
  grp_approve:{bot_id}:{chat_id}:{requester_id}
  grp_deny:{bot_id}:{chat_id}:{requester_id}
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

from config import settings
from db.ops.clone_groups import update_access_status, mark_group_left
from bot.registry import get as registry_get

log = logging.getLogger("group_approval")


async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    action = parts[0]  # grp_approve | grp_deny
    bot_id = int(parts[1])
    chat_id = int(parts[2])
    requester = int(parts[3])
    db_pool = context.bot_data.get("db_pool")

    if action == "grp_approve":
        if db_pool:
            async with db_pool.acquire() as db:
                await update_access_status(db, bot_id, chat_id, "active")

        # DM the requester: approved
        # We should try to send this via the clone bot if it's still in the group,
        # or via the primary bot if the user has started it.
        # The prompt says DM to requester.
        try:
            await context.bot.send_message(
                chat_id=requester,
                text=(
                    f"✅ <b>Request approved!</b>\n\n"
                    f"The bot owner approved your group. "
                    f"The bot is now active in your group.\n\n"
                    f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            log.warning(f"[APPROVAL] Could not DM requester {requester}: {e}")

        await query.edit_message_text(
            f"✅ Approved. Bot is now active in that group."
            f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}",
            parse_mode=ParseMode.HTML,
        )
        log.info(f"[APPROVAL] Approved | bot={bot_id} chat={chat_id}")

    elif action == "grp_deny":
        if db_pool:
            async with db_pool.acquire() as db:
                await update_access_status(db, bot_id, chat_id, "denied")

        # Bot leaves the group
        # We need the clone bot instance to make it leave.
        clone_app = registry_get(bot_id)
        if clone_app:
            try:
                await clone_app.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"👋 The bot owner has not approved this group. "
                        f"I'll be leaving now.\n\n"
                        f"Want your own bot? Visit @{settings.MAIN_BOT_USERNAME or settings.BOT_DISPLAY_NAME or 'the main bot'}\n\n"
                        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

            try:
                await clone_app.bot.leave_chat(chat_id)
            except Exception:
                pass
        else:
            log.warning(
                f"[APPROVAL] Could not find clone bot {bot_id} in registry to leave group {chat_id}"
            )

        if db_pool:
            async with db_pool.acquire() as db:
                await mark_group_left(db, bot_id, chat_id)

        # DM requester: denied
        try:
            await context.bot.send_message(
                chat_id=requester,
                text=(
                    f"❌ <b>Request denied.</b>\n\n"
                    f"The bot owner didn't approve your group.\n\n"
                    f"💡 Create your own free bot at @{settings.MAIN_BOT_USERNAME or settings.BOT_DISPLAY_NAME or 'the main bot'}\n\n"
                    f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"❌ Denied. Bot has left that group." f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}",
            parse_mode=ParseMode.HTML,
        )
        log.info(f"[APPROVAL] Denied | bot={bot_id} chat={chat_id}")


# Registered on PRIMARY bot only
group_approval_handler = CallbackQueryHandler(handle_approval, pattern=r"^grp_(approve|deny):")
