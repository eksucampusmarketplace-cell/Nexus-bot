"""
bot/handlers/booster.py

Member Booster and Force Join Channel handlers.
Implements the complete boost system including:
- Invite link tracking
- Manual add detection and credit management
- Force channel gate
- Witness mode for manual add attribution
"""

import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ChatMemberHandler,
    CommandHandler, MessageHandler, CallbackQueryHandler,
    filters
)
from telegram.error import TelegramError, Forbidden

logger = logging.getLogger(__name__)


# ==================== Helper Functions ====================

def detect_join_source(member) -> str:
    """
    Detect how a member joined the group.
    
    Returns:
        - invite_link: via tracked invite link
        - join_request: via join request (creates_join_request=True)
        - manual_add: manually added (no invite link)
        - bot_add: added via bot
        - unknown: fallback
    """
    if member.invite_link:
        if getattr(member.invite_link, 'creates_join_request', False):
            return "join_request"
        return "invite_link"
    
    if getattr(member.new_chat_member, 'via_bot', False):
        return "bot_add"
    
    # No invite link = manual add (contacts, search, group settings, etc.)
    return "manual_add"


def make_progress_bar(current: int, required: int, style: str = "blocks") -> str:
    """Generate visual progress bar."""
    if required <= 0:
        return f"✅ Complete!"
    
    pct = min(current / required, 1.0)
    length = 10
    
    if style == "blocks":
        filled = int(pct * length)
        bar = "█" * filled + "░" * (length - filled)
    elif style == "dots":
        filled = int(pct * length)
        bar = "●" * filled + "○" * (length - filled)
    elif style == "emoji":
        filled = int(pct * length)
        bar = "🟩" * filled + "⬜" * (length - filled)
    elif style == "numbers":
        return f"[{current}/{required}]"
    else:
        return f"[{current}/{required}]"
    
    return f"{bar} {current}/{required}"


async def is_admin_or_exempt(chat_id: int, user_id: int, config: dict, bot) -> bool:
    """Check if user is admin or exempt."""
    # Check specific exemptions
    if config.get('exempt_specific_users') and user_id in config.get('exempt_specific_users', []):
        return True
    
    # Check if admins are exempt
    if config.get('exempt_admins', True):
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in ['administrator', 'creator']:
                return True
        except TelegramError:
            pass
    
    return False


# ==================== Core Logic ====================

async def handle_new_member(
    bot, update: Update, config: dict, is_channel_gate: bool = False
):
    """Handle new member joins - main entry point."""
    chat = update.effective_chat
    member = update.chat_member
    new_user = member.new_chat_member.user
    
    # Ignore bots
    if new_user.is_bot:
        return
    
    join_source = detect_join_source(member)
    logger.info(
        f"[BOOSTER] New member | group_id={chat.id} | "
        f"user_id={new_user.id} | source={join_source}"
    )
    
    # Check if user is admin or exempt
    if await is_admin_or_exempt(chat.id, new_user.id, config, bot):
        logger.info(f"[BOOSTER] Skipping admin/exempt user {new_user.id}")
        return
    
    # Get user's boost record if exists
    from db.ops.booster import get_boost_record, create_boost_record
    record = await get_boost_record(chat.id, new_user.id)
    
    # Handle channel gate first
    if config.get('force_channel_enabled') and config.get('force_channel_id'):
        await handle_channel_gate(bot, chat, new_user, config)
        if is_channel_gate:
            return
    
    # Handle boost system
    if config.get('force_add_enabled') and config.get('force_add_required', 0) > 0:
        await handle_boost_join(
            bot, chat, new_user, member, join_source, config, record
        )


