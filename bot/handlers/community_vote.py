"""
bot/handlers/community_vote.py

Community Vote System - Democratic scam removal v21
6 auto-detected scam patterns + manual vote trigger.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from bot.utils.permissions import is_admin
from bot.logging.log_channel import log_event

log = logging.getLogger("community_vote")

# Scam patterns for auto-detection
SCAM_PATTERNS = {
    "lottery": {
        "patterns": [
            r"congratulations.*won.*\$[\d,]+",
            r"winner.*lottery.*prize",
            r"you won.*\d+.*(btc|eth|usdt)",
            r"lucky winner.*\$[\d,]+",
        ],
        "description": "🎰 Lottery/Prize Scam",
    },
    "crypto_pump": {
        "patterns": [
            r"pump.*dump.*crypto",
            r"guaranteed.*profit.*\d+%",
            r"invest.*double.*money",
            r"crypto.*signal.*vip",
        ],
        "description": "📈 Crypto Pump & Dump",
    },
    "urgency": {
        "patterns": [
            r"urgent.*immediate.*action",
            r"limited.*time.*offer",
            r"act now.*expire",
            r"only.*spots left",
        ],
        "description": "⏰ Fake Urgency",
    },
    "recovery": {
        "patterns": [
            r"recover.*lost.*(btc|crypto|funds)",
            r"hacked.*recover.*account",
            r"lost.*password.*recover",
            r"scammed.*get.*money back",
        ],
        "description": "🔄 Recovery Scam",
    },
    "job": {
        "patterns": [
            r"work.*from.*home.*\$[\d,]+.*(day|week|month)",
            r"easy.*money.*job",
            r"hiring.*immediately.*no experience",
            r"earn.*\$[\d,]+.*per.*day",
        ],
        "description": "💼 Fake Job Offer",
    },
    "airdrop": {
        "patterns": [
            r"airdrop.*claim.*free",
            r"free.*tokens.*airdrop",
            r"send.*eth.*get.*double",
            r"verify.*wallet.*receive",
        ],
        "description": "🎁 Fake Airdrop",
    },
}


def detect_scam(text: str) -> Optional[tuple]:
    """
    Detect scam patterns in text.
    Returns (scam_type, description) if detected, None otherwise.
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    for scam_type, data in SCAM_PATTERNS.items():
        for pattern in data["patterns"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return scam_type, data["description"]
    
    return None


async def start_community_vote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_message,
    scam_type: str,
    scam_description: str,
    trigger_text: str = None,
    is_auto: bool = False
):
    """Start a community vote on a suspicious message."""
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    if not db:
        return
    
    # Get vote settings
    try:
        async with db.acquire() as conn:
            settings_row = await conn.fetchrow(
                "SELECT settings FROM groups WHERE chat_id = $1",
                chat.id
            )
            
            settings = settings_row["settings"] or {}
            if isinstance(settings, str):
                import json
                settings = json.loads(settings)
            
            vote_settings = settings.get("auto_vote", {})
            threshold = vote_settings.get("threshold", 5)
            timeout = vote_settings.get("timeout", 10)
            action = vote_settings.get("action", "kick")
            enabled = vote_settings.get("enabled", True)
    except Exception as e:
        log.debug(f"Vote settings error: {e}")
        threshold = 5
        timeout = 10
        action = "kick"
        enabled = True
    
    if not enabled and is_auto:
        return
    
    target_user = target_message.from_user
    
    # Create vote message
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Guilty", callback_data=f"vote:up:{target_message.message_id}"),
            InlineKeyboardButton("❌ Not Guilty", callback_data=f"vote:down:{target_message.message_id}"),
        ],
        [
            InlineKeyboardButton("🤐 Abstain", callback_data=f"vote:abstain:{target_message.message_id}"),
        ]
    ])
    
    trigger_info = f"\n🤖 <i>Auto-detected: {scam_description}</i>" if is_auto else ""
    
    vote_text = (
        f"⚖️ <b>Community Vote</b>\n\n"
        f"Target: {target_user.mention_html()}\n"
        f"Reason: {scam_description}{trigger_info}\n\n"
        f"Threshold: <b>{threshold}</b> votes\n"
        f"Timeout: <b>{timeout}</b> minutes\n"
        f"Action if passed: <b>{action}</b>\n\n"
        f"Vote below:"
    )
    
    try:
        vote_msg = await context.bot.send_message(
            chat_id=chat.id,
            text=vote_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            reply_to_message_id=target_message.message_id
        )
        
        # Save to database
        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO community_vote_log 
                   (chat_id, message_id, target_user_id, scam_type, trigger_text,
                    vote_message_id, threshold, timeout_minutes, action, started_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                chat.id, target_message.message_id, target_user.id, scam_type,
                trigger_text or scam_description, vote_msg.message_id,
                threshold, timeout, action, user.id if not is_auto else 0
            )
        
        # Schedule vote timeout
        asyncio.create_task(
            _process_vote_timeout(context, chat.id, target_message.message_id, timeout)
        )
        
        log.info(f"[VOTE] Started | chat={chat.id} target={target_user.id} type={scam_type}")
        
    except Exception as e:
        log.error(f"[VOTE] Start failed: {e}")


