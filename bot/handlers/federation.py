"""
bot/handlers/federation.py

TrustNet (Federation) System - v21
Full cross-group trust network with 20 commands.
Aliases: /fed* and /trust* both work.
"""

import logging
import re
import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler

from bot.utils.permissions import is_admin
from bot.logging.log_channel import log_event

log = logging.getLogger("federation")


def generate_invite_code() -> str:
    """Generate a unique federation invite code."""
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    return f"FED-{code}"


async def cmd_newtrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/newtrust <name> - Create a new TrustNet (owner only, private chat)."""
    user = update.effective_user
    chat = update.effective_chat
    
    # Must be in private chat
    if chat.type != "private":
        await update.message.reply_text("❌ Create TrustNets in private chat with me.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🌐 <b>Create TrustNet</b>\n\n"
            "Usage: <code>/newtrust Network Name</code>\n\n"
            "A TrustNet lets you share bans across multiple groups.",
            parse_mode="HTML"
        )
        return
    
    name = " ".join(context.args)
    if len(name) > 50:
        await update.message.reply_text("❌ Name too long (max 50 characters).")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    invite_code = generate_invite_code()
    
    try:
        async with db.acquire() as conn:
            # Create federation
            fed_id = await conn.fetchval(
                """INSERT INTO federations (owner_id, name, invite_code)
                   VALUES ($1, $2, $3) RETURNING id""",
                user.id, name, invite_code
            )
        
        await update.message.reply_text(
            f"🌐 <b>TrustNet Created!</b>\n\n"
            f"Name: <b>{name}</b>\n"
            f"ID: <code>{fed_id}</code>\n"
            f"Invite: <code>{invite_code}</code>\n\n"
            f"Share this invite code with group owners to join.\n"
            f"Use <code>/myfeds</code> to manage your networks.",
            parse_mode="HTML"
        )
        log.info(f"[FED] Created | id={fed_id} owner={user.id} name={name}")
        
    except Exception as e:
        log.error(f"[FED] Create failed: {e}")
        await update.message.reply_text("❌ Failed to create TrustNet. Please try again.")


async def cmd_jointrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/jointrust <code> - Join a TrustNet using invite code (group owner only)."""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Use this command in a group.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🌐 <b>Join TrustNet</b>\n\n"
            "Usage: <code>/jointrust FED-XXXXXXXX</code>\n\n"
            "You must be the group owner to join.",
            parse_mode="HTML"
        )
        return
    
    invite_code = context.args[0].upper()
    if not re.match(r'^FED-[A-Z0-9]{8}$', invite_code):
        await update.message.reply_text("❌ Invalid invite code format. Use: FED-XXXXXXXX")
        return
    
    # Check if user is group owner
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status != "creator":
            await update.message.reply_text("❌ Only the group owner can join a TrustNet.")
            return
    except Exception:
        await update.message.reply_text("❌ Could not verify ownership.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Find federation
            fed = await conn.fetchrow(
                "SELECT id, name, owner_id FROM federations WHERE invite_code = $1",
                invite_code
            )
            
            if not fed:
                await update.message.reply_text("❌ Invalid invite code.")
                return
            
            # Check if already joined
            existing = await conn.fetchval(
                "SELECT 1 FROM federation_members WHERE federation_id = $1 AND chat_id = $2",
                fed["id"], chat.id
            )
            if existing:
                await update.message.reply_text("❌ This group is already in this TrustNet.")
                return
            
            # Add to federation
            await conn.execute(
                """INSERT INTO federation_members (federation_id, chat_id, joined_by)
                   VALUES ($1, $2, $3)""",
                fed["id"], chat.id, user.id
            )
        
        await update.message.reply_text(
            f"✅ <b>Joined TrustNet!</b>\n\n"
            f"Network: <b>{fed['name']}</b>\n"
            f"Owner: <code>{fed['owner_id']}</code>\n\n"
            f"Bans will now be shared across all groups in this network.",
            parse_mode="HTML"
        )
        log.info(f"[FED] Joined | fed={fed['id']} chat={chat.id} user={user.id}")
        
    except Exception as e:
        log.error(f"[FED] Join failed: {e}")
        await update.message.reply_text("❌ Failed to join TrustNet.")


async def cmd_leavetrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/leavetrust - Leave the current TrustNet (group owner only)."""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Use this command in a group.")
        return
    
    # Check ownership
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status != "creator":
            await update.message.reply_text("❌ Only the group owner can leave a TrustNet.")
            return
    except Exception:
        await update.message.reply_text("❌ Could not verify ownership.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Find memberships
            memberships = await conn.fetch(
                """SELECT fm.id, fm.federation_id, f.name 
                   FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1""",
                chat.id
            )
            
            if not memberships:
                await update.message.reply_text("❌ This group is not in any TrustNet.")
                return
            
            # Leave all (usually just one)
            for m in memberships:
                await conn.execute(
                    "DELETE FROM federation_members WHERE id = $1",
                    m["id"]
                )
            
            names = ", ".join([m["name"] for m in memberships])
        
        await update.message.reply_text(
            f"✅ <b>Left TrustNet(s)</b>\n\n"
            f"Networks: <b>{names}</b>\n\n"
            f"Note: Existing bans remain in effect.",
            parse_mode="HTML"
        )
        log.info(f"[FED] Left | chat={chat.id} user={user.id}")
        
    except Exception as e:
        log.error(f"[FED] Leave failed: {e}")
        await update.message.reply_text("❌ Failed to leave TrustNet.")


async def cmd_trustinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/trustinfo - Show this group's TrustNet memberships (any admin)."""
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Use this command in a group.")
        return
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            memberships = await conn.fetch(
                """SELECT f.id, f.name, f.owner_id, f.invite_code, fm.joined_at,
                          (SELECT COUNT(*) FROM federation_members WHERE federation_id = f.id) as group_count,
                          (SELECT COUNT(*) FROM federation_bans WHERE federation_id = f.id) as ban_count
                   FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1""",
                chat.id
            )
        
        if not memberships:
            await update.message.reply_text(
                "🌐 <b>No TrustNet Membership</b>\n\n"
                "This group is not part of any TrustNet.\n"
                "Use <code>/jointrust &lt;code&gt;</code> to join one.",
                parse_mode="HTML"
            )
            return
        
        lines = ["🌐 <b>TrustNet Memberships</b>\n"]
        for m in memberships:
            lines.append(
                f"\n<b>{m['name']}</b>\n"
                f"  Groups: {m['group_count']} | Shared bans: {m['ban_count']}\n"
                f"  Joined: {m['joined_at'].strftime('%Y-%m-%d')}"
            )
        
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        
    except Exception as e:
        log.error(f"[FED] Info failed: {e}")
        await update.message.reply_text("❌ Failed to get TrustNet info.")


async def cmd_myfeds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/myfeds - List all TrustNets you own with invite codes (private chat)."""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type != "private":
        await update.message.reply_text("❌ Use this command in private chat.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            feds = await conn.fetch(
                """SELECT f.id, f.name, f.invite_code, f.created_at,
                          (SELECT COUNT(*) FROM federation_members WHERE federation_id = f.id) as group_count,
                          (SELECT COUNT(*) FROM federation_bans WHERE federation_id = f.id) as ban_count
                   FROM federations f
                   WHERE f.owner_id = $1
                   ORDER BY f.created_at DESC""",
                user.id
            )
        
        if not feds:
            await update.message.reply_text(
                "🌐 <b>Your TrustNets</b>\n\n"
                "You don't own any TrustNets yet.\n"
                "Create one with <code>/newtrust &lt;name&gt;</code>",
                parse_mode="HTML"
            )
            return
        
        lines = ["🌐 <b>Your TrustNets</b>\n"]
        for f in feds:
            lines.append(
                f"\n<b>{f['name']}</b>\n"
                f"  Invite: <code>{f['invite_code']}</code>\n"
                f"  Groups: {f['group_count']} | Bans: {f['ban_count']}\n"
                f"  Created: {f['created_at'].strftime('%Y-%m-%d')}"
            )
        
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        
    except Exception as e:
        log.error(f"[FED] Myfeds failed: {e}")
        await update.message.reply_text("❌ Failed to get your TrustNets.")


async def cmd_fedchats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fedchats <net-id> - List all groups in a specific TrustNet (owner only)."""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Usage: <code>/fedchats &lt;federation-id&gt;</code>", parse_mode="HTML")
        return
    
    fed_id = context.args[0]
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Check ownership
            fed = await conn.fetchrow(
                "SELECT name, owner_id FROM federations WHERE id = $1",
                fed_id
            )
            
            if not fed:
                await update.message.reply_text("❌ TrustNet not found.")
                return
            
            if fed["owner_id"] != user.id:
                await update.message.reply_text("❌ You don't own this TrustNet.")
                return
            
            # Get groups
            groups = await conn.fetch(
                """SELECT fm.chat_id, fm.joined_at, g.title
                   FROM federation_members fm
                   LEFT JOIN groups g ON g.chat_id = fm.chat_id
                   WHERE fm.federation_id = $1
                   ORDER BY fm.joined_at DESC""",
                fed_id
            )
        
        if not groups:
            await update.message.reply_text("No groups in this TrustNet yet.")
            return
        
        lines = [f"🌐 <b>{fed['name']}</b> - Groups ({len(groups)})\n"]
        for g in groups:
            title = g["title"] or f"Chat {g['chat_id']}"
            lines.append(f"• {title}")
        
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        
    except Exception as e:
        log.error(f"[FED] Fedchats failed: {e}")
        await update.message.reply_text("❌ Failed to get group list.")


async def cmd_trustban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/trustban [reason] - Ban a user across all TrustNet groups (fed admin)."""
    user = update.effective_user
    chat = update.effective_chat
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    message = update.effective_message
    reply = message.reply_to_message
    
    if not reply:
        await update.message.reply_text("Reply to a message to ban that user across the TrustNet.")
        return
    
    target = reply.from_user
    reason = " ".join(context.args) if context.args else "No reason provided"
    
    if target.id == context.bot.id:
        await update.message.reply_text("❌ I can't ban myself.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get federations this group is in
            feds = await conn.fetch(
                """SELECT f.id, f.name, f.ban_mode
                   FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1""",
                chat.id
            )
            
            if not feds:
                await update.message.reply_text("❌ This group is not in any TrustNet.")
                return
            
            # Check if user is federation admin
            is_fed_admin = False
            for fed in feds:
                admin_check = await conn.fetchval(
                    """SELECT 1 FROM federation_admins 
                       WHERE federation_id = $1 AND user_id = $2""",
                    fed["id"], user.id
                )
                if admin_check or fed.get("owner_id") == user.id:
                    is_fed_admin = True
                    break
            
            if not is_fed_admin:
                await update.message.reply_text("❌ You must be a TrustNet admin to use this command.")
                return
            
            banned_count = 0
            for fed in feds:
                # Add to federation bans
                await conn.execute(
                    """INSERT INTO federation_bans (federation_id, user_id, reason, banned_by)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (federation_id, user_id) DO UPDATE 
                       SET reason = EXCLUDED.reason, banned_by = EXCLUDED.banned_by, banned_at = NOW()""",
                    fed["id"], target.id, reason, user.id
                )
                
                # Get all groups in federation and ban
                groups = await conn.fetch(
                    "SELECT chat_id FROM federation_members WHERE federation_id = $1",
                    fed["id"]
                )
                
                for g in groups:
                    try:
                        await context.bot.ban_chat_member(g["chat_id"], target.id)
                        banned_count += 1
                    except Exception:
                        pass  # Bot might not be admin in all groups
            
            # Log action
            await log_event(
                bot=context.bot,
                db=db,
                chat_id=chat.id,
                event_type="federation_ban",
                actor=user,
                target=target,
                details={"reason": reason, "groups_affected": banned_count},
                chat_title=chat.title or ""
            )
        
        await update.message.reply_text(
            f"🌐 <b>Federation Ban Applied</b>\n\n"
            f"User: {target.mention_html()}\n"
            f"Reason: {reason}\n"
            f"Affected: {banned_count} groups",
            parse_mode="HTML"
        )
        log.info(f"[FED] Ban | target={target.id} by={user.id} feds={len(feds)}")
        
    except Exception as e:
        log.error(f"[FED] Ban failed: {e}")
        await update.message.reply_text("❌ Failed to apply federation ban.")


async def cmd_sfban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/sfban [reason] - Silent ban (no notification to other groups)."""
    # Similar to trustban but with silent flag
    user = update.effective_user
    chat = update.effective_chat
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    message = update.effective_message
    reply = message.reply_to_message
    
    if not reply:
        await update.message.reply_text("Reply to a message to silently ban that user.")
        return
    
    target = reply.from_user
    reason = " ".join(context.args) if context.args else "No reason provided"
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            feds = await conn.fetch(
                """SELECT f.id FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1""",
                chat.id
            )
            
            for fed in feds:
                await conn.execute(
                    """INSERT INTO federation_bans (federation_id, user_id, reason, banned_by, silent)
                       VALUES ($1, $2, $3, $4, TRUE)
                       ON CONFLICT (federation_id, user_id) DO UPDATE 
                       SET silent = TRUE, reason = EXCLUDED.reason""",
                    fed["id"], target.id, reason, user.id
                )
        
        await update.message.reply_text(
            f"🤫 <b>Silent Federation Ban Applied</b>\n\n"
            f"User: {target.mention_html()}\n"
            f"Reason: {reason}\n"
            f"No notifications were sent.",
            parse_mode="HTML"
        )
        log.info(f"[FED] Silent ban | target={target.id} by={user.id}")
        
    except Exception as e:
        log.error(f"[FED] Silent ban failed: {e}")
        await update.message.reply_text("❌ Failed to apply silent ban.")


async def cmd_trustunban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/trustunban <user_id> - Remove a federation ban."""
    user = update.effective_user
    chat = update.effective_chat
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: <code>/trustunban &lt;user_id&gt;</code>", parse_mode="HTML")
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get federations
            feds = await conn.fetch(
                """SELECT f.id FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1""",
                chat.id
            )
            
            unbanned_count = 0
            for fed in feds:
                # Remove ban
                result = await conn.execute(
                    "DELETE FROM federation_bans WHERE federation_id = $1 AND user_id = $2",
                    fed["id"], target_id
                )
                
                if result != "DELETE 0":
                    unbanned_count += 1
                    # Unban in all groups
                    groups = await conn.fetch(
                        "SELECT chat_id FROM federation_members WHERE federation_id = $1",
                        fed["id"]
                    )
                    for g in groups:
                        try:
                            await context.bot.unban_chat_member(g["chat_id"], target_id)
                        except Exception:
                            pass
            
            if unbanned_count == 0:
                await update.message.reply_text("❌ User was not banned in any TrustNet.")
                return
        
        await update.message.reply_text(
            f"✅ <b>Federation Unban</b>\n\n"
            f"User ID: <code>{target_id}</code>\n"
            f"Removed from {unbanned_count} TrustNet(s).",
            parse_mode="HTML"
        )
        log.info(f"[FED] Unban | target={target_id} by={user.id}")
        
    except Exception as e:
        log.error(f"[FED] Unban failed: {e}")
        await update.message.reply_text("❌ Failed to unban user.")


async def cmd_trustbans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/trustbans - List all active bans in this group's TrustNets."""
    chat = update.effective_chat
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            bans = await conn.fetch(
                """SELECT fb.user_id, fb.reason, fb.banned_at, fb.silent, f.name
                   FROM federation_bans fb
                   JOIN federations f ON f.id = fb.federation_id
                   JOIN federation_members fm ON fm.federation_id = f.id
                   WHERE fm.chat_id = $1
                   ORDER BY fb.banned_at DESC
                   LIMIT 20""",
                chat.id
            )
        
        if not bans:
            await update.message.reply_text("✅ No active federation bans for this group's TrustNets.")
            return
        
        lines = [f"🚫 <b>Active Federation Bans ({len(bans)})</b>\n"]
        for b in bans[:10]:
            silent = " 🤫" if b["silent"] else ""
            lines.append(
                f"• <code>{b['user_id']}</code> — {b['name']}{silent}\n"
                f"  <i>{b['reason'][:40]}</i>"
            )
        
        if len(bans) > 10:
            lines.append(f"\n<i>...and {len(bans) - 10} more</i>")
        
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        
    except Exception as e:
        log.error(f"[FED] Bans list failed: {e}")
        await update.message.reply_text("❌ Failed to get ban list.")


async def cmd_fedstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fedstat [user_id] - Check if a user is federation-banned."""
    chat = update.effective_chat
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    # Get user ID from reply or args
    message = update.effective_message
    reply = message.reply_to_message
    
    if reply:
        target_id = reply.from_user.id
    elif context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
            return
    else:
        await update.message.reply_text("Reply to a message or provide a user ID.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            bans = await conn.fetch(
                """SELECT fb.reason, fb.banned_at, fb.silent, f.name
                   FROM federation_bans fb
                   JOIN federations f ON f.id = fb.federation_id
                   JOIN federation_members fm ON fm.federation_id = f.id
                   WHERE fm.chat_id = $1 AND fb.user_id = $2""",
                chat.id, target_id
            )
        
        if not bans:
            await update.message.reply_text(
                f"✅ User <code>{target_id}</code> is not banned in any TrustNet.",
                parse_mode="HTML"
            )
            return
        
        lines = [f"🚫 <b>Federation Ban Status</b>\nUser: <code>{target_id}</code>\n"]
        for b in bans:
            silent = " (silent)" if b["silent"] else ""
            lines.append(
                f"• <b>{b['name']}</b>{silent}\n"
                f"  Reason: {b['reason']}\n"
                f"  Banned: {b['banned_at'].strftime('%Y-%m-%d')}"
            )
        
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        
    except Exception as e:
        log.error(f"[FED] Stat failed: {e}")
        await update.message.reply_text("❌ Failed to check federation status.")


async def cmd_fedadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fedadmins - List all admins in the current TrustNet."""
    chat = update.effective_chat
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get first federation this group is in
            fed = await conn.fetchrow(
                """SELECT f.id, f.name, f.owner_id
                   FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1
                   LIMIT 1""",
                chat.id
            )
            
            if not fed:
                await update.message.reply_text("❌ This group is not in any TrustNet.")
                return
            
            # Get admins
            admins = await conn.fetch(
                """SELECT user_id, promoted_at FROM federation_admins
                   WHERE federation_id = $1""",
                fed["id"]
            )
        
        lines = [f"🌐 <b>{fed['name']}</b> - Admins\n"]
        lines.append(f"• Owner: <code>{fed['owner_id']}</code> 👑\n")
        
        for a in admins:
            lines.append(f"• <code>{a['user_id']}</code>")
        
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        
    except Exception as e:
        log.error(f"[FED] Admins list failed: {e}")
        await update.message.reply_text("❌ Failed to get admin list.")


async def cmd_fpromote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fpromote - Promote a user to federation admin (owner only)."""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    reply = message.reply_to_message
    
    if not reply:
        await update.message.reply_text("Reply to a message to promote that user to federation admin.")
        return
    
    target = reply.from_user
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get federation and verify ownership
            fed = await conn.fetchrow(
                """SELECT f.id, f.name FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1 AND f.owner_id = $2
                   LIMIT 1""",
                chat.id, user.id
            )
            
            if not fed:
                await update.message.reply_text("❌ You must be the TrustNet owner to promote admins.")
                return
            
            # Promote
            await conn.execute(
                """INSERT INTO federation_admins (federation_id, user_id, promoted_by)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (federation_id, user_id) DO NOTHING""",
                fed["id"], target.id, user.id
            )
        
        await update.message.reply_text(
            f"✅ <b>Federation Admin Promoted</b>\n\n"
            f"User: {target.mention_html()}\n"
            f"Network: {fed['name']}",
            parse_mode="HTML"
        )
        log.info(f"[FED] Promote | target={target.id} fed={fed['id']}")
        
    except Exception as e:
        log.error(f"[FED] Promote failed: {e}")
        await update.message.reply_text("❌ Failed to promote user.")


async def cmd_fdemote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fdemote - Demote a federation admin (owner only)."""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    reply = message.reply_to_message
    
    if not reply:
        await update.message.reply_text("Reply to a message to demote that user.")
        return
    
    target = reply.from_user
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            fed = await conn.fetchrow(
                """SELECT f.id, f.name FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1 AND f.owner_id = $2
                   LIMIT 1""",
                chat.id, user.id
            )
            
            if not fed:
                await update.message.reply_text("❌ You must be the TrustNet owner to demote admins.")
                return
            
            await conn.execute(
                "DELETE FROM federation_admins WHERE federation_id = $1 AND user_id = $2",
                fed["id"], target.id
            )
        
        await update.message.reply_text(
            f"✅ <b>Federation Admin Demoted</b>\n\n"
            f"User: {target.mention_html()}\n"
            f"Network: {fed['name']}",
            parse_mode="HTML"
        )
        log.info(f"[FED] Demote | target={target.id} fed={fed['id']}")
        
    except Exception as e:
        log.error(f"[FED] Demote failed: {e}")
        await update.message.reply_text("❌ Failed to demote user.")


async def cmd_fedtransfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fedtransfer <uid> <netid> - Transfer TrustNet ownership (private chat)."""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type != "private":
        await update.message.reply_text("❌ Use this command in private chat.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: <code>/fedtransfer &lt;new_owner_id&gt; &lt;federation_id&gt;</code>", parse_mode="HTML")
        return
    
    try:
        new_owner_id = int(context.args[0])
        fed_id = context.args[1]
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Verify ownership
            fed = await conn.fetchrow(
                "SELECT name FROM federations WHERE id = $1 AND owner_id = $2",
                fed_id, user.id
            )
            
            if not fed:
                await update.message.reply_text("❌ You don't own this TrustNet or it doesn't exist.")
                return
            
            # Transfer
            await conn.execute(
                "UPDATE federations SET owner_id = $1 WHERE id = $2",
                new_owner_id, fed_id
            )
        
        await update.message.reply_text(
            f"✅ <b>TrustNet Transferred</b>\n\n"
            f"Network: {fed['name']}\n"
            f"New Owner: <code>{new_owner_id}</code>",
            parse_mode="HTML"
        )
        log.info(f"[FED] Transfer | fed={fed_id} new_owner={new_owner_id}")
        
    except Exception as e:
        log.error(f"[FED] Transfer failed: {e}")
        await update.message.reply_text("❌ Failed to transfer ownership.")


async def cmd_fbroadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fbroadcast - Broadcast a message to all TrustNet groups (fed admin)."""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    reply = message.reply_to_message
    
    if not reply:
        await update.message.reply_text("Reply to a message to broadcast it to all TrustNet groups.")
        return
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get federations and check admin status
            feds = await conn.fetch(
                """SELECT f.id, f.name FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1""",
                chat.id
            )
            
            if not feds:
                await update.message.reply_text("❌ This group is not in any TrustNet.")
                return
            
            sent_count = 0
            for fed in feds:
                # Check if user is fed admin or owner
                is_admin = await conn.fetchval(
                    """SELECT 1 FROM federation_admins WHERE federation_id = $1 AND user_id = $2
                       UNION
                       SELECT 1 FROM federations WHERE id = $1 AND owner_id = $2""",
                    fed["id"], user.id
                )
                
                if not is_admin:
                    continue
                
                # Get all groups
                groups = await conn.fetch(
                    "SELECT chat_id FROM federation_members WHERE federation_id = $1",
                    fed["id"]
                )
                
                # Forward message
                for g in groups:
                    try:
                        await reply.copy(chat_id=g["chat_id"])
                        sent_count += 1
                    except Exception:
                        pass
        
        await update.message.reply_text(
            f"📢 <b>Broadcast Complete</b>\n\n"
            f"Message sent to {sent_count} groups.",
            parse_mode="HTML"
        )
        log.info(f"[FED] Broadcast | by={user.id} groups={sent_count}")
        
    except Exception as e:
        log.error(f"[FED] Broadcast failed: {e}")
        await update.message.reply_text("❌ Failed to broadcast.")


async def cmd_setfedlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setfedlog <net-id> - Set this group as the log channel for a TrustNet (owner only)."""
    user = update.effective_user
    chat = update.effective_chat
    
    if not context.args:
        await update.message.reply_text("Usage: <code>/setfedlog &lt;federation_id&gt;</code>", parse_mode="HTML")
        return
    
    fed_id = context.args[0]
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Verify ownership
            fed = await conn.fetchrow(
                "SELECT name FROM federations WHERE id = $1 AND owner_id = $2",
                fed_id, user.id
            )
            
            if not fed:
                await update.message.reply_text("❌ You don't own this TrustNet or it doesn't exist.")
                return
            
            # Set log channel
            await conn.execute(
                "UPDATE federations SET log_channel_id = $1 WHERE id = $2",
                chat.id, fed_id
            )
        
        await update.message.reply_text(
            f"✅ <b>Log Channel Set</b>\n\n"
            f"Network: {fed['name']}\n"
            f"Log Channel: <code>{chat.id}</code>",
            parse_mode="HTML"
        )
        
    except Exception as e:
        log.error(f"[FED] Set log failed: {e}")
        await update.message.reply_text("❌ Failed to set log channel.")


async def cmd_trustappeal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/trustappeal <reason> - Appeal a federation ban (any user, private chat)."""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type != "private":
        await update.message.reply_text("❌ Use this command in private chat.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 <b>Appeal Federation Ban</b>\n\n"
            "Usage: <code>/trustappeal &lt;your appeal reason (min 20 chars)&gt;</code>\n\n"
            "Explain why you believe the ban was unjustified.",
            parse_mode="HTML"
        )
        return
    
    reason = " ".join(context.args)
    if len(reason) < 20:
        await update.message.reply_text("❌ Appeal reason too short. Please provide at least 20 characters.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Find bans for this user
            bans = await conn.fetch(
                "SELECT federation_id FROM federation_bans WHERE user_id = $1",
                user.id
            )
            
            if not bans:
                await update.message.reply_text("✅ You are not banned in any TrustNet.")
                return
            
            # Create appeals
            for ban in bans:
                await conn.execute(
                    """INSERT INTO federation_appeals (federation_id, user_id, reason)
                       VALUES ($1, $2, $3)
                       ON CONFLICT DO NOTHING""",
                    ban["federation_id"], user.id, reason
                )
        
        await update.message.reply_text(
            f"📝 <b>Appeal Submitted</b>\n\n"
            f"Your appeal has been sent to the TrustNet admins.\n"
            f"You will be notified when it's reviewed.",
            parse_mode="HTML"
        )
        log.info(f"[FED] Appeal | user={user.id}")
        
    except Exception as e:
        log.error(f"[FED] Appeal failed: {e}")
        await update.message.reply_text("❌ Failed to submit appeal.")


async def cmd_trusttrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/trusttrust - Show cross-federation trust score for a user (admin)."""
    chat = update.effective_chat
    message = update.effective_message
    reply = message.reply_to_message
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    if reply:
        target_id = reply.from_user.id
        target_name = reply.from_user.mention_html()
    elif context.args:
        try:
            target_id = int(context.args[0])
            target_name = f"<code>{target_id}</code>"
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
            return
    else:
        await update.message.reply_text("Reply to a message or provide a user ID.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get reputation scores
            scores = await conn.fetch(
                """SELECT fr.score, f.name FROM federation_reputation fr
                   JOIN federations f ON f.id = fr.federation_id
                   JOIN federation_members fm ON fm.federation_id = f.id
                   WHERE fm.chat_id = $1 AND fr.user_id = $2""",
                chat.id, target_id
            )
            
            if not scores:
                # Default neutral score
                await update.message.reply_text(
                    f"🛡️ <b>Trust Score</b>\n"
                    f"User: {target_name}\n"
                    f"Score: 50/100 (Neutral)\n"
                    f"No history in this TrustNet.",
                    parse_mode="HTML"
                )
                return
            
            avg_score = sum(s["score"] for s in scores) / len(scores)
            
            # Determine level
            if avg_score >= 80:
                level = "🟢 Trusted"
            elif avg_score >= 60:
                level = "🟡 Reliable"
            elif avg_score >= 40:
                level = "⚪ Neutral"
            elif avg_score >= 20:
                level = "🟠 Suspicious"
            else:
                level = "🔴 Untrusted"
            
            lines = [
                f"🛡️ <b>Trust Score</b>",
                f"User: {target_name}",
                f"Score: {avg_score:.0f}/100 ({level})",
                f"\n<b>By Network:</b>"
            ]
            
            for s in scores:
                lines.append(f"• {s['name']}: {s['score']}/100")
            
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
            
    except Exception as e:
        log.error(f"[FED] Trust score failed: {e}")
        await update.message.reply_text("❌ Failed to get trust score.")


# Handler registration
federation_handlers = [
    # TrustNet commands
    CommandHandler("newtrust", cmd_newtrust),
    CommandHandler("jointrust", cmd_jointrust),
    CommandHandler("leavetrust", cmd_leavetrust),
    CommandHandler("trustinfo", cmd_trustinfo),
    CommandHandler("myfeds", cmd_myfeds),
    CommandHandler("fedchats", cmd_fedchats),
    CommandHandler("trustban", cmd_trustban),
    CommandHandler("sfban", cmd_sfban),
    CommandHandler("trustunban", cmd_trustunban),
    CommandHandler("trustbans", cmd_trustbans),
    CommandHandler("fedstat", cmd_fedstat),
    CommandHandler("fedadmins", cmd_fedadmins),
    CommandHandler("fpromote", cmd_fpromote),
    CommandHandler("fdemote", cmd_fdemote),
    CommandHandler("fedtransfer", cmd_fedtransfer),
    CommandHandler("fbroadcast", cmd_fbroadcast),
    CommandHandler("setfedlog", cmd_setfedlog),
    CommandHandler("trustappeal", cmd_trustappeal),
    CommandHandler("trusttrust", cmd_trusttrust),
    
    # Federation aliases (work the same as trust* commands)
    CommandHandler("newfed", cmd_newtrust),
    CommandHandler("joinfed", cmd_jointrust),
    CommandHandler("leavefed", cmd_leavetrust),
    CommandHandler("fedinfo", cmd_trustinfo),
    CommandHandler("fban", cmd_trustban),
    CommandHandler("sfban", cmd_sfban),
    CommandHandler("unfban", cmd_trustunban),
    CommandHandler("fbanlist", cmd_trustbans),
    CommandHandler("fstats", cmd_fedstat),
    CommandHandler("fadmins", cmd_fedadmins),
    CommandHandler("ftransfer", cmd_fedtransfer),
    CommandHandler("fbroadcast", cmd_fbroadcast),
]