async def handle_boost_join(
    bot, chat, new_user, member, join_source: str, config: dict, existing_record: dict
):
    """Handle boost-related join logic."""
    from db.ops.booster import (
        create_boost_record, record_invite_event, get_boost_record,
        record_manual_add, update_invite_count, set_unlocked
    )
    
    # Create or update boost record
    required_count = config.get('force_add_required', 5)
    
    if existing_record:
        # User already has a record - might be returning member
        if existing_record.get('is_unlocked'):
            # Already unlocked - no action needed
            logger.info(f"[BOOSTER] Returning unlocked member {new_user.id}")
            return
    else:
        # New member - create record
        await create_boost_record(
            group_id=chat.id,
            user_id=new_user.id,
            username=new_user.username,
            first_name=new_user.first_name,
            required_count=required_count,
            join_source=join_source
        )
    
    # Handle based on join source
    if join_source == "invite_link" and member.invite_link:
        # Attribute invite to the link creator
        invite_link = member.invite_link.invite_link
        inviter_id = None
        
        # Try to find who created this link (would need to track created links)
        # For now, just log the invite
        logger.info(
            f"[BOOSTER] Invite via link | group_id={chat.id} | "
            f"invite_link={invite_link} | new_user={new_user.id}"
        )
        
        # Record the event
        await record_invite_event(
            group_id=chat.id,
            inviter_user_id=inviter_id or 0,
            invited_user_id=new_user.id,
            invited_username=new_user.username,
            invited_first_name=new_user.first_name,
            invite_link=invite_link,
            source="link"
        )
    
    elif join_source == "manual_add":
        # Record manual add for admin review
        added_by = None
        if hasattr(member, 'from_user') and member.from_user:
            added_by = member.from_user.id
        
        await record_manual_add(
            group_id=chat.id,
            added_user_id=new_user.id,
            added_username=new_user.username,
            added_first_name=new_user.first_name,
            added_by_user_id=added_by
        )
        
        logger.info(
            f"[BOOSTER] Manual add detected | group_id={chat.id} | "
            f"added={new_user.id} | added_by={added_by}"
        )
        
        # Auto-detect: notify admins
        if config.get('manual_add_auto_detect'):
            await notify_admins_manual_add(bot, chat, new_user, added_by, config)
        
        # Witness mode: DM new member
        if config.get('manual_add_witness_mode'):
            asyncio.create_task(send_witness_dm(bot, new_user, chat, config))
    
    # Apply restriction to new member
    await apply_boost_restriction(bot, chat, new_user, config)


async def apply_boost_restriction(bot, chat, new_user, config: dict):
    """Apply boost restriction to a user."""
    from db.ops.booster import set_restricted, get_boost_record
    
    action = config.get('force_add_action', 'mute')
    required_count = config.get('force_add_required', 5)
    
    # Get or create record
    record = await get_boost_record(chat.id, new_user.id)
    if not record:
        from db.ops.booster import create_boost_record
        record = await create_boost_record(
            group_id=chat.id,
            user_id=new_user.id,
            username=new_user.username,
            first_name=new_user.first_name,
            required_count=required_count
        )
    
    # Apply restriction based on action
    try:
        if action == 'mute':
            await bot.restrict_chat_member(
                chat.id, new_user.id,
                permissions={
                    "can_send_messages": False,
                    "can_send_media_messages": False,
                    "can_send_other_messages": False,
                    "can_add_web_page_previews": False
                }
            )
        elif action == 'restrict_media':
            await bot.restrict_chat_member(
                chat.id, new_user.id,
                permissions={
                    "can_send_messages": True,
                    "can_send_media_messages": False,
                    "can_send_other_messages": False,
                    "can_add_web_page_previews": False
                }
            )
        
        await set_restricted(chat.id, new_user.id, True)
        
        # Send boost message
        await send_boost_message(bot, chat, new_user, config, record)
        
        logger.info(
            f"[BOOSTER] Restricted | group_id={chat.id} | "
            f"user_id={new_user.id} | action={action}"
        )
    except TelegramError as e:
        logger.warning(f"[BOOSTER] Could not restrict user {new_user.id}: {e}")


async def send_boost_message(bot, chat, new_user, config: dict, record: dict):
    """Send the boost requirement message to new member."""
    message_template = config.get(
        'force_add_message',
        "👋 Welcome {first_name}!\n\n"
        "This group requires you to invite {required} member(s) "
        "before you can send messages.\n\n"
        "🔗 Your personal invite link:\n{link}\n\n"
        "📊 Progress: {bar} {current}/{required}\n\n"
        "Share your link and you'll unlock access automatically!"
    )
    
    # Format the message
    current = record.get('invited_count', 0) + record.get('manual_credits', 0)
    required = record.get('required_count', config.get('force_add_required', 5))
    remaining = max(0, required - current)
    bar = make_progress_bar(current, required, config.get('force_add_progress_style', 'blocks'))
    
    # Personal link would be generated - using placeholder for now
    link = f"https://t.me/{chat.username}?invite=pending"
    
    message = message_template.format(
        first_name=new_user.first_name or "there",
        required=required,
        current=current,
        remaining=remaining,
        link=link,
        bar=bar
    )
    
    try:
        await bot.send_message(chat.id, message, parse_mode='HTML')
    except TelegramError as e:
        logger.warning(f"[BOOSTER] Could not send boost message: {e}")