async def _process_vote_timeout(context, chat_id: int, message_id: int, timeout_minutes: int):
    """Process vote timeout and take action if needed."""
    await asyncio.sleep(timeout_minutes * 60)
    
    db = context.application.bot_data.get("db_pool") or context.application.bot_data.get("db")
    if not db:
        return
    
    try:
        async with db.acquire() as conn:
            # Get vote data
            vote = await conn.fetchrow(
                """SELECT * FROM community_vote_log 
                   WHERE chat_id = $1 AND message_id = $2 AND result IS NULL""",
                chat_id, message_id
            )
            
            if not vote:
                return
            
            # Count votes
            participants = await conn.fetch(
                "SELECT vote FROM community_vote_participants WHERE vote_id = $1",
                vote["id"]
            )
            
            upvotes = sum(1 for p in participants if p["vote"] == "up")
            downvotes = sum(1 for p in participants if p["vote"] == "down")
            abstentions = sum(1 for p in participants if p["vote"] == "abstain")
            
            # Determine result
            if upvotes >= vote["threshold"]:
                result = "passed"
                action_taken = vote["action"]
            elif downvotes >= vote["threshold"]:
                result = "failed"
                action_taken = None
            else:
                result = "timeout"
                action_taken = None
            
            # Update vote log
            await conn.execute(
                """UPDATE community_vote_log 
                   SET result = $1, action_taken = $2, ended_at = NOW(),
                       upvotes = $3, downvotes = $4, abstentions = $5
                   WHERE id = $6""",
                result, action_taken, upvotes, downvotes, abstentions, vote["id"]
            )
        
        # Take action if passed
        if result == "passed" and action_taken:
            await _execute_vote_action(context, chat_id, vote["target_user_id"], action_taken, vote["id"])
        
        # Send result message
        result_text = {
            "passed": f"✅ <b>Vote Passed</b>\n\nAction: {action_taken}\nVotes: {upvotes} guilty, {downvotes} not guilty",
            "failed": f"❌ <b>Vote Failed</b>\n\nVotes: {upvotes} guilty, {downvotes} not guilty",
            "timeout": f"⏱️ <b>Vote Expired</b>\n\nNot enough votes. Threshold was {vote['threshold']}."
        }.get(result, "Vote ended.")
        
        await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode="HTML")
        
    except Exception as e:
        log.error(f"[VOTE] Timeout processing failed: {e}")


async def _execute_vote_action(context, chat_id: int, user_id: int, action: str, vote_id: str):
    """Execute the vote action on the target user."""
    try:
        if action == "mute":
            from telegram import ChatPermissions
            until = datetime.now(timezone.utc) + timedelta(hours=1)
            await context.bot.restrict_chat_member(
                chat_id, user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until
            )
        elif action == "kick":
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)  # Allow rejoin
        elif action == "ban":
            await context.bot.ban_chat_member(chat_id, user_id)
        elif action == "delete":
            # Delete the original message
            db = context.application.bot_data.get("db_pool") or context.application.bot_data.get("db")
            if db:
                async with db.acquire() as conn:
                    vote = await conn.fetchrow(
                        "SELECT message_id FROM community_vote_log WHERE id = $1",
                        vote_id
                    )
                    if vote:
                        try:
                            await context.bot.delete_message(chat_id, vote["message_id"])
                        except Exception:
                            pass
        
        log.info(f"[VOTE] Action executed | chat={chat_id} user={user_id} action={action}")
        
    except Exception as e:
        log.error(f"[VOTE] Action failed: {e}")


async def cmd_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/vote - Manually start a community vote on a message."""
    chat = update.effective_chat
    message = update.effective_message
    reply = message.reply_to_message
    
    if not reply:
        await update.message.reply_text(
            "⚖️ <b>Community Vote</b>\n\n"
            "Reply to a suspicious message with <code>/vote</code> to start a vote.\n\n"
            "The community will decide if action should be taken.",
            parse_mode="HTML"
        )
        return
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    target_user = reply.from_user
    if target_user.id == context.bot.id:
        await update.message.reply_text("❌ Can't vote on bot messages.")
        return
    
    await start_community_vote(
        update, context, reply,
        scam_type="manual",
        scam_description="Manual vote requested by admin",
        is_auto=False
    )


async def cmd_votekick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/votekick - Quick alias to start a vote kick."""
    await cmd_vote(update, context)


