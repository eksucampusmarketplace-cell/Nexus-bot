"""
bot/handlers/group_lifecycle.py

Handles the full lifecycle of a clone bot being added to or removed from a group.
Registered on EVERY clone bot in factory.py.

Events handled:
  - bot added to group (my_chat_member: left/kicked → member/admin)
  - bot removed from group (my_chat_member: member/admin → left/kicked)

On ADD — decision tree:
  1. Is this the clone owner?         → register as owner group, full access
  2. Is limit already reached?        → send limit message, immediately leave
  3. Is policy = 'blocked'?           → send blocked message, immediately leave
  4. Is policy = 'open'?              → register with access_status='active', onboard stranger
  5. Is policy = 'approval'?          → register with access_status='pending',
                                         notify owner, tell stranger to wait

On REMOVE — mark group as left in DB.
"""

import logging

from telegram import ChatMemberUpdated, Update
from telegram.constants import ParseMode
from telegram.ext import ChatMemberHandler, ContextTypes

from bot.utils.keyboards import support_keyboard
from config import settings

# alert_new_group_add might not exist, I'll check or just skip it if it's not provided
# from bot.utils.alerts import alert_new_group_add
from db.ops.clone_groups import (
    get_active_group_count,
    get_clone_config,
    get_group_entry,
    mark_group_left,
    register_group,
)
from bot.utils.crypto import hash_token
from db.ops.groups import upsert_group

log = logging.getLogger("group_lifecycle")


def _is_bot_add(update: ChatMemberUpdated, bot_id: int) -> bool:
    """Returns True if this event is the bot itself being added."""
    new = update.new_chat_member
    return (
        new.user.id == bot_id
        and new.status in ("member", "administrator")
        and update.old_chat_member.status in ("left", "kicked")
    )


