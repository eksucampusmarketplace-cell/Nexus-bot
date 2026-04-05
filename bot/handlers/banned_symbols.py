"""
bot/handlers/banned_symbols.py

Banned symbols management for username filtering (UltraPro feature).

Commands:
  /bannedsymbol <symbol>      — Add a symbol to the banned symbols list
  /bannedsymbol               — Show all banned symbols
  /unbannedsymbol <symbol>    — Remove a symbol from the banned symbols list
  /clearbannedsymbols         — Clear all banned symbols
  /bannedsymbolaction <action> [symbol] — Set action: ban|kick|mute

Available only for Pro and Unlimited plans (UltraPro).
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.moderation.utils import ERRORS, RANK_ADMIN, get_user_rank
from bot.billing.billing_helpers import get_owner_plan
from db.ops.banned_symbols import (
    get_banned_symbols,
    add_banned_symbol,
    remove_banned_symbol,
    clear_banned_symbols,
)
from db.client import db

log = logging.getLogger("[BANNED_SYMBOLS]")

DEFAULT_ACTION = "ban"
VALID_ACTIONS = ["ban", "kick", "mute"]

# Minimum plan required for this feature
MIN_PLAN_FOR_SYMBOLS = ["pro", "unlimited"]


async def _is_ultrapro_group(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, str]:
    """
    Check if the group has access to UltraPro features.
    Returns (has_access, error_message).
    """
    try:
        # Get the bot's owner
        get_owner_id = context.bot_data.get("get_owner_id")
        if get_owner_id:
            owner_id = await get_owner_id(context.bot.id)
        else:
            # Fallback: try to get from database
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT owner_user_id FROM bots WHERE is_primary = TRUE LIMIT 1"
                )
                owner_id = row["owner_user_id"] if row else None

        if not owner_id:
            return False, "❌ Could not determine bot ownership."

        plan = await get_owner_plan(db.pool, owner_id)

        if plan not in MIN_PLAN_FOR_SYMBOLS:
            return False, (
                f"⚠️ <b>UltraPro Feature</b>\n\n"
                f"Banned symbols filtering is available only for <b>Pro</b> and <b>Unlimited</b> plans.\n\n"
                f"Your current plan: <code>{plan.upper()}</code>\n"
                f"Upgrade to unlock this feature!"
            )

        return True, ""

    except Exception as e:
        log.error(f"Failed to check plan: {e}")
        return False, "❌ Could not verify plan status."


async def bannedsymbol_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add or list banned symbols."""
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Check admin permission
    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    # Check UltraPro access
    has_access, error_msg = await _is_ultrapro_group(chat_id, context)
    if not has_access:
        await update.message.reply_text(error_msg, parse_mode="HTML")
        return

    if not context.args:
        # List banned symbols
        symbols = await get_banned_symbols(chat_id)
        if not symbols:
            await update.message.reply_text(
                "📋 <b>Banned Symbols</b>\n\n"
                "No symbols are currently banned.\n\n"
                "<i>Usage: /bannedsymbol &lt;symbol&gt;</i>\n"
                "<i>Example: /bannedsymbol 🎰</i>",
                parse_mode="HTML"
            )
            return

        lines = []
        for item in symbols:
            action_emoji = {"ban": "🚫", "kick": "👢", "mute": "🔇"}.get(item["action"], "🚫")
            lines.append(f"{action_emoji} <code>{item['symbol']}</code> ({item['action']})")

        text = f"📋 <b>Banned Symbols ({len(symbols)}):</b>\n\n"
        text += "\n".join(lines)
        text += "\n\n<i>Users with these symbols in their username will be removed automatically.</i>"
        await update.message.reply_text(text, parse_mode="HTML")
        return

    # Add new symbol
    symbol = " ".join(context.args)
    if not symbol.strip():
        await update.message.reply_text("❓ Usage: /bannedsymbol <symbol>")
        return

    try:
        await add_banned_symbol(chat_id, symbol.strip(), invoker.id, DEFAULT_ACTION)
        await update.message.reply_text(
            f"✅ Added banned symbol: <code>{symbol}</code>\n"
            f"Action: <b>{DEFAULT_ACTION}</b>\n\n"
            f"Users with this symbol in their username will be {DEFAULT_ACTION}ned on join.",
            parse_mode="HTML"
        )
        log.info(f"[BANNED_SYMBOLS] Added '{symbol}' to chat {chat_id}")
    except Exception as e:
        log.error(f"Failed to add banned symbol: {e}")
        await update.message.reply_text(f"❌ Failed to add symbol: {e}")