async def cmd_votesettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/votesettings - Configure community vote settings (admin only)."""
    chat = update.effective_chat
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    # Parse args
    if len(context.args) >= 2:
        setting = context.args[0].lower()
        value = context.args[1]
        
        try:
            async with db.acquire() as conn:
                # Get current settings
                row = await conn.fetchrow(
                    "SELECT settings FROM groups WHERE chat_id = $1",
                    chat.id
                )
                
                settings = row["settings"] or {}
                if isinstance(settings, str):
                    import json
                    settings = json.loads(settings)
                
                auto_vote = settings.get("auto_vote", {})
                
                if setting == "threshold":
                    auto_vote["threshold"] = max(3, min(20, int(value)))
                elif setting == "timeout":
                    auto_vote["timeout"] = max(5, min(60, int(value)))
                elif setting == "action":
                    if value in ["mute", "kick", "ban", "delete"]:
                        auto_vote["action"] = value
                elif setting == "auto":
                    auto_vote["enabled"] = value.lower() in ["on", "true", "yes", "1"]
                
                settings["auto_vote"] = auto_vote
                
                await conn.execute(
                    "UPDATE groups SET settings = $1 WHERE chat_id = $2",
                    settings, chat.id
                )
            
            await update.message.reply_text(
                f"✅ <b>Vote Settings Updated</b>\n\n"
                f"{setting}: {value}",
                parse_mode="HTML"
            )
            return
            
        except Exception as e:
            log.error(f"[VOTE] Settings update failed: {e}")
            await update.message.reply_text("❌ Failed to update settings.")
            return
    
    # Show current settings
    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT settings FROM groups WHERE chat_id = $1",
                chat.id
            )
            
            settings = row["settings"] or {}
            if isinstance(settings, str):
                import json
                settings = json.loads(settings)
            
            auto_vote = settings.get("auto_vote", {})
            
            await update.message.reply_text(
                f"⚙️ <b>Community Vote Settings</b>\n\n"
                f"Auto-detect: {'✅ On' if auto_vote.get('enabled', True) else '❌ Off'}\n"
                f"Threshold: {auto_vote.get('threshold', 5)} votes\n"
                f"Timeout: {auto_vote.get('timeout', 10)} minutes\n"
                f"Action: {auto_vote.get('action', 'kick')}\n\n"
                f"<i>Usage: /votesettings &lt;setting&gt; &lt;value&gt;</i>\n"
                f"Settings: threshold (3-20), timeout (5-60), action (mute/kick/ban/delete), auto (on/off)",
                parse_mode="HTML"
            )
    except Exception as e:
        log.error(f"[VOTE] Settings display failed: {e}")


async def cmd_votestats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/votestats - Show community vote statistics."""
    chat = update.effective_chat
    
    if not await is_admin(update, context):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get stats
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM community_vote_log WHERE chat_id = $1",
                chat.id
            )
            passed = await conn.fetchval(
                "SELECT COUNT(*) FROM community_vote_log WHERE chat_id = $1 AND result = 'passed'",
                chat.id
            )
            failed = await conn.fetchval(
                "SELECT COUNT(*) FROM community_vote_log WHERE chat_id = $1 AND result = 'failed'",
                chat.id
            )
            
            # By scam type
            by_type = await conn.fetch(
                """SELECT scam_type, COUNT(*) as count 
                   FROM community_vote_log 
                   WHERE chat_id = $1 
                   GROUP BY scam_type""",
                chat.id
            )
        
        lines = [
            f"📊 <b>Community Vote Statistics</b>\n",
            f"Total Votes: {total}",
            f"✅ Passed: {passed}",
            f"❌ Failed: {failed}",
            f"\n<b>By Type:</b>"
        ]
        
        for t in by_type:
            type_name = t["scam_type"].replace("_", " ").title()
            lines.append(f"• {type_name}: {t['count']}")
        
        # Show scam pattern reference
        lines.append("\n<b>Auto-detected Patterns:</b>")
        for scam_type, data in SCAM_PATTERNS.items():
            lines.append(f"• {data['description']}")
        
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        
    except Exception as e:
        log.error(f"[VOTE] Stats failed: {e}")
        await update.message.reply_text("❌ Failed to get statistics.")