async def notify_admins_manual_add(bot, chat, new_user, added_by_id, config: dict):
    """Notify admins about a manual add."""
    from bot.utils.permissions import is_admin
    
    # Get admins
    try:
        admins = await bot.get_chat_administrators(chat.id)
    except TelegramError:
        return
    
    # Build keyboard for assignment
    keyboard = [
        [
            InlineKeyboardButton(
                "👤 Assign Credit",
                callback_data=f"booster:assign:{new_user.id}"
            )
        ]
    ]
    
    added_by_str = f"by admin/user {added_by_id}" if added_by_id else "unknown"
    
    for admin in admins:
        if admin.user.is_bot:
            continue
        try:
            await bot.send_message(
                admin.user.id,
                f"👤 *Manual Add Detected*\n\n"
                f"New member: {new_user.first_name or 'Unknown'}"
                f"{f' (@{new_user.username})' if new_user.username else ''}\n"
                f"Added: {added_by_str}\n\n"
                f"Since this wasn't via an invite link, no automatic credit was given.\n"
                f"Would you like to assign credit to someone?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except (TelegramError, Forbidden):
            pass


async def send_witness_dm(bot, new_user, chat, config: dict):
    """Send DM to new member asking who invited them."""
    await asyncio.sleep(30)  # Wait for user to settle
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📋 Select who invited me",
                callback_data=f"witness:select:{chat.id}:{new_user.id}"
            )
        ],
        [
            InlineKeyboardButton(
                "❓ I don't know",
                callback_data=f"witness:unknown:{chat.id}:{new_user.id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🚫 Nobody — I found it myself",
                callback_data=f"witness:self:{chat.id}:{new_user.id}"
            )
        ]
    ])
    
    try:
        await bot.send_message(
            new_user.id,
            f"👋 Hey {new_user.first_name}!\n\n"
            f"You were recently added to *{chat.title}*.\n\n"
            f"Do you know who invited you? "
            f"Letting us know helps them earn credit! 🎯",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        logger.info(f"[BOOSTER] Witness DM sent | group_id={chat.id} | user_id={new_user.id}")
    except Forbidden:
        logger.debug(f"[BOOSTER] Witness DM blocked (user has bot DMs off) | user_id={new_user.id}")
    except TelegramError as e:
        logger.warning(f"[BOOSTER] Witness DM error: {e}")


async def handle_channel_gate(bot, chat, new_user, config: dict):
    """Handle channel gate verification."""
    from db.ops.booster import (
        create_channel_record, set_channel_restricted, get_channel_record
    )
    
    channel_id = config.get('force_channel_id')
    if not channel_id:
        return
    
    # Check if user is member of channel
    try:
        member = await bot.get_chat_member(channel_id, new_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            # User is member - verify them
            await create_channel_record(
                group_id=chat.id,
                user_id=new_user.id,
                username=new_user.username,
                channel_id=channel_id
            )
            await set_channel_verified(chat.id, new_user.id)
            logger.info(
                f"[FCHANNEL] Verified | group_id={chat.id} | "
                f"user_id={new_user.id} | channel={channel_id}"
            )
            return
    except TelegramError:
        pass
    
    # Not a member - apply restriction
    await create_channel_record(
        group_id=chat.id,
        user_id=new_user.id,
        username=new_user.username,
        channel_id=channel_id
    )
    await set_channel_restricted(chat.id, new_user.id, True)
    
    # Send gate message
    message_template = config.get(
        'force_channel_message',
        "📢 You must join our channel to participate here.\n\n"
        "After joining, tap ✅ I Joined to verify."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I Joined", callback_data=f"channel:verify:{chat.id}:{new_user.id}")]
    ])
    
    try:
        await bot.send_message(
            new_user.id,
            message_template,
            reply_markup=keyboard
        )
    except (TelegramError, Forbidden):
        pass
    
    # Restrict in group
    action = config.get('force_channel_action', 'restrict')
    if action == 'restrict':
        try:
            await bot.restrict_chat_member(
                chat.id, new_user.id,
                permissions={
                    "can_send_messages": False,
                    "can_send_media_messages": False,
                    "can_send_other_messages": False,
                    "can_add_web_page_previews": False
                }
            )
        except TelegramError:
            pass
    
    logger.info(
        f"[FCHANNEL] Gate applied | group_id={chat.id} | "
        f"user_id={new_user.id} | channel={channel_id}"
    )


# ==================== Telegram Handlers ====================

async def chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ChatMemberUpdated - main entry point for member changes."""
    member = update.chat_member
    if not member:
        return
    
    # Only handle new memberships
    if member.new_chat_member.status not in ['member', 'restricted']:
        return
    
    # Get config
    from db.ops.booster import get_boost_config, get_channel_gate_config
    
    boost_config = await get_boost_config(update.effective_chat.id)
    channel_config = await get_channel_gate_config(update.effective_chat.id)
    
    # Merge configs (channel gate settings are in channel_config)
    config = {**boost_config, **channel_config}
    
    await handle_new_member(context.bot, update, config)


# ==================== Admin Commands ====================

async def boost_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show boost status - /booststatus"""
    from db.ops.booster import get_boost_config, get_boost_stats
    
    chat = update.effective_chat
    if not await check_admin(context, update):
        return
    
    config = await get_boost_config(chat.id)
    stats = await get_boost_stats(chat.id)
    
    status_emoji = "✅ Active" if config.get('force_add_enabled') else "❌ Disabled"
    mode = config.get('force_add_action', 'mute')
    
    message = f"""⚡ **Nexus Boost Status**

**Status:** {status_emoji}
**Required invites:** {config.get('force_add_required', 0)}
**Mode:** {mode}

**📊 Stats:**
• Total boosting: {stats.get('total_records', 0)}
• Still locked: {stats.get('locked_count', 0)}
• Completed: {stats.get('unlocked_count', 0)}
• Exempted: {stats.get('exempted_count', 0)}

**🏆 Top Inviters:**"""
    
    for i, inviter in enumerate(stats.get('top_inviters', [])[:5], 1):
        name = inviter.get('username') or inviter.get('first_name', 'Unknown')
        count = inviter.get('total_invites', 0)
        message += f"\n{i}. @{name} — {count} invited"
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def boost_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set boost requirement - /boostset <number>"""
    from db.ops.booster import get_boost_config, save_boost_config
    
    if not await check_admin(context, update):
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /boostset <number>")
        return
    
    try:
        required = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid number.")
        return
    
    if required < 1:
        await update.message.reply_text("Minimum is 1 invite.")
        return
    
    chat = update.effective_chat
    config = await get_boost_config(chat.id)
    config['force_add_enabled'] = True
    config['force_add_required'] = required
    
    await save_boost_config(chat.id, config)
    
    await update.message.reply_text(
        f"✅ Boost requirement set to *{required}* invites.\n\n"
        f"Members who join from now must invite {required} people to unlock.",
        parse_mode='Markdown'
    )


async def boost_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable boost - /boostoff"""
    from db.ops.booster import get_boost_config, save_boost_config, get_all_boost_records
    
    if not await check_admin(context, update):
        return
    
    chat = update.effective_chat
    config = await get_boost_config(chat.id)
    
    if not config.get('force_add_enabled'):
        await update.message.reply_text("Boost is already disabled.")
        return
    
    # Get restricted members
    records = await get_all_boost_records(chat.id)
    restricted = [r for r in records if r.get('is_restricted') and not r.get('is_unlocked')]
    
    if restricted:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, disable", callback_data="boost:confirm_off"),
                InlineKeyboardButton("❌ Cancel", callback_data="boost:cancel_off")
            ]
        ])
        await update.message.reply_text(
            f"⚠️ Disable boost? {len(restricted)} members are currently locked.\n\n"
            f"All muted members will be unmuted.",
            reply_markup=keyboard
        )
    else:
        config['force_add_enabled'] = False
        await save_boost_config(chat.id, config)
        await update.message.reply_text("✅ Boost disabled.")