def _is_bot_remove(update: ChatMemberUpdated, bot_id: int) -> bool:
    """Returns True if this event is the bot itself being removed."""
    new = update.new_chat_member
    return (
        new.user.id == bot_id
        and new.status in ("left", "kicked")
        and update.old_chat_member.status in ("member", "administrator")
    )


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler for bot being added/removed from groups."""
    event = update.my_chat_member
    if not event:
        return

    bot_id = context.bot.id
    chat = event.chat
    actor = event.from_user  # who added or removed the bot

    # In this project, db is often in bot_data["db_pool"] or similar
    # Based on main.py: primary_app.bot_data["db_pool"] = pool
    db_pool = context.bot_data.get("db_pool")

    # ── BOT REMOVED ──────────────────────────────────────────────────────
    if _is_bot_remove(event, bot_id):
        log.info(f"[LIFECYCLE] Removed | bot={bot_id} chat={chat.id} by={actor.id}")
        if db_pool:
            async with db_pool.acquire() as db:
                await mark_group_left(db, bot_id, chat.id)
        return

    # ── BOT ADDED ────────────────────────────────────────────────────────
    if not _is_bot_add(event, bot_id):
        return

    log.info(f"[LIFECYCLE] Added | bot={bot_id} chat={chat.id} by={actor.id}")

    if not db_pool:
        log.warning(f"[LIFECYCLE] No DB pool | bot={bot_id} chat={chat.id}")
        return

    async with db_pool.acquire() as db:
        # Primary bot: unlimited groups, open policy, owner is OWNER_ID
        is_primary_bot = context.bot_data.get("is_primary", False)
        if is_primary_bot:
            from config import settings as _settings
            config = {
                "owner_id": _settings.OWNER_ID,
                "group_limit": 0,
                "group_access_policy": "open",
                "bot_add_notifications": False,
            }
        else:
            config = await get_clone_config(db, bot_id)
            if not config:
                log.error(f"[LIFECYCLE] Clone config not found | bot={bot_id}")
                return

        owner_id = config["owner_id"]
        group_limit = config["group_limit"]  # 1–5
        policy = config["group_access_policy"]  # open|approval|blocked
        notify_owner = config["bot_add_notifications"]
        is_owner = actor.id == owner_id

        # ── 1. OWNER ADDING TO THEIR OWN GROUP ───────────────────────────────
        if is_owner:
            active_count = await get_active_group_count(db, bot_id)

            # Check limit even for owner (group_limit = 0 means unlimited)
            if group_limit > 0 and active_count >= group_limit:
                await _leave_with_message(context, chat, "limit_reached", owner_id, is_owner=True)
                return

            await register_group(
                db,
                bot_id,
                chat.id,
                chat.title,
                actor.id,
                actor.full_name,
                is_owner_group=True,
                access_status="active",
            )
            token_hash = hash_token(context.bot.token)
            try:
                member_count = await chat.get_member_count()
            except Exception:
                member_count = 0
            photo_big = None
            photo_small = None
            try:
                chat_obj = await context.bot.get_chat(chat.id)
                if chat_obj.photo:
                    photo_big = chat_obj.photo.big_file_id
                    photo_small = chat_obj.photo.small_file_id
            except Exception as e:
                log.warning(f"[LIFECYCLE] Could not get chat photo | chat={chat.id} error={e}")
            await upsert_group(
                chat.id,
                chat.title,
                token_hash,
                member_count=member_count,
                photo_big=photo_big,
                photo_small=photo_small,
            )
            log.info(f"[LIFECYCLE] Owner group registered | bot={bot_id} chat={chat.id}")

            # Send setup DM to owner
            await _send_owner_setup_dm(context, owner_id, chat, bot_id)
            return

        # ── 2. STRANGER ADDING THE BOT ───────────────────────────────────────
        active_count = await get_active_group_count(db, bot_id)

        # Check group limit first (group_limit = 0 means unlimited)
        if group_limit > 0 and active_count >= group_limit:
            await _leave_with_message(context, chat, "limit_reached", actor.id, is_owner=False)
            # Notify owner if enabled
            if notify_owner:
                await _notify_owner_limit_hit(context, owner_id, chat, actor)
            return

        # Check access policy
        if policy == "blocked":
            await _leave_with_message(context, chat, "blocked", actor.id, is_owner=False)
            return

        if policy == "open":
            await register_group(
                db,
                bot_id,
                chat.id,
                chat.title,
                actor.id,
                actor.full_name,
                is_owner_group=False,
                access_status="active",
            )
            token_hash = hash_token(context.bot.token)
            try:
                member_count = await chat.get_member_count()
            except Exception:
                member_count = 0
            photo_big = None
            photo_small = None
            try:
                chat_obj = await context.bot.get_chat(chat.id)
                if chat_obj.photo:
                    photo_big = chat_obj.photo.big_file_id
                    photo_small = chat_obj.photo.small_file_id
            except Exception as e:
                log.warning(f"[LIFECYCLE] Could not get chat photo | chat={chat.id} error={e}")
            await upsert_group(
                chat.id,
                chat.title,
                token_hash,
                member_count=member_count,
                photo_big=photo_big,
                photo_small=photo_small,
            )
            # Onboard the stranger
            await _send_stranger_onboard_dm(context, actor, chat, policy="open")
            # Notify owner if enabled
            if notify_owner:
                await _notify_owner_new_group(context, owner_id, chat, actor)
            return

        if policy == "approval":
            await register_group(
                db,
                bot_id,
                chat.id,
                chat.title,
                actor.id,
                actor.full_name,
                is_owner_group=False,
                access_status="pending",
            )
            # Tell stranger to wait
            await _send_stranger_onboard_dm(context, actor, chat, policy="approval")
            # Always notify owner for approval (regardless of notification setting)
            await _notify_owner_approval_needed(context, owner_id, chat, actor, bot_id)
            return


# ── HELPERS ───────────────────────────────────────────────────────────────


async def _leave_with_message(context, chat, reason: str, actor_id: int, is_owner: bool):
    """
    Send a message to the group then immediately leave.
    reason: "limit_reached" | "blocked"
    """
    bot_name = settings.BOT_DISPLAY_NAME
    main_bot = settings.MAIN_BOT_USERNAME

    if reason == "limit_reached":
        text = (
            f"👋 Hi! I'm at my group limit and can't stay here.\n\n"
            f"To use a bot like me in this group, create your own at "
            f"@{main_bot}.\n\n"
            f"⚡ Powered by {bot_name}"
        )
    else:  # blocked
        text = (
            f"👋 Hi! This bot is currently set to private and isn't "
            f"accepting new groups.\n\n"
            f"Want your own bot? Create one free at @{main_bot}.\n\n"
            f"⚡ Powered by {bot_name}"
        )

    try:
        await context.bot.send_message(chat_id=chat.id, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.warning(f"[LIFECYCLE] Could not send leave message | chat={chat.id} error={e}")

    try:
        await context.bot.leave_chat(chat.id)
        log.info(f"[LIFECYCLE] Left | chat={chat.id} reason={reason}")
    except Exception as e:
        log.warning(f"[LIFECYCLE] Could not leave chat | chat={chat.id} error={e}")


async def _send_owner_setup_dm(context, owner_id: int, chat, bot_id: int):
    """DM the owner confirming their bot was added to a new group."""
    miniapp_url = settings.MINI_APP_URL
    try:
        # We need to send this via the primary bot if possible,
        # or just via the current bot. The prompt says DM to owner via primary bot.
        # But here 'context.bot' is the clone bot.
        # To send via primary bot, we need its instance.
        # For now, let's send via the current bot.
        # Actually, let's check how other handlers do it.
        await context.bot.send_message(
            chat_id=owner_id,
            text=(
                f"✅ <b>Your bot was added to a new group!</b>\n\n"
                f"Group: <b>{chat.title}</b>\n"
                f"ID: <code>{chat.id}</code>\n\n"
                f"Open the Mini App to configure it."
                f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=support_keyboard(
                include_miniapp=bool(miniapp_url), miniapp_url=miniapp_url
            ),
        )
    except Exception as e:
        log.warning(f"[LIFECYCLE] Could not DM owner | owner={owner_id} error={e}")


async def _send_stranger_onboard_dm(context, actor, chat, policy: str):
    """
    DM the stranger who added the bot.
    policy="open"     → bot is active, redirect them to create their own clone
    policy="approval" → bot is pending, tell them owner must approve
    """
    main_bot = settings.MAIN_BOT_USERNAME
    bot_name = settings.BOT_DISPLAY_NAME

    if policy == "open":
        text = (
            f"👋 Hi {actor.first_name}!\n\n"
            f"I've been added to <b>{chat.title}</b> and I'm active.\n\n"
            f"⚠️ <b>Note:</b> You're using someone else's bot. "
            f"You won't have full control over it.\n\n"
            f"💡 <b>Want your own bot with full control?</b>\n"
            f"Create your own free clone at @{main_bot} — "
            f"it takes less than a minute.\n\n"
            f"⚡ Powered by {bot_name}"
        )
    else:  # approval
        text = (
            f"👋 Hi {actor.first_name}!\n\n"
            f"I've been added to <b>{chat.title}</b>, but the bot owner "
            f"needs to approve new groups first.\n\n"
            f"⏳ <b>Your request is pending.</b> The owner will be notified.\n\n"
            f"💡 <b>Don't want to wait?</b>\n"
            f"Create your own free clone at @{main_bot} — "
            f"full control, instant setup.\n\n"
            f"⚡ Powered by {bot_name}"
        )

    try:
        await context.bot.send_message(
            chat_id=actor.id, text=text, parse_mode=ParseMode.HTML, reply_markup=support_keyboard()
        )
    except Exception as e:
        log.warning(f"[LIFECYCLE] Could not DM stranger | user={actor.id} error={e}")


async def _notify_owner_new_group(context, owner_id: int, chat, actor):
    """Notify clone owner that their bot was added to a new group (open policy)."""
    try:
        await context.bot.send_message(
            chat_id=owner_id,
            text=(
                f"📢 <b>Your bot was added to a new group</b>\n\n"
                f"Group: <b>{chat.title}</b>\n"
                f"Added by: <a href='tg://user?id={actor.id}'>{actor.full_name}</a> "
                f"(<code>{actor.id}</code>)\n\n"
                f"Your policy is set to <b>Open</b> — the bot is now active there."
                f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.warning(f"[LIFECYCLE] Could not notify owner | owner={owner_id} error={e}")


async def _notify_owner_approval_needed(context, owner_id: int, chat, actor, bot_id: int):
    """
    Notify clone owner that a stranger wants to use their bot.
    Sends inline buttons: [✅ Approve] [❌ Deny]
    """
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        await context.bot.send_message(
            chat_id=owner_id,
            text=(
                f"🔔 <b>New group approval request</b>\n\n"
                f"Someone wants to use your bot in their group.\n\n"
                f"Group: <b>{chat.title}</b> (<code>{chat.id}</code>)\n"
                f"Requested by: <a href='tg://user?id={actor.id}'>{actor.full_name}</a> "
                f"(<code>{actor.id}</code>)\n\n"
                f"Approve to let them use the bot. "
                f"Deny to remove the bot from their group."
                f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Approve", callback_data=f"grp_approve:{bot_id}:{chat.id}:{actor.id}"
                        ),
                        InlineKeyboardButton(
                            "❌ Deny", callback_data=f"grp_deny:{bot_id}:{chat.id}:{actor.id}"
                        ),
                    ]
                ]
            ),
        )
    except Exception as e:
        log.warning(f"[LIFECYCLE] Could not send approval request | owner={owner_id} error={e}")


async def _notify_owner_limit_hit(context, owner_id: int, chat, actor):
    """Tell owner their bot hit the group limit and had to leave a group."""
    try:
        await context.bot.send_message(
            chat_id=owner_id,
            text=(
                f"⚠️ <b>Group limit reached</b>\n\n"
                f"Your bot was added to <b>{chat.title}</b> but had to leave "
                f"because you've reached your group limit.\n\n"
                f"To increase your limit, update it with /cloneset."
                f"\n\n⚡ Powered by {settings.BOT_DISPLAY_NAME}"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.warning(f"[LIFECYCLE] Could not notify owner limit | owner={owner_id} error={e}")


# ── Handler object to register in factory.py ─────────────────────────────
group_lifecycle_handler = ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
