"""
bot/captcha/engine.py

CAPTCHA challenge generation and verification.
"""

import asyncio
import logging
import random
import string
import uuid
from datetime import datetime, timezone, timedelta

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError

from db.ops.captcha import (
    create_challenge, get_challenge_by_id, get_pending_challenge,
    mark_challenge_passed, increment_attempts, log_member_event
)

log = logging.getLogger("captcha")

EMOJI_OPTIONS = ["🌟", "🎯", "🔥", "💎", "🚀", "🎲", "🌈", "⚡", "🎭", "🦋"]


async def send_captcha(
    bot: Bot,
    chat_id: int,
    user,
    settings: dict,
    db,
    join_message_id: int | None = None
):
    """
    Send CAPTCHA challenge to new member.
    Called after restricting the user.
    """
    mode    = settings.get("captcha_mode", "button")
    timeout = settings.get("captcha_timeout_mins", 5)
    cid     = str(uuid.uuid4())[:12]

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout)

    if mode == "button":
        text, markup, answer = _build_button_captcha(cid)
    elif mode == "math":
        text, markup, answer = _build_math_captcha(cid)
    elif mode == "text":
        text, markup, answer = _build_text_captcha(cid)
    else:
        text, markup, answer = _build_button_captcha(cid)

    full_text = (
        f"👋 Welcome, {user.mention_html()}!\n\n"
        f"Please complete the CAPTCHA to join the group.\n\n"
        f"{text}\n\n"
        f"⏱ You have {timeout} minute(s)."
    )

    # Create challenge record first (without message_id) to prevent race conditions
    await create_challenge(
        db, chat_id=chat_id, user_id=user.id,
        challenge_id=cid, mode=mode, answer=str(answer),
        message_id=None, expires_at=expires_at
    )

    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=full_text,
            reply_markup=markup,
            parse_mode="HTML",
            reply_to_message_id=join_message_id
        )
        msg_id = msg.message_id
        # Update with message_id
        await db.execute(
            "UPDATE captcha_challenges SET message_id = $1 WHERE challenge_id = $2",
            msg_id, cid
        )
    except TelegramError as e:
        log.warning(f"[CAPTCHA] Send failed | {e}")
        # Clean up challenge if send failed
        await db.execute("DELETE FROM captcha_challenges WHERE challenge_id = $1", cid)
        return

    log.info(
        f"[CAPTCHA] Sent | chat={chat_id} user={user.id} "
        f"mode={mode} cid={cid}"
    )

    # Schedule timeout check
    asyncio.create_task(
        _timeout_check(bot, chat_id, user.id, cid, timeout * 60, settings, db)
    )


async def verify_button(
    bot: Bot,
    chat_id: int,
    user_id: int,
    challenge_id: str,
    is_correct: bool,
    db,
    settings: dict
) -> bool:
    """Handle inline button press. Returns True if passed."""
    challenge = await get_challenge_by_id(db, challenge_id)
    if not challenge or challenge["passed"]:
        return False
    if challenge["user_id"] != user_id:
        return False

    if is_correct:
        await _pass_captcha(bot, chat_id, user_id, challenge, db)
        return True
    else:
        attempts = await increment_attempts(db, challenge_id)
        if attempts >= 3:
            await _fail_captcha(bot, chat_id, user_id, challenge, db,
                                reason="Too many wrong attempts")
        return False


async def verify_text_answer(
    bot: Bot,
    chat_id: int,
    user_id: int,
    answer_text: str,
    db,
    settings: dict
) -> bool:
    """
    Check text/math CAPTCHA answer from user message.
    Called from message handler for users with pending challenges.
    Returns True if answered correctly.
    """
    challenge = await get_pending_challenge(db, chat_id, user_id)
    if not challenge:
        return False
    if challenge["mode"] not in ("math", "text"):
        return False

    correct = answer_text.strip().lower() == challenge["answer"].lower()

    if correct:
        await _pass_captcha(bot, chat_id, user_id, challenge, db)
        return True
    else:
        attempts = await increment_attempts(db, challenge["challenge_id"])
        if attempts >= 3:
            await _fail_captcha(
                bot, chat_id, user_id, challenge, db,
                reason="Too many wrong attempts"
            )
        else:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Wrong answer. {3 - attempts} attempt(s) left.",
                    reply_to_message_id=challenge["message_id"]
                )
            except TelegramError:
                pass
        return False