async def boost_exempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exempt user from boost - /boostexempt @user"""
    from db.ops.booster import set_exempted
    
    if not await check_admin(context, update):
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /boostexempt @user [reason]")
        return
    
    user = await extract_user_from_args(update, context)
    if not user:
        return
    
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Admin exempted"
    
    await set_exempted(
        chat_id=update.effective_chat.id,
        user_id=user.id,
        exempted=True,
        exempted_by=update.effective_user.id,
        reason=reason
    )
    
    # Unrestrict if currently restricted
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, user.id,
            permissions={
                "can_send_messages": True,
                "can_send_media_messages": True,
                "can_send_other_messages": True,
                "can_add_web_page_previews": True
            }
        )
    except TelegramError:
        pass
    
    await update.message.reply_text(
        f"✅ @{user.username or user.first_name} has been exempted from boost requirement.\n"
        f"Reason: {reason}"
    )


async def boost_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset user's boost - /boostreset @user"""
    from db.ops.booster import reset_boost_record
    
    if not await check_admin(context, update):
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /boostreset @user")
        return
    
    user = await extract_user_from_args(update, context)
    if not user:
        return
    
    await reset_boost_record(update.effective_chat.id, user.id)
    
    await update.message.reply_text(
        f"✅ @{user.username or user.first_name}'s boost progress has been reset."
    )


