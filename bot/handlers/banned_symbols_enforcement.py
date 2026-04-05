"""
bot/handlers/banned_symbols_enforcement.py

Enforcement handler for banned symbols in usernames.
Checks new members when they join and takes action if their username
contains any banned symbols.

This is an UltraPro feature (Pro and Unlimited plans only).
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.billing.billing_helpers import get_owner_plan
from db.ops.banned_symbols import check_username_against_symbols, log_banned_symbol_match
from db.client import db

log = logging.getLogger("[BANNED_SYMBOLS_ENFORCE]")

# Minimum plan required for this feature
MIN_PLAN_FOR_SYMBOLS = ["pro", "unlimited"]


async def check_new_member_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if a new member's username contains banned symbols.
    Returns True if user was removed (to skip further processing), False otherwise.
    Works with both ChatMemberHandler and MessageHandler (new_chat_members).
    """
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return False

    chat_id = chat.id

    # Check if feature is available for this group (UltraPro only)
    try:
        get_owner_id = context.bot_data.get("get_owner_id")
        if get_owner_id:
            owner_id = await get_owner_id(context.bot.id)
        else:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT owner_user_id FROM bots WHERE is_primary = TRUE LIMIT 1"
                )
                owner_id = row["owner_user_id"] if row else None

        if not owner_id:
            return False

        plan = await get_owner_plan(db.pool, owner_id)
        if plan not in MIN_PLAN_FOR_SYMBOLS:
            return False  # Feature not available for this plan

    except Exception as e:
        log.debug(f"Could not check plan for banned symbols: {e}")
        return False

    # Get the new member(s) - support both ChatMemberHandler and MessageHandler formats
    members = []

    if update.chat_member:
        # ChatMemberHandler format
        members = [update.chat_member.new_chat_member.user]
    elif update.message and update.message.new_chat_members:
        # MessageHandler format (new_chat_members)
        members = update.message.new_chat_members
    else:
        return False

    for member in members:
        # Skip bots
        if member.is_bot:
            continue

        username = member.username or ""
        first_name = member.first_name or ""
        full_name = f"{first_name} {member.last_name or ''}".strip()

        # Check against banned symbols
        match = await check_username_against_symbols(chat_id, username)
        if not match:
            # Also check first name if no username match
            match = await check_username_against_symbols(chat_id, full_name)

        if match:
            symbol = match["symbol"]
            action = match["action"]
            user_id = member.id

            try:
                # Take action
                if action == "ban":
                    await context.bot.ban_chat_member(chat_id, user_id)
                    action_emoji = "🚫"
                    action_text = "banned"
                elif action == "kick":
                    await context.bot.unban_chat_member(chat_id, user_id)
                    action_emoji = "👢"
                    action_text = "kicked"
                elif action == "mute":
                    await context.bot.restrict_chat_member(
                        chat_id, user_id, permissions={"can_send_messages": False}
                    )
                    action_emoji = "🔇"
                    action_text = "muted"
                else:
                    action = "ban"  # Default fallback
                    await context.bot.ban_chat_member(chat_id, user_id)
                    action_emoji = "🚫"
                    action_text = "banned"

                # Log the match
                await log_banned_symbol_match(
                    chat_id, user_id, username or full_name, symbol, action
                )

                # Notify the group
                name_display = f"@{username}" if username else full_name
                notification_text = (
                    f"{action_emoji} <b>Banned Symbol Detected</b>\n\n"
                    f"User: {name_display}\n"
                    f"Matched symbol: <code>{symbol}</code>\n"
                    f"Action: <b>{action_text}</b>\n\n"
                    f"<i>This is an UltraPro automated filter.</i>"
                )

                # Handle both ChatMemberHandler and MessageHandler formats
                if update.message:
                    await update.message.reply_text(notification_text, parse_mode="HTML")
                else:
                    await context.bot.send_message(chat_id, notification_text, parse_mode="HTML")

                log.info(
                    f"[BANNED_SYMBOLS] {action_text} user {user_id} in chat {chat_id} "
                    f"for symbol '{symbol}'"
                )
                return True  # User was removed

            except Exception as e:
                log.error(f"Failed to take action on banned symbol match: {e}")
                continue

    return False  # No action taken


async def check_member_username_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if an existing member changed their username to contain banned symbols.
    Called when a user's profile changes.
    Returns True if user was removed, False otherwise.
    """
    chat_member = update.chat_member
    if not chat_member:
        return False

    chat = chat_member.chat
    if not chat or chat.type == "private":
        return False

    chat_id = chat.id
    user = chat_member.new_chat_member.user

    # Only check if user is a member (not if they're leaving)
    if chat_member.new_chat_member.status != "member":
        return False

    # Check if feature is available (UltraPro only)
    try:
        get_owner_id = context.bot_data.get("get_owner_id")
        if get_owner_id:
            owner_id = await get_owner_id(context.bot.id)
        else:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT owner_user_id FROM bots WHERE is_primary = TRUE LIMIT 1"
                )
                owner_id = row["owner_user_id"] if row else None

        if not owner_id:
            return False

        plan = await get_owner_plan(db.pool, owner_id)
        if plan not in MIN_PLAN_FOR_SYMBOLS:
            return False

    except Exception as e:
        log.debug(f"Could not check plan for banned symbols: {e}")
        return False

    # Check the user's username
    username = user.username or ""
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    # Check against banned symbols
    match = await check_username_against_symbols(chat_id, username)
    if not match:
        match = await check_username_against_symbols(chat_id, full_name)

    if match:
        symbol = match["symbol"]
        action = match["action"]
        user_id = user.id

        try:
            # Take action
            if action == "ban":
                await context.bot.ban_chat_member(chat_id, user_id)
                action_emoji = "🚫"
                action_text = "banned"
            elif action == "kick":
                await context.bot.unban_chat_member(chat_id, user_id)
                action_emoji = "👢"
                action_text = "kicked"
            elif action == "mute":
                await context.bot.restrict_chat_member(
                    chat_id, user_id, permissions={"can_send_messages": False}
                )
                action_emoji = "🔇"
                action_text = "muted"
            else:
                action = "ban"
                await context.bot.ban_chat_member(chat_id, user_id)
                action_emoji = "🚫"
                action_text = "banned"

            # Log the match
            await log_banned_symbol_match(
                chat_id, user_id, username or full_name, symbol, action
            )

            # Notify the group
            name_display = f"@{username}" if username else full_name
            await context.bot.send_message(
                chat_id,
                f"{action_emoji} <b>Banned Symbol Detected</b>\n\n"
                f"User {name_display} changed their name to include a banned symbol.\n"
                f"Matched symbol: <code>{symbol}</code>\n"
                f"Action: <b>{action_text}</b>\n\n"
                f"<i>This is an UltraPro automated filter.</i>",
                parse_mode="HTML"
            )

            log.info(
                f"[BANNED_SYMBOLS] {action_text} user {user_id} in chat {chat_id} "
                f"for username change with symbol '{symbol}'"
            )
            return True

        except Exception as e:
            log.error(f"Failed to take action on banned symbol match: {e}")

    return False