async def _pass_captcha(bot, chat_id, user_id, challenge, db):
    """Unrestrict user, delete challenge message, log pass."""
    await mark_challenge_passed(db, challenge["challenge_id"])

    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions={
                "can_send_messages":       True,
                "can_send_media_messages": True,
                "can_send_polls":          True,
                "can_send_other_messages": True,
                "can_add_web_page_previews": True,
            }
        )
    except TelegramError as e:
        log.warning(f"[CAPTCHA] Unrestrict failed | {e}")

    try:
        await bot.delete_message(chat_id, challenge["message_id"])
    except TelegramError:
        pass

    await log_member_event(db, chat_id, user_id, "captcha_pass")

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ Welcome! You've been verified.",
        )
    except TelegramError:
        pass

    log.info(f"[CAPTCHA] Passed | chat={chat_id} user={user_id}")


async def _fail_captcha(bot, chat_id, user_id, challenge, db, reason=""):
    """Kick user, delete challenge message, log fail."""
    try:
        await bot.delete_message(chat_id, challenge["message_id"])
    except TelegramError:
        pass

    try:
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id)  # kick, not ban
    except TelegramError as e:
        log.warning(f"[CAPTCHA] Kick failed | {e}")

    await log_member_event(db, chat_id, user_id, "captcha_fail",
                           {"reason": reason})

    log.info(f"[CAPTCHA] Failed + kicked | chat={chat_id} user={user_id}")


async def _timeout_check(
    bot, chat_id, user_id, challenge_id, delay, settings, db
):
    await asyncio.sleep(delay)
    challenge = await get_challenge_by_id(db, challenge_id)
    if not challenge or challenge["passed"]:
        return

    log.info(f"[CAPTCHA] Timeout | chat={chat_id} user={user_id}")

    if settings.get("captcha_kick_on_timeout", True):
        await _fail_captcha(
            bot, chat_id, user_id, challenge, db,
            reason="CAPTCHA timeout"
        )


# ── Challenge builders ─────────────────────────────────────────────────────

def _build_button_captcha(cid: str):
    """4 buttons: 1 correct (random emoji+number), 3 decoys."""
    options   = random.sample(EMOJI_OPTIONS, 4)
    correct   = random.randint(0, 3)
    correct_label = f"{options[correct]} {random.randint(10,99)}"

    decoy_labels = [
        f"{options[i]} {random.randint(10,99)}"
        for i in range(4) if i != correct
    ]

    all_labels = decoy_labels.copy()
    all_labels.insert(correct, correct_label)

    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=f"captcha:{cid}:{'1' if i == correct else '0'}"
        )
        for i, label in enumerate(all_labels)
    ]

    markup = InlineKeyboardMarkup([buttons[:2], buttons[2:]])
    text   = f"👆 Tap the correct button:\n<b>{correct_label}</b>"
    return text, markup, correct_label


def _build_math_captcha(cid: str):
    """Simple arithmetic: addition or subtraction."""
    op = random.choice(["+", "-", "*"])
    if op == "+":
        a, b   = random.randint(1, 20), random.randint(1, 20)
        answer = a + b
        text   = f"🔢 What is <b>{a} + {b}</b>? Reply with the number."
    elif op == "-":
        a, b   = random.randint(10, 30), random.randint(1, 10)
        answer = a - b
        text   = f"🔢 What is <b>{a} - {b}</b>? Reply with the number."
    else:
        a, b   = random.randint(2, 9), random.randint(2, 9)
        answer = a * b
        text   = f"🔢 What is <b>{a} × {b}</b>? Reply with the number."

    return text, None, str(answer)


def _build_text_captcha(cid: str):
    """6-char alphanumeric code user must type exactly."""
    code   = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    text   = f"🔤 Type exactly: <code>{code}</code>"
    return text, None, code