async def boost_grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant access without invites - /boostgrant @user"""
    from db.ops.booster import grant_access
    
    if not await check_admin(context, update):
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /boostgrant @user")
        return
    
    user = await extract_user_from_args(update, context)
    if not user:
        return
    
    await grant_access(update.effective_chat.id, user.id)
    
    # Unrestrict
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, user.id,
            permissions={
                "can_send_messages": True,
                "can_send_media_messages": True,
                "can_send_other_messages": True,
                "can_add_web_page_previews": True
            }
        )
    except TelegramError:
        pass
    
    await update.message.reply_text(
        f"✅ @{user.username or user.first_name} has been granted access!"
    )


# ==================== Member Commands ====================

async def boost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show member's boost status - /boost"""
    from db.ops.booster import get_boost_record, get_boost_config
    
    user = update.effective_user
    chat = update.effective_chat
    
    config = await get_boost_config(chat.id)
    record = await get_boost_record(chat.id, user.id)
    
    if not record:
        await update.message.reply_text(
            "No boost requirement is active for you in this group."
        )
        return
    
    current = record.get('invited_count', 0) + record.get('manual_credits', 0)
    required = record.get('required_count', config.get('force_add_required', 5))
    remaining = max(0, required - current)
    bar = make_progress_bar(current, required, config.get('force_add_progress_style', 'blocks'))
    
    message = f"""⚡ **Your Boost Status**

**Progress:** {bar}
**Invited:** {record.get('invited_count', 0)}
**Manual credits:** {record.get('manual_credits', 0)}
**Remaining:** {remaining}

Your link: https://t.me/{chat.username}?invite=pending"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def mylink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show member's invite link - /mylink"""
    chat = update.effective_chat
    
    link = f"https://t.me/{chat.username}?invite=pending"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Link", url=f"t.me/{chat.username}?invite=pending")]
    ])
    
    await update.message.reply_text(
        f"🔗 Your invite link:\n{link}",
        reply_markup=keyboard
    )


