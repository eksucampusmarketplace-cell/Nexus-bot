"""
bot/handlers/sangmata.py

Sangmata - Name/Username History Tracker v21
Tracks first name, last name, username changes passively per message.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from telegram import Update
from telegram.ext import ChatMemberHandler, ContextTypes, CommandHandler, MessageHandler, filters

from bot.utils.permissions import is_admin

log = logging.getLogger("sangmata")


async def track_name_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Track name changes passively by checking every message.
    This runs on every message to detect changes.
    """
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    
    if not message or not user or not chat:
        return
    
    # Skip bots
    if user.is_bot:
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    if not db:
        return
    
    # Only track in groups where it's enabled
    if chat.type in ["group", "supergroup"]:
        try:
            async with db.acquire() as conn:
                # Check if name history tracking is enabled for this group
                history_enabled = await conn.fetchval(
                    "SELECT name_history_enabled FROM groups WHERE chat_id = $1",
                    chat.id
                )
                if not history_enabled:
                    return
        except Exception:
            # If we can't check, assume disabled to be safe
            return
    
    try:
        async with db.acquire() as conn:
            # Check if user has opted out
            optout = await conn.fetchval(
                "SELECT 1 FROM user_history_optout WHERE user_id = $1",
                user.id
            )
            if optout:
                return
            
            # Get last snapshot (direct lookup - no ORDER BY needed with unique constraint)
            last_snapshot = await conn.fetchrow(
                """SELECT first_name, last_name, username 
                   FROM user_snapshots 
                   WHERE user_id = $1 AND source_chat_id = $2""",
                user.id, chat.id
            )
            
            current_first = user.first_name or ""
            current_last = user.last_name or ""
            current_username = user.username or ""

            # Check for changes (normalize NULL from DB to empty string for comparison)
            if last_snapshot:
                prev_first = last_snapshot["first_name"] or ""
                prev_last = last_snapshot["last_name"] or ""
                prev_username = last_snapshot["username"] or ""
                changed = (
                    prev_first != current_first or
                    prev_last != current_last or
                    prev_username != current_username
                )

                if not changed:
                    return

                # Record what changed
                changes = []
                if prev_first != current_first:
                    changes.append(f"first_name: {prev_first} → {current_first}")
                if prev_last != current_last:
                    changes.append(f"last_name: {prev_last} → {current_last}")
                if prev_username != current_username:
                    old_un = prev_username or "(none)"
                    new_un = current_username or "(none)"
                    changes.append(f"username: @{old_un} → @{new_un}")

                # Log to history with both old and new values
                await conn.execute(
                    """INSERT INTO user_name_history
                       (user_id, first_name, last_name, username, source_chat_id,
                        old_first_name, old_last_name, old_username)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    user.id, current_first, current_last, current_username, chat.id,
                    prev_first, prev_last, prev_username
                )

                log.debug(f"[SANGMATA] Change detected for {user.id}: {'; '.join(changes)}")
            
            # Create/update snapshot using upsert (NH-01 fix: ON CONFLICT to prevent crashes)
            snapshot_id = await conn.fetchval(
                """INSERT INTO user_snapshots 
                   (user_id, first_name, last_name, username, source_chat_id)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (user_id, source_chat_id) DO UPDATE
                     SET first_name = EXCLUDED.first_name,
                         last_name  = EXCLUDED.last_name,
                         username   = EXCLUDED.username,
                         captured_at = NOW()
                   RETURNING id""",
                user.id, current_first, current_last, current_username, chat.id
            )
            
            # Update the history entry with snapshot_id
            await conn.execute(
                """UPDATE user_name_history SET snapshot_id = $1 
                   WHERE user_id = $2 AND snapshot_id IS NULL""",
                snapshot_id, user.id
            )
            
    except Exception as e:
        log.error(f"[SANGMATA] Tracking error for user {user.id}: {e}")


async def track_name_change_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Track name changes from chat_member updates (ChatMemberHandler).
    This catches name changes even when users don't send messages.
    """
    change = update.chat_member
    if not change:
        return
    
    old_user = change.old_chat_member.user
    new_user = change.new_chat_member.user
    chat = change.chat
    
    # Skip bots
    if old_user.is_bot or new_user.is_bot:
        return
    
    # Only track in groups
    if chat.type not in ["group", "supergroup"]:
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    if not db:
        return
    
    # Check if name/username actually changed
    name_changed = (
        old_user.first_name != new_user.first_name or
        old_user.last_name != new_user.last_name or
        old_user.username != new_user.username
    )
    if not name_changed:
        return
    
    # Check if tracking is enabled for this group
    try:
        async with db.acquire() as conn:
            enabled = await conn.fetchval(
                "SELECT name_history_enabled FROM groups WHERE chat_id = $1", chat.id
            )
            if not enabled:
                return
    except Exception:
        return
    
    # Check if user has opted out
    try:
        async with db.acquire() as conn:
            optout = await conn.fetchval(
                "SELECT 1 FROM user_history_optout WHERE user_id = $1",
                new_user.id
            )
            if optout:
                return
    except Exception:
        pass
    
    # Record the name change
    try:
        async with db.acquire() as conn:
            # Record what changed
            changes = []
            if old_user.first_name != new_user.first_name:
                changes.append(f"first_name: {old_user.first_name} → {new_user.first_name}")
            if old_user.last_name != new_user.last_name:
                changes.append(f"last_name: {old_user.last_name} → {new_user.last_name}")
            if old_user.username != new_user.username:
                old_un = old_user.username or "(none)"
                new_un = new_user.username or "(none)"
                changes.append(f"username: @{old_un} → @{new_un}")
            
            # Log to history with both old and new values
            await conn.execute(
                """INSERT INTO user_name_history
                   (user_id, first_name, last_name, username, source_chat_id,
                    old_first_name, old_last_name, old_username, changed_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())""",
                new_user.id,
                new_user.first_name or "",
                new_user.last_name or "",
                new_user.username or "",
                chat.id,
                old_user.first_name or "",
                old_user.last_name or "",
                old_user.username or ""
            )
            
            # Update/create snapshot
            await conn.execute(
                """INSERT INTO user_snapshots 
                   (user_id, first_name, last_name, username, source_chat_id)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (user_id, source_chat_id) DO UPDATE
                   SET first_name = EXCLUDED.first_name,
                       last_name = EXCLUDED.last_name,
                       username = EXCLUDED.username,
                       captured_at = NOW()""",
                new_user.id,
                new_user.first_name or "",
                new_user.last_name or "",
                new_user.username or "",
                chat.id
            )
            
            log.debug(f"[SANGMATA] ChatMember change detected for {new_user.id}: {'; '.join(changes)}")
    except Exception as e:
        log.error(f"[SANGMATA] ChatMember tracking error: {e}")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /history - Show name/username history for a user (admin only).
    Reply to a message or provide user ID.
    """
    chat = update.effective_chat
    message = update.effective_message
    reply = message.reply_to_message
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Use this command in a group.")
        return
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    # Get target user
    if reply:
        target_user = reply.from_user
        target_id = target_user.id
        target_name = target_user.mention_html()
    elif context.args:
        try:
            target_id = int(context.args[0])
            target_name = f"<code>{target_id}</code>"
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
            return
    else:
        await update.message.reply_text(
            "📋 <b>Name History</b>\n\n"
            "Reply to a message with <code>/history</code>\n"
            "Or use: <code>/history &lt;user_id&gt;</code>",
            parse_mode="HTML"
        )
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get history
            history = await conn.fetch(
                """SELECT first_name, last_name, username, changed_at
                   FROM user_name_history
                   WHERE user_id = $1
                   ORDER BY changed_at DESC
                   LIMIT 20""",
                target_id
            )
            
            # Get current snapshot
            current = await conn.fetchrow(
                """SELECT first_name, last_name, username
                   FROM user_snapshots
                   WHERE user_id = $1
                   ORDER BY captured_at DESC
                   LIMIT 1""",
                target_id
            )
            
            # Check optout status
            optout = await conn.fetchval(
                "SELECT 1 FROM user_history_optout WHERE user_id = $1",
                target_id
            )
        
        if not history and not current:
            await update.message.reply_text(
                f"📋 <b>No History Found</b>\n\n"
                f"User: {target_name}\n\n"
                f"No name changes recorded for this user yet.",
                parse_mode="HTML"
            )
            return
        
        lines = [f"📋 <b>Name History</b>", f"User: {target_name}"]
        
        if optout:
            lines.append("\n⚠️ <i>This user has opted out of name tracking.</i>")
        
        # Show current
        if current:
            un = f" @{current['username']}" if current["username"] else ""
            lines.append(f"\n<b>Current:</b> {current['first_name']}{un}")
        
        # Show history
        if history:
            lines.append("\n<b>History:</b>")
            for h in history[:10]:
                date_str = h["changed_at"].strftime("%Y-%m-%d %H:%M")
                un = f" @{h['username']}" if h["username"] else ""
                lines.append(f"• {date_str}: {h['first_name']}{un}")
            
            if len(history) > 10:
                lines.append(f"\n<i>...and {len(history) - 10} more entries</i>")
        
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        log.info(f"[SANGMATA] History viewed | target={target_id} by={update.effective_user.id}")
        
    except Exception as e:
        log.error(f"[SANGMATA] History failed: {e}")
        await update.message.reply_text("❌ Failed to get history.")


async def cmd_historyoptout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /historyoptout - Opt out of name history tracking (private chat only).
    """
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type != "private":
        await update.message.reply_text("❌ Use this command in private chat with me.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_history_optout (user_id, reason)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO NOTHING""",
                user.id, "User requested opt-out"
            )
        
        await update.message.reply_text(
            "✅ <b>Opt-out Complete</b>\n\n"
            "Your name changes will no longer be tracked.\n\n"
            "To opt back in, use <code>/historyoptin</code>",
            parse_mode="HTML"
        )
        log.info(f"[SANGMATA] Opt-out | user={user.id}")
        
    except Exception as e:
        log.error(f"[SANGMATA] Opt-out failed: {e}")
        await update.message.reply_text("❌ Failed to process opt-out.")


async def cmd_historyoptin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /historyoptin - Opt back into name history tracking.
    """
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type != "private":
        await update.message.reply_text("❌ Use this command in private chat.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            await conn.execute(
                "DELETE FROM user_history_optout WHERE user_id = $1",
                user.id
            )
        
        await update.message.reply_text(
            "✅ <b>Opt-in Complete</b>\n\n"
            "Your name changes will now be tracked again.",
            parse_mode="HTML"
        )
        log.info(f"[SANGMATA] Opt-in | user={user.id}")
        
    except Exception as e:
        log.error(f"[SANGMATA] Opt-in failed: {e}")
        await update.message.reply_text("❌ Failed to process opt-in.")


async def cmd_historydelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /historydelete - Delete your name history (private chat only).
    """
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type != "private":
        await update.message.reply_text("❌ Use this command in private chat with me.")
        return
    
    # Confirm with args
    if not context.args or context.args[0].lower() != "confirm":
        await update.message.reply_text(
            "⚠️ <b>Delete Name History</b>\n\n"
            "This will permanently delete all your name history data.\n\n"
            "To confirm, type:\n"
            "<code>/historydelete confirm</code>",
            parse_mode="HTML"
        )
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Delete history
            history_result = await conn.execute(
                "DELETE FROM user_name_history WHERE user_id = $1",
                user.id
            )
            
            # Delete snapshots
            snapshot_result = await conn.execute(
                "DELETE FROM user_snapshots WHERE user_id = $1",
                user.id
            )
            
            # Auto opt-out
            await conn.execute(
                """INSERT INTO user_history_optout (user_id, reason)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO NOTHING""",
                user.id, "User deleted their data"
            )
        
        await update.message.reply_text(
            "✅ <b>History Deleted</b>\n\n"
            "All your name history has been permanently deleted.\n"
            "You have also been opted out of future tracking.",
            parse_mode="HTML"
        )
        log.info(f"[SANGMATA] Data deleted | user={user.id}")
        
    except Exception as e:
        log.error(f"[SANGMATA] Delete failed: {e}")
        await update.message.reply_text("❌ Failed to delete history.")


# Handler registration
sangmata_handlers = [
    CommandHandler("history", cmd_history),
    CommandHandler("historyoptout", cmd_historyoptout),
    CommandHandler("historyoptin", cmd_historyoptin),
    CommandHandler("historydelete", cmd_historydelete),
    # Message handler for passive tracking (when users send messages)
    MessageHandler(filters.ALL & filters.ChatType.GROUPS, track_name_change),
    # ChatMember handler for tracking name changes without messages
    ChatMemberHandler(track_name_change_chat_member, ChatMemberHandler.CHAT_MEMBER),
]
