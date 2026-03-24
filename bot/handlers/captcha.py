import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ChatMemberHandler, ContextTypes

from db.ops.captcha import (
    create_challenge,
    get_challenge_by_id,
    get_pending_challenge,
    log_member_event,
    mark_challenge_passed,
)

logger = logging.getLogger(__name__)


async def new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for new chat members - used by ChatMemberHandler.
    This is called when a user's chat member status changes (e.g., they join).
    """
    chat_id = update.effective_chat.id
    if not update.chat_member or not update.chat_member.new_chat_member:
        return

    new_member = update.chat_member.new_chat_member

    # Only process users who were added (not left/kicked)
    if new_member.status not in ["member", "restricted"]:
        return

    member = new_member.user

    # Skip bots
    if member.is_bot:
        return

    from db.ops.groups import get_group

    group = await get_group(chat_id)
    if not group:
        return

    settings = group.get("settings", {})
    modules = group.get("modules", {})

    # Helper function to check module status
    def is_module_enabled(module_name):
        """Check if a module is enabled in the modules dict."""
        return modules.get(module_name, False)

    # Anti-bot check
    antibot = settings.get("automod", {}).get("antibot", {})
    # Check if antibot module is disabled via Mini App toggle
    if not is_module_enabled("antibot"):
        antibot = {"enabled": False}
    if antibot.get("enabled") and not member.username:
        try:
            await context.bot.unban_chat_member(chat_id, member.id)
            logger.info(f"[AUTOMOD] Kicked user without username: {member.id}")
        except Exception as e:
            logger.warning(f"[AUTOMOD] Failed to kick user without username: {e}")
        return

    # Captcha check
    captcha = settings.get("automod", {}).get("captcha", {})
    # Check if captcha module is disabled via Mini App toggle
    if not is_module_enabled("captcha"):
        captcha = {"enabled": False}
    if captcha.get("enabled"):
        await send_captcha(update, context, member)
        return

    # Welcome message
    welcome = settings.get("welcome", {})
    # Check if welcome_message module is disabled via Mini App toggle
    if not is_module_enabled("welcome_message"):
        welcome = {"enabled": False}
    if welcome.get("enabled"):
        text = welcome.get("text", "Welcome {first_name}!").format(
            first_name=member.first_name,
            last_name=member.last_name or "",
            username=member.username or "",
        )
        try:
            msg = await context.bot.send_message(chat_id, text)
            delete_after = welcome.get("delete_after", 0)
            if delete_after > 0:
                context.job_queue.run_once(
                    delete_msg_job,
                    delete_after,
                    data={"chat_id": chat_id, "message_id": msg.message_id},
                )
        except Exception as e:
            logger.warning(f"[WELCOME] Failed to send welcome message: {e}")


async def delete_msg_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to delete a message after a delay."""
    try:
        await context.bot.delete_message(
            context.job.data["chat_id"], context.job.data["message_id"]
        )
    except:
        pass


async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE, member):
    chat_id = update.effective_chat.id
    user_id = member.id
    db = context.bot_data.get("db")

    keyboard = [[InlineKeyboardButton("✅ I'm human", callback_data=f"captcha_verify_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"Welcome {member.first_name}! Please click the button below to verify you're human."
    msg = await context.bot.send_message(chat_id, text, reply_markup=reply_markup)

    from datetime import timezone

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=120)
    # Use create_challenge instead of add_captcha_pending
    import uuid

    challenge_id = str(uuid.uuid4())[:12]
    await create_challenge(
        db,
        chat_id=chat_id,
        user_id=user_id,
        challenge_id=challenge_id,
        mode="button",
        answer="verified",
        message_id=msg.message_id,
        expires_at=expires_at,
    )

    # Schedule kick if not verified
    context.job_queue.run_once(
        captcha_timeout,
        120,
        data={"chat_id": chat_id, "user_id": user_id, "challenge_id": challenge_id},
    )


async def captcha_timeout(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    db = context.bot_data.get("db")
    pending = await get_pending_challenge(db, data["chat_id"], data["user_id"])
    if pending and not pending.get("passed", False):
        try:
            await context.bot.unban_chat_member(data["chat_id"], data["user_id"])
            await context.bot.delete_message(data["chat_id"], pending["message_id"])
            await log_member_event(
                db, data["chat_id"], data["user_id"], "captcha_fail", {"reason": "timeout"}
            )
        except:
            pass


async def captcha_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if not data.startswith("captcha_verify_"):
        return

    user_id = int(data.split("_")[-1])
    if query.from_user.id != user_id:
        await query.answer("This button is not for you!", show_alert=True)
        return

    chat_id = update.effective_chat.id
    db = context.bot_data.get("db")
    pending = await get_pending_challenge(db, chat_id, user_id)
    if pending and not pending.get("passed", False):
        await query.answer("Verified! Welcome.")
        try:
            await context.bot.delete_message(chat_id, pending["message_id"])
            await mark_challenge_passed(db, pending["challenge_id"])
            await log_member_event(db, chat_id, user_id, "captcha_pass")
        except:
            pass
    else:
        await query.answer("Session expired or already verified.")