async def remain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show remaining invites needed - /remain"""
    from db.ops.booster import get_boost_record, get_boost_config
    
    user = update.effective_user
    chat = update.effective_chat
    
    config = await get_boost_config(chat.id)
    record = await get_boost_record(chat.id, user.id)
    
    if not record or record.get('is_unlocked'):
        await update.message.reply_text(
            "✅ You've completed your boost! No more invites needed."
        )
        return
    
    current = record.get('invited_count', 0) + record.get('manual_credits', 0)
    required = record.get('required_count', config.get('force_add_required', 5))
    remaining = max(0, required - current)
    
    await update.message.reply_text(
        f"You need to invite *{remaining}* more member(s) to unlock messaging.",
        parse_mode='Markdown'
    )


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show visual progress - /progress"""
    from db.ops.booster import get_boost_record, get_boost_config
    
    user = update.effective_user
    chat = update.effective_chat
    
    config = await get_boost_config(chat.id)
    record = await get_boost_record(chat.id, user.id)
    
    if not record:
        await update.message.reply_text("No boost requirement active.")
        return
    
    current = record.get('invited_count', 0) + record.get('manual_credits', 0)
    required = record.get('required_count', config.get('force_add_required', 5))
    bar = make_progress_bar(current, required, config.get('force_add_progress_style', 'blocks'))
    
    message = f"""⚡ **Boost Progress**

{bar}

✅ Invited via link: {record.get('invited_count', 0)}
✅ Manual credits: {record.get('manual_credits', 0)}
⏳ Remaining: {max(0, required - current)}"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def invited_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show people user has invited - /invited"""
    from db.ops.booster import get_user_invites
    
    user = update.effective_user
    chat = update.effective_chat
    
    invites = await get_user_invites(chat.id, user.id)
    
    if not invites:
        await update.message.reply_text("You haven't invited anyone yet.")
        return
    
    message = f"👥 **Your Invites ({len(invites)})**\n\n"
    
    for i, inv in enumerate(invites[:10], 1):
        name = inv.get('invited_username') or inv.get('invited_first_name', 'Unknown')
        source = inv.get('source', 'link')
        message += f"{i}. @{name} — via {source}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def addcreditme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request manual add credit - /addcreditme <count>"""
    from db.ops.booster import create_credit_request, get_recent_manual_adds
    
    if not context.args:
        await update.message.reply_text("Usage: /addcreditme <count>")
        return
    
    try:
        count = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid number.")
        return
    
    user = update.effective_user
    chat = update.effective_chat
    
    # Get recent manual adds
    recent = await get_recent_manual_adds(chat.id, hours=2)
    matched = len(recent)
    
    # Create credit request
    await create_credit_request(
        group_id=chat.id,
        claimant_user_id=user.id,
        claimant_username=user.username,
        claimed_count=count
    )
    
    message = f"""📋 Credit Request Submitted

You claimed to have manually added *{count}* member(s).

Recent manual adds detected: *{matched}*

An admin will review your request."""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def boosttop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show leaderboard - /boosttop"""
    from db.ops.booster import get_boost_stats
    
    chat = update.effective_chat
    stats = await get_boost_stats(chat.id)
    
    inviters = stats.get('top_inviters', [])
    
    if not inviters:
        await update.message.reply_text("No invites recorded yet.")
        return
    
    message = "🏆 **Boost Leaderboard**\n\n"
    
    medals = ['🥇', '🥈', '🥉']
    for i, inv in enumerate(inviters, 1):
        name = inv.get('username') or inv.get('first_name', 'Unknown')
        count = inv.get('total_invites', 0)
        medal = medals[i-1] if i <= 3 else f"{i}."
        message += f"{medal} @{name} — {count} invited\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def invitedby_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show who invited a user - /invitedby @user"""
    from db.ops.booster import get_invited_by
    
    if not context.args:
        await update.message.reply_text("Usage: /invitedby @user")
        return
    
    user = await extract_user_from_args(update, context)
    if not user:
        return
    
    chat = update.effective_chat
    inviter = await get_invited_by(chat.id, user.id)
    
    if not inviter:
        await update.message.reply_text(
            f"@{user.username or user.first_name} has no invite record."
        )
        return
    
    inviter_id = inviter.get('inviter_user_id')
    source = inviter.get('source', 'link')
    
    if inviter_id:
        await update.message.reply_text(
            f"👤 @{user.username or user.first_name} was invited via {source}."
        )
    else:
        await update.message.reply_text(
            f"👤 @{user.username or user.first_name} was manually added (source unknown)."
        )


# ==================== Channel Commands ====================

async def setchannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set required channel - /setchannel @channel"""
    from db.ops.booster import get_channel_gate_config, save_channel_gate_config
    
    if not await check_admin(context, update):
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /setchannel @channel")
        return
    
    channel_input = context.args[0]
    
    # Extract channel username or ID
    if channel_input.startswith('@'):
        channel_username = channel_input[1:]
        channel_id = None
    elif channel_input.startswith('-100'):
        try:
            channel_id = int(channel_input)
            channel_username = None
        except ValueError:
            await update.message.reply_text("Invalid channel ID format.")
            return
    else:
        channel_username = channel_input
    
    chat = update.effective_chat
    config = await get_channel_gate_config(chat.id)
    config['force_channel_enabled'] = True
    config['force_channel_id'] = channel_id
    config['force_channel_username'] = channel_username
    
    await save_channel_gate_config(chat.id, config)
    
    await update.message.reply_text(
        f"✅ Members must now join @{channel_username or channel_id} to chat here."
    )


async def removechannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove channel requirement - /removechannel"""
    from db.ops.booster import get_channel_gate_config, save_channel_gate_config, delete_all_channel_records
    
    if not await check_admin(context, update):
        return
    
    chat = update.effective_chat
    await delete_all_channel_records(chat.id)
    
    config = await get_channel_gate_config(chat.id)
    config['force_channel_enabled'] = False
    config['force_channel_id'] = None
    config['force_channel_username'] = None
    
    await save_channel_gate_config(chat.id, config)
    
    await update.message.reply_text("✅ Channel requirement removed.")


