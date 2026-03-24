"""
bot/handlers/password.py

Group password system.
New members must DM the bot with the correct password to unlock their
ability to send messages in the group.

Flow:
  1. New member joins
  2. Bot restricts them (can't send messages)
  3. Bot sends group message: "DM me the password to join"
  4. Bot DMs user: "This group requires a password. Please enter it."
  5. User DMs password → bot verifies
  6. Correct → unrestrict in group, confirm
  7. Wrong → increment attempts, kick after max_attempts

Commands (admin):
  /setpassword word123   → set password
  /clearpassword         → disable password

Logs prefix: [PASSWORD]
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from telegram import ChatPermissions, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.utils.permissions import is_admin
from db.ops.automod import update_group_setting

log = logging.getLogger("password")


async def send_password_challenge(bot, chat_id: int, user, settings: dict, db):
    """
    Called after new member joins (if password enabled).
    Restrict user + DM them the challenge.
    """
    timeout = settings.get("password_timeout_mins", 5)
    expires = datetime.now(timezone.utc) + timedelta(minutes=timeout)

    try:
        await bot.restrict_chat_member(
            chat_id=chat_id, user_id=user.id, permissions=ChatPermissions(can_send_messages=False)
        )
    except TelegramError:
        pass

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"👋 Welcome, {user.mention_html()}!\n\n"
                "This group requires a password to participate.\n"
                "📩 Please DM me the password to unlock your access."
            ),
            parse_mode="HTML",
        )
    except TelegramError:
        pass

    await db.execute(
        """INSERT INTO password_challenges
           (chat_id, user_id, attempts, passed, expires_at)
           VALUES ($1,$2,0,FALSE,$3)
           ON CONFLICT (chat_id, user_id)
           DO UPDATE SET attempts=0, passed=FALSE, expires_at=$3""",
        chat_id,
        user.id,
        expires,
    )

    try:
        await bot.send_message(
            chat_id=user.id,
            text=(
                "🔐 <b>Group Password Required</b>\n\n"
                "You joined a group that requires a password.\n"
                "Please enter the password below.\n\n"
                f"⏱ You have {timeout} minute(s)."
            ),
            parse_mode="HTML",
        )
    except TelegramError:
        log.warning(f"[PASSWORD] DM failed | user={user.id} " "(user may have DMs disabled)")
        try:
            me = await bot.get_me()
            await bot.send_message(
                chat_id=chat_id,
                text=(f"{user.mention_html()} — please start the bot " f"first: @{me.username}"),
                parse_mode="HTML",
            )
        except TelegramError:
            pass

    asyncio.create_task(_password_timeout(bot, chat_id, user.id, timeout * 60, db))
    log.info(f"[PASSWORD] Challenge sent | chat={chat_id} user={user.id}")


async def handle_password_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles DM messages from users who have pending password challenges.
    Only fires in private chats.
    """
    msg = update.effective_message
    user = update.effective_user
    db = context.bot_data.get("db")

    if not msg or not user:
        return

    rows = await db.fetch(
        """SELECT pc.*, g.group_password,
                  g.password_attempts, g.password_kick_on_fail
           FROM password_challenges pc
           JOIN groups g ON g.chat_id = pc.chat_id
           WHERE pc.user_id=$1 AND pc.passed=FALSE
           AND pc.expires_at > NOW()
           ORDER BY pc.created_at DESC""",
        user.id,
    )

    if not rows:
        return

    challenge = dict(rows[0])
    chat_id = challenge["chat_id"]
    correct = challenge["group_password"]
    max_att = challenge.get("password_attempts", 3)
    attempts = challenge["attempts"] + 1

    await db.execute(
        "UPDATE password_challenges SET attempts=$1 WHERE chat_id=$2 AND user_id=$3",
        attempts,
        chat_id,
        user.id,
    )

    if msg.text and msg.text.strip() == correct:
        await db.execute(
            "UPDATE password_challenges SET passed=TRUE WHERE chat_id=$1 AND user_id=$2",
            chat_id,
            user.id,
        )
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
        except TelegramError:
            pass

        await msg.reply_text(
            "✅ <b>Correct!</b> You now have access to the group.", parse_mode="HTML"
        )
        log.info(f"[PASSWORD] Passed | chat={chat_id} user={user.id}")

    else:
        remaining = max_att - attempts
        if remaining <= 0 and challenge.get("password_kick_on_fail"):
            try:
                await context.bot.ban_chat_member(chat_id, user.id)
                await context.bot.unban_chat_member(chat_id, user.id)
            except TelegramError:
                pass
            await msg.reply_text("❌ Too many wrong attempts. You've been removed.")
            log.info(f"[PASSWORD] Kicked (wrong password) | " f"chat={chat_id} user={user.id}")
        else:
            await msg.reply_text(f"❌ Wrong password. {max(0, remaining)} attempt(s) left.")


async def _password_timeout(bot, chat_id, user_id, delay, db):
    await asyncio.sleep(delay)
    row = await db.fetchrow(
        "SELECT passed FROM password_challenges WHERE chat_id=$1 AND user_id=$2", chat_id, user_id
    )
    if row and not row["passed"]:
        try:
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id)
        except TelegramError:
            pass
        log.info(f"[PASSWORD] Timeout kick | chat={chat_id} user={user_id}")


async def cmd_setpassword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setpassword word123"""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    if not await is_admin(update, context):
        await msg.reply_text("❌ Only admins can set the group password.")
        return

    if not context.args:
        await msg.reply_text("Usage: /setpassword <password>")
        return

    password = context.args[0]
    try:
        await update_group_setting(db, chat.id, "group_password", password)
    except Exception as e:
        log.error(f"[PASSWORD] Failed to set | chat={chat.id} error={e}")
        await msg.reply_text("❌ Failed to set password. Please try again.")
        return
    await msg.reply_text(
        f"🔐 Group password set.\n" f"New members must DM the bot with: <code>{password}</code>",
        parse_mode="HTML",
    )
    log.info(f"[PASSWORD] Set | chat={chat.id}")


async def cmd_clearpassword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/clearpassword — disable group password."""
    msg = update.effective_message
    chat = update.effective_chat
    db = context.bot_data.get("db")

    if not await is_admin(update, context):
        await msg.reply_text("❌ Only admins can clear the group password.")
        return

    try:
        await update_group_setting(db, chat.id, "group_password", None)
    except Exception as e:
        log.error(f"[PASSWORD] Failed to clear | chat={chat.id} error={e}")
        await msg.reply_text("❌ Failed to clear password. Please try again.")
        return
    await msg.reply_text("✅ Group password cleared. Anyone can join freely.")
    log.info(f"[PASSWORD] Cleared | chat={chat.id}")