async def unbannedsymbol_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a banned symbol."""
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Check admin permission
    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    # Check UltraPro access
    has_access, error_msg = await _is_ultrapro_group(chat_id, context)
    if not has_access:
        await update.message.reply_text(error_msg, parse_mode="HTML")
        return

    if not context.args:
        await update.message.reply_text("❓ Usage: /unbannedsymbol <symbol>")
        return

    symbol = " ".join(context.args).strip()

    try:
        removed = await remove_banned_symbol(chat_id, symbol)
        if not removed:
            await update.message.reply_text(
                f"❌ <code>{symbol}</code> is not in the banned symbols list.",
                parse_mode="HTML"
            )
            return

        await update.message.reply_text(
            f"✅ Removed banned symbol: <code>{symbol}</code>",
            parse_mode="HTML"
        )
        log.info(f"[BANNED_SYMBOLS] Removed '{symbol}' from chat {chat_id}")
    except Exception as e:
        log.error(f"Failed to remove banned symbol: {e}")
        await update.message.reply_text(f"❌ Failed to remove symbol: {e}")


async def clearbannedsymbols_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all banned symbols."""
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Check admin permission
    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    # Check UltraPro access
    has_access, error_msg = await _is_ultrapro_group(chat_id, context)
    if not has_access:
        await update.message.reply_text(error_msg, parse_mode="HTML")
        return

    try:
        await clear_banned_symbols(chat_id)
        await update.message.reply_text("✅ All banned symbols have been cleared.")
        log.info(f"[BANNED_SYMBOLS] Cleared all symbols from chat {chat_id}")
    except Exception as e:
        log.error(f"Failed to clear banned symbols: {e}")
        await update.message.reply_text(f"❌ Failed to clear symbols: {e}")


async def bannedsymbolaction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set action for banned symbols (ban/kick/mute)."""
    chat_id = update.effective_chat.id
    invoker = update.effective_user

    # Check admin permission
    if await get_user_rank(context.bot, chat_id, invoker.id) < RANK_ADMIN:
        await update.message.reply_text(ERRORS["no_permission"])
        return

    # Check UltraPro access
    has_access, error_msg = await _is_ultrapro_group(chat_id, context)
    if not has_access:
        await update.message.reply_text(error_msg, parse_mode="HTML")
        return

    if not context.args or context.args[0].lower() not in VALID_ACTIONS:
        await update.message.reply_text(
            f"❓ Usage: /bannedsymbolaction <action> [symbol]\n"
            f"Actions: {', '.join(VALID_ACTIONS)}\n\n"
            f"<i>Without a symbol, sets the default action.</i>",
            parse_mode="HTML"
        )
        return

    action = context.args[0].lower()
    symbol = context.args[1] if len(context.args) > 1 else None

    if symbol:
        # Update specific symbol's action
        try:
            from db.client import db
            async with db.pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE banned_symbols SET action = $1 WHERE chat_id = $2 AND symbol = $3",
                    action, chat_id, symbol
                )
                if "UPDATE 0" in result:
                    await update.message.reply_text(
                        f"❌ <code>{symbol}</code> is not in the banned symbols list.",
                        parse_mode="HTML"
                    )
                    return

            await update.message.reply_text(
                f"✅ Action for <code>{symbol}</code> set to: <b>{action}</b>",
                parse_mode="HTML"
            )
            log.info(f"[BANNED_SYMBOLS] Set action '{action}' for '{symbol}' in chat {chat_id}")
        except Exception as e:
            log.error(f"Failed to set symbol action: {e}")
            await update.message.reply_text(f"❌ Failed to set action: {e}")
    else:
        # Set default action in settings
        try:
            import json
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id = $1", chat_id)
                settings = row["settings"] if row else {}
                if isinstance(settings, str):
                    try:
                        settings = json.loads(settings)
                    except Exception:
                        settings = {}

                if "banned_symbols" not in settings:
                    settings["banned_symbols"] = {}
                settings["banned_symbols"]["default_action"] = action

                await conn.execute(
                    "UPDATE groups SET settings = $1::jsonb WHERE chat_id = $2",
                    json.dumps(settings), chat_id
                )

            await update.message.reply_text(
                f"✅ Default banned symbols action set to: <b>{action}</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            log.error(f"Failed to set default action: {e}")
            await update.message.reply_text(f"❌ Failed to set default action: {e}")