async def channelstatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show channel gate status - /channelstatus"""
    from db.ops.booster import get_channel_gate_config, get_channel_stats
    
    chat = update.effective_chat
    if not await check_admin(context, update):
        return
    
    config = await get_channel_gate_config(chat.id)
    stats = await get_channel_stats(chat.id)
    
    status = "✅ Active" if config.get('force_channel_enabled') else "❌ Disabled"
    channel = config.get('force_channel_username') or config.get('force_channel_id') or "Not set"
    action = config.get('force_channel_action', 'restrict')
    
    message = f"""📢 **Force Channel Status**

**Status:** {status}
**Channel:** @{channel}
**Action:** {action}

**📊 Stats:**
• Pending verification: {stats.get('pending_count', 0)}
• Verified: {stats.get('verified_count', 0)}
• Avg verification time: {stats.get('avg_verify_seconds', 0)}s"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


# ==================== Utility Functions ====================

async def check_admin(context, update: Update) -> bool:
    """Check if user is admin."""
    from bot.utils.permissions import is_admin
    return await is_admin(update, context)


async def extract_user_from_args(update: Update, context) -> Optional[object]:
    """Extract user from command arguments."""
    if not context.args:
        return None
    
    arg = context.args[0]
    
    if arg.startswith('@'):
        # Username - need to resolve
        await update.message.reply_text(
            "Please reply to a user's message to mention them."
        )
        return None
    
    # Try as user ID
    try:
        user_id = int(arg)
        # Try to get user from chat
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            return member.user
        except TelegramError:
            await update.message.reply_text("User not found in this chat.")
            return None
    except ValueError:
        await update.message.reply_text("Invalid user.")
        return None


# ==================== Callback Handlers ====================

async def booster_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle booster-related callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("booster:assign:"):
        # Handle manual add credit assignment
        user_id = int(data.split(':')[-1])
        await query.edit_message_text(
            f"Assigning credit for user {user_id}...\n\n"
            f"Use /assignadd @inviter @{user_id} to assign credit."
        )
    
    elif data == "boost:confirm_off":
        from db.ops.booster import get_boost_config, save_boost_config
        chat = query.message.chat
        config = await get_boost_config(chat.id)
        config['force_add_enabled'] = False
        await save_boost_config(chat.id, config)
        
        # Unrestrict all
        from db.ops.booster import get_all_boost_records
        records = await get_all_boost_records(chat.id)
        for record in records:
            if record.get('is_restricted') and not record.get('is_unlocked'):
                try:
                    await context.bot.restrict_chat_member(
                        chat.id, record['user_id'],
                        permissions={
                            "can_send_messages": True,
                            "can_send_media_messages": True,
                            "can_send_other_messages": True,
                            "can_add_web_page_previews": True
                        }
                    )
                except TelegramError:
                    pass
        
        await query.edit_message_text("✅ Boost disabled. All members unmuted.")
    
    elif data == "boost:cancel_off":
        await query.edit_message_text("Cancelled.")