async def handle_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle vote button presses."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    parts = data.split(":")
    if len(parts) != 3:
        return
    
    _, vote_type, message_id_str = parts
    message_id = int(message_id_str)
    chat_id = query.message.chat_id
    
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    
    try:
        async with db.acquire() as conn:
            # Get vote
            vote = await conn.fetchrow(
                """SELECT id, target_user_id FROM community_vote_log 
                   WHERE chat_id = $1 AND message_id = $2 AND result IS NULL""",
                chat_id, message_id
            )
            
            if not vote:
                await query.edit_message_text("⛔ This vote has ended.")
                return
            
            # Can't vote on yourself
            if user.id == vote["target_user_id"]:
                await query.answer("❌ You can't vote on yourself!", show_alert=True)
                return
            
            # Record or update vote
            await conn.execute(
                """INSERT INTO community_vote_participants (vote_id, user_id, vote)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (vote_id, user_id) DO UPDATE SET vote = EXCLUDED.vote""",
                vote["id"], user.id, vote_type
            )
        
        await query.answer(f"✅ Vote recorded: {vote_type}")
        
        # Get updated counts
        async with db.acquire() as conn:
            participants = await conn.fetch(
                "SELECT vote FROM community_vote_participants WHERE vote_id = $1",
                vote["id"]
            )
        
        upvotes = sum(1 for p in participants if p["vote"] == "up")
        downvotes = sum(1 for p in participants if p["vote"] == "down")
        abstentions = sum(1 for p in participants if p["vote"] == "abstain")
        
        # Check if threshold reached
        vote_data = await conn.fetchrow(
            "SELECT threshold, action FROM community_vote_log WHERE id = $1",
            vote["id"]
        )
        
        if upvotes >= vote_data["threshold"]:
            # End vote early
            await conn.execute(
                """UPDATE community_vote_log 
                   SET result = 'passed', action_taken = $1, ended_at = NOW(),
                       upvotes = $2, downvotes = $3, abstentions = $4
                   WHERE id = $5""",
                vote_data["action"], upvotes, downvotes, abstentions, vote["id"]
            )
            
            await _execute_vote_action(context, chat_id, vote["target_user_id"], vote_data["action"], vote["id"])
            
            await query.edit_message_text(
                f"✅ <b>Vote Passed</b>\n\n"
                f"Action: {vote_data['action']}\n"
                f"Final: {upvotes} guilty, {downvotes} not guilty",
                parse_mode="HTML"
            )
        elif downvotes >= vote_data["threshold"]:
            await conn.execute(
                """UPDATE community_vote_log 
                   SET result = 'failed', ended_at = NOW(),
                       upvotes = $1, downvotes = $2, abstentions = $3
                   WHERE id = $4""",
                upvotes, downvotes, abstentions, vote["id"]
            )
            
            await query.edit_message_text(
                f"❌ <b>Vote Failed</b>\n\n"
                f"Final: {upvotes} guilty, {downvotes} not guilty",
                parse_mode="HTML"
            )
        
    except Exception as e:
        log.error(f"[VOTE] Callback failed: {e}")


# Auto-detection handler
async def auto_detect_scam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-detect scam messages and trigger votes."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    
    if not chat or chat.type not in ["group", "supergroup"]:
        return
    
    if not message or not user or user.is_bot:
        return
    
    text = message.text or message.caption or ""
    
    # Check for scam patterns
    result = detect_scam(text)
    if not result:
        return
    
    scam_type, scam_description = result
    
    # Check if auto-vote is enabled
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    if not db:
        return
    
    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT settings FROM groups WHERE chat_id = $1",
                chat.id
            )
            
            if not row:
                return
            
            settings = row["settings"] or {}
            if isinstance(settings, str):
                import json
                settings = json.loads(settings)
            
            auto_vote = settings.get("auto_vote", {})
            if not auto_vote.get("enabled", True):
                return
    except Exception as e:
        log.debug(f"Auto-detect settings error: {e}")
        return
    
    # Start vote
    await start_community_vote(
        update, context, message,
        scam_type=scam_type,
        scam_description=scam_description,
        trigger_text=text[:200],
        is_auto=True
    )
    
    log.info(f"[VOTE] Auto-detected | chat={chat.id} user={user.id} type={scam_type}")


# Handler registration
community_vote_handlers = [
    CommandHandler("vote", cmd_vote),
    CommandHandler("votekick", cmd_votekick),
    CommandHandler("votesettings", cmd_votesettings),
    CommandHandler("votestats", cmd_votestats),
    CallbackQueryHandler(handle_vote_callback, pattern=r"^vote:(up|down|abstain):\d+$"),
]
