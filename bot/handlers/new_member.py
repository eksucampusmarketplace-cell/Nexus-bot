"""
bot/handlers/new_member.py

Unified new member join handler.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.antiraid.engine import handle_new_member
from bot.captcha.engine import send_captcha
from db.ops.approval import is_member_approved

log = logging.getLogger("new_member")


async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle member joining or leaving."""
    chat_member = update.chat_member
    if not chat_member:
        return

    new_status = chat_member.new_chat_member.status
    old_status = chat_member.old_chat_member.status
    user = chat_member.new_chat_member.user
    chat = chat_member.chat
    db = context.bot_data.get("db")

    # ── Member joined ──────────────────────────────────────────────────────
    if new_status == "member" and old_status in ("left", "kicked", "restricted"):
        # Track the member in our database
        try:
            from db.ops.users import upsert_user

            await upsert_user(user.id, chat.id, user.username, user.first_name)
        except Exception as e:
            log.debug(f"Failed to upsert user on join: {e}")
        # Note: sometimes old_status is restricted if they were muted/restricted by bot before and left/rejoined

        get_settings = context.bot_data.get("get_settings")
        if not get_settings:
            from db.ops.automod import get_group_settings

            settings = await get_group_settings(db, chat.id)
        else:
            settings = await get_settings(chat.id)

        get_owner_id = context.bot_data.get("get_owner_id")
        if not get_owner_id:
            # Fallback
            owner_id = None
        else:
            owner_id = await get_owner_id(context.bot.id)

        # Bot inviter ban
        if user.is_bot and settings.get("bot_inviter_ban"):
            inviter = chat_member.from_user
            if inviter:
                try:
                    await context.bot.ban_chat_member(chat.id, inviter.id)
                    log.info(
                        f"[NEW_MEMBER] Bot inviter banned | " f"inviter={inviter.id} chat={chat.id}"
                    )
                except Exception:
                    pass
            return

        # Anti-raid check
        restricted = await handle_new_member(context.bot, chat.id, user, settings, db, owner_id)

        # ── New Anti-raid System Integration ──────────────────────────────────
        try:
            import time

            from bot.antiraid.detector import MemberProfile, RaidDetector

            detector = RaidDetector(context.bot_data.get("redis"), db, context.bot)
            profile = MemberProfile(
                user_id=user.id,
                joined_at=time.time(),
                has_username=bool(user.username),
                first_name=user.first_name or "",
                username=user.username or "",
            )
            threat_level = await detector.on_member_join(chat.id, profile)

            if threat_level in ("red", "critical"):
                from bot.antiraid.lockdown import LockdownManager

                lockdown = LockdownManager(context.bot_data.get("redis"), db, context.bot)
                await lockdown.activate(chat.id, f"Raid detected ({threat_level})")
        except Exception as e:
            log.error(f"New anti-raid check failed: {e}")
        # ──────────────────────────────────────────────────────────────────────

        # If anti-raid already restricted/banned the user, check if we should still do CAPTCHA
        if restricted and settings.get("antiraid_mode") != "captcha":
            return

        # CAPTCHA
        # Skip if already approved (unlikely for new join, but possible if added via app first)
        approved = await is_member_approved(db, chat.id, user.id)
        if approved:
            await _send_welcome(context.bot, chat.id, user, settings, db)
            return

        if settings.get("captcha_enabled") or (
            restricted and settings.get("antiraid_mode") == "captcha"
        ):
            # Restrict first if not already restricted
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat.id, user_id=user.id, permissions={"can_send_messages": False}
                )
            except Exception:
                pass

            # We don't have a message_id for the join event in ChatMemberHandler usually
            # unless it's a Message with new_chat_members, but we are using ChatMemberHandler.
            join_msg_id = None
            await send_captcha(context.bot, chat.id, user, settings, db, join_msg_id)
            return

        # Group password challenge
        if settings.get("group_password"):
            from bot.handlers.password import send_password_challenge

            await send_password_challenge(context.bot, chat.id, user, settings, db)
            return

        # Welcome message (if no CAPTCHA)
        await _send_welcome(context.bot, chat.id, user, settings, db)

    # ── Member left ────────────────────────────────────────────────────────
    elif new_status in ("left", "kicked") and old_status == "member":
        from db.ops.antiraid import log_member_event

        await log_member_event(db, chat.id, user, "leave" if new_status == "left" else "kick")

        get_owner_id = context.bot_data.get("get_owner_id")
        if get_owner_id:
            owner_id = await get_owner_id(context.bot.id)
            if owner_id:
                from api.routes.events import push_event

                try:
                    push_event(
                        owner_id,
                        {
                            "type": "leave",
                            "title": f"🚪 {user.full_name} left",
                            "body": f"@{user.username or user.id}",
                            "chat_id": chat.id,
                            "user_id": user.id,
                        },
                    )
                except Exception:
                    pass


async def _send_welcome(bot, chat_id, user, settings, db):
    """Send welcome message."""
    try:
        from bot.handlers.greetings import welcome_handler

        # Mocking update and context to reuse existing welcome_handler
        class MockUpdate:
            def __init__(self, user, chat_id):
                self.message = type("obj", (object,), {"new_chat_members": [user]})
                self.effective_chat = type("obj", (object,), {"id": chat_id})
                self.effective_message = self.message

        class MockContext:
            def __init__(self, bot, db):
                self.bot = bot
                self.bot_data = {"db_pool": db}

        mock_update = MockUpdate(user, chat_id)
        mock_context = MockContext(bot, db)
        await welcome_handler(mock_update, mock_context)
    except Exception as e:
        log.warning(f"Welcome handler failed: {e}")