async def channel_verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel verification callback."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("channel:verify:"):
        parts = data.split(':')
        chat_id = int(parts[2])
        user_id = int(parts[3])
        
        # Verify user is the one clicking
        if update.effective_user.id != user_id:
            await query.answer("This button isn't for you!", show_alert=True)
            return
        
        # Get config
        from db.ops.booster import get_channel_gate_config
        config = await get_channel_gate_config(chat_id)
        channel_id = config.get('force_channel_id')
        
        if not channel_id:
            await query.edit_message_text("Channel requirement has been removed.")
            return
        
        # Check if user joined channel
        try:
            member = await context.bot.get_chat_member(channel_id, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                await query.answer("You haven't joined the channel yet!", show_alert=True)
                return
        except TelegramError:
            await query.answer("Could not verify. Please try again.", show_alert=True)
            return
        
        # Verify and unrestrict
        from db.ops.booster import set_channel_verified, create_channel_record
        await create_channel_record(chat_id, user_id, channel_id=channel_id)
        await set_channel_verified(chat_id, user_id)
        
        try:
            await context.bot.restrict_chat_member(
                chat_id, user_id,
                permissions={
                    "can_send_messages": True,
                    "can_send_media_messages": True,
                    "can_send_other_messages": True,
                    "can_add_web_page_previews": True
                }
            )
        except TelegramError:
            pass
        
        await query.edit_message_text("✅ You're verified! You can now send messages.")


# ==================== Message Handler for Channel Gate ====================

async def check_channel_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check channel verification on each message."""
    if not update.message or not update.message.from_user:
        return
    
    user = update.message.from_user
    chat = update.message.chat
    
    # Ignore bots and admins
    if user.is_bot:
        return
    
    from db.ops.booster import get_channel_gate_config, get_channel_record
    
    config = await get_channel_gate_config(chat.id)
    
    if not config.get('force_channel_enabled'):
        return
    
    # Check if admin or exempt
    if await is_admin_or_exempt(chat.id, user.id, config, context.bot):
        return
    
    # Check verification status
    record = await get_channel_record(chat.id, user.id)
    
    if not record or not record.get('is_verified'):
        # Check channel membership
        channel_id = config.get('force_channel_id')
        try:
            member = await context.bot.get_chat_member(channel_id, user.id)
            if member.status in ['member', 'administrator', 'creator']:
                # Now a member - verify them
                await create_channel_record(chat.id, user.id, user.username, channel_id)
                await set_channel_verified(chat.id, user.id)
                return
        except TelegramError:
            pass
        
        # Delete message and notify
        try:
            await update.message.delete()
        except TelegramError:
            pass

        action = config.get('force_channel_action', 'restrict')
        if action == 'restrict':
            try:
                await context.bot.restrict_chat_member(
                    chat.id, user.id,
                    permissions={
                        "can_send_messages": False,
                        "can_send_media_messages": False,
                        "can_send_other_messages": False,
                        "can_add_web_page_previews": False
                    }
                )
            except TelegramError:
                pass


# ==================== Register Handlers ====================

def register_handlers(app):
    """Register all booster handlers with the application."""
    from bot.utils.aliases import register_aliases
    
    GROUP = filters.ChatType.GROUPS
    PRIVATE = filters.ChatType.PRIVATE
    
    # Chat member handler for join detection
    app.add_handler(ChatMemberHandler(chat_member_handler, ChatMemberHandler.CHAT_MEMBER))
    
    # Message handler for channel gate checks
    app.add_handler(MessageHandler(GROUP, check_channel_on_message), group=10)
    
    # Boost commands
    app.add_handler(CommandHandler("booststatus", boost_status, filters=GROUP))
    app.add_handler(CommandHandler("boostset", boost_set, filters=GROUP))
    app.add_handler(CommandHandler("boostoff", boost_off, filters=GROUP))
    app.add_handler(CommandHandler("boostexempt", boost_exempt, filters=GROUP))
    app.add_handler(CommandHandler("boostunexempt", boost_exempt, filters=GROUP))
    app.add_handler(CommandHandler("boostreset", boost_reset, filters=GROUP))
    app.add_handler(CommandHandler("boostgrant", boost_grant, filters=GROUP))
    app.add_handler(CommandHandler("boostrevoke", boost_grant, filters=GROUP))
    app.add_handler(CommandHandler("boosttop", boosttop_command, filters=GROUP))
    app.add_handler(CommandHandler("boostlog", boost_status, filters=GROUP))
    
    # Member-facing boost commands
    app.add_handler(CommandHandler("boost", boost_command))
    app.add_handler(CommandHandler("mylink", mylink_command))
    app.add_handler(CommandHandler("remain", remain_command))
    app.add_handler(CommandHandler("progress", progress_command))
    app.add_handler(CommandHandler("invited", invited_command))
    app.add_handler(CommandHandler("addcreditme", addcreditme_command))
    app.add_handler(CommandHandler("invitedby", invitedby_command))
    app.add_handler(CommandHandler("whoinvited", invitedby_command))
    
    # Channel commands
    app.add_handler(CommandHandler("setchannel", setchannel_command, filters=GROUP))
    app.add_handler(CommandHandler("removechannel", removechannel_command, filters=GROUP))
    app.add_handler(CommandHandler("channelstatus", channelstatus_command, filters=GROUP))
    app.add_handler(CommandHandler("channelcheck", channelstatus_command, filters=GROUP))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(booster_callback, pattern=r'^booster:'))
    app.add_handler(CallbackQueryHandler(channel_verify_callback, pattern=r'^channel:verify:'))
    app.add_handler(CallbackQueryHandler(channel_verify_callback, pattern=r'^witness:'))
    
    # Register aliases
    booster_aliases = {
        "/boost": boost_command,
        "+invite": boost_command,
        "/remain": remain_command,
        "/mylink": mylink_command,
        "/progress": progress_command,
        "/invited": invited_command,
        "/addcreditme": addcreditme_command,
        "/invitedby": invitedby_command,
        "/whoinvited": invitedby_command,
    }
    register_aliases(app, booster_aliases)
    
    logger.info("[BOOSTER] All handlers registered")


# Import Optional for type hints
from typing import Optional
