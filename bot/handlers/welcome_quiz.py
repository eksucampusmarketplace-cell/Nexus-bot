"""
bot/handlers/welcome_quiz.py

Welcome Quiz — configurable knowledge quizzes for new members.
Extends beyond CAPTCHA with admin-defined questions.

Commands:
  /quizadd <question> | <opt1> | <opt2> | ... | correct=<N>  — Add a quiz question
  /quizlist            — List quiz questions for this group
  /quizdel <id>        — Delete a quiz question
  /quizmode on|off     — Enable/disable welcome quiz for this group

Log prefix: [QUIZ]
"""

import logging
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.utils.permissions import is_admin

log = logging.getLogger("quiz")


async def cmd_quizadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a welcome quiz question."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command only works in groups.")
        return

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can add quiz questions.")
        return

    text = " ".join(context.args)
    if "|" not in text:
        await update.message.reply_text(
            "<b>Add Quiz Question</b>\n\n"
            "Usage:\n"
            "<code>/quizadd What is our rule #1? | Be kind | Spam allowed"
            " | No rules | correct=0</code>\n\n"
            "Options are separated by <code>|</code>.\n"
            "<code>correct=N</code> sets the correct answer index (0-based).\n"
            "Default correct answer is option 0 (first option).",
            parse_mode=ParseMode.HTML,
        )
        return

    parts = [p.strip() for p in text.split("|")]
    question = parts[0]
    correct_idx = 0

    # Extract correct= from last part if present
    options = []
    for p in parts[1:]:
        if p.lower().startswith("correct="):
            try:
                correct_idx = int(p.split("=")[1])
            except ValueError:
                pass
        else:
            options.append(p)

    if len(options) < 2:
        await update.message.reply_text("Please provide at least 2 options.")
        return

    if correct_idx >= len(options):
        correct_idx = 0

    import json

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO welcome_quiz_questions
               (chat_id, question, options, correct_idx, created_by)
               VALUES ($1, $2, $3::jsonb, $4, $5)
               RETURNING id""",
            chat.id,
            question,
            json.dumps(options),
            correct_idx,
            user.id,
        )

    await update.message.reply_text(
        f"Quiz question #{row['id']} added.\n"
        f"Q: {question}\n"
        f"Correct: {options[correct_idx]}",
    )
    log.info(f"[QUIZ] Added | chat={chat.id} id={row['id']} by={user.id}")


async def cmd_quizlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List quiz questions for this group."""
    chat = update.effective_chat

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can view quiz questions.")
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, question, options, correct_idx
               FROM welcome_quiz_questions
               WHERE chat_id=$1 AND is_active=TRUE
               ORDER BY id""",
            chat.id,
        )

    if not rows:
        await update.message.reply_text(
            "No quiz questions configured. Use /quizadd to add one."
        )
        return

    import json

    lines = ["<b>Welcome Quiz Questions</b>\n"]
    for r in rows:
        opts = (
            json.loads(r["options"]) if isinstance(r["options"], str) else r["options"]
        )
        correct = opts[r["correct_idx"]] if r["correct_idx"] < len(opts) else "?"
        lines.append(f"#{r['id']}: {r['question']}\n  Correct: {correct}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_quizdel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a quiz question."""
    chat = update.effective_chat

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can delete quiz questions.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /quizdel <question_id>")
        return

    try:
        q_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid question ID.")
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    async with db.acquire() as conn:
        result = await conn.execute(
            "UPDATE welcome_quiz_questions SET is_active=FALSE WHERE id=$1 AND chat_id=$2",
            q_id,
            chat.id,
        )

    if "UPDATE 1" in result:
        await update.message.reply_text(f"Question #{q_id} deleted.")
        log.info(f"[QUIZ] Deleted | chat={chat.id} id={q_id}")
    else:
        await update.message.reply_text(f"Question #{q_id} not found.")


async def cmd_quizmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable/disable welcome quiz for this group."""
    chat = update.effective_chat

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can toggle quiz mode.")
        return

    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.message.reply_text("Usage: /quizmode on|off")
        return

    enabled = context.args[0].lower() == "on"
    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    async with db.acquire() as conn:
        await conn.execute(
            """UPDATE groups SET captcha_mode=$1 WHERE chat_id=$2""",
            "quiz" if enabled else "button",
            chat.id,
        )

    status = "enabled" if enabled else "disabled"
    await update.message.reply_text(f"Welcome quiz {status}.")
    log.info(f"[QUIZ] Mode | chat={chat.id} enabled={enabled}")


async def send_quiz_challenge(bot, db, chat_id: int, user_id: int, user_name: str):
    """
    Send a random quiz question to a new member.
    Called from the captcha/new_member flow when captcha_mode='quiz'.
    Returns True if a question was sent, False if no questions configured.
    """
    import json

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, question, options, correct_idx
               FROM welcome_quiz_questions
               WHERE chat_id=$1 AND is_active=TRUE""",
            chat_id,
        )

    if not rows:
        return False

    q = random.choice(rows)
    opts = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]

    buttons = []
    for i, opt in enumerate(opts):
        buttons.append(
            [
                InlineKeyboardButton(
                    opt, callback_data=f"quiz:{chat_id}:{user_id}:{q['id']}:{i}"
                )
            ]
        )

    from datetime import datetime, timedelta, timezone

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    msg = await bot.send_message(
        chat_id=chat_id,
        text=(
            f"Welcome {user_name}!\n\n"
            f"Please answer this question to verify you're not a bot:\n\n"
            f"<b>{q['question']}</b>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    async with db.acquire() as conn:
        await conn.execute(
            """INSERT INTO welcome_quiz_pending
               (chat_id, user_id, question_id, message_id, expires_at)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (chat_id, user_id) DO UPDATE
               SET question_id=EXCLUDED.question_id,
                   message_id=EXCLUDED.message_id,
                   expires_at=EXCLUDED.expires_at""",
            chat_id,
            user_id,
            q["id"],
            msg.message_id,
            expires_at,
        )

    log.info(f"[QUIZ] Challenge sent | chat={chat_id} user={user_id} q={q['id']}")
    return True


async def handle_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz answer button clicks."""
    query = update.callback_query
    data = query.data

    # quiz:<chat_id>:<user_id>:<question_id>:<selected_idx>
    parts = data.split(":")
    if len(parts) != 5:
        await query.answer("Invalid quiz data.")
        return

    _, chat_id_str, user_id_str, q_id_str, selected_str = parts
    chat_id = int(chat_id_str)
    user_id = int(user_id_str)
    q_id = int(q_id_str)
    selected_idx = int(selected_str)

    # Only the challenged user can answer
    if query.from_user.id != user_id:
        await query.answer("This quiz is not for you!", show_alert=True)
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    import json

    async with db.acquire() as conn:
        q_row = await conn.fetchrow(
            "SELECT correct_idx FROM welcome_quiz_questions WHERE id=$1", q_id
        )
        if not q_row:
            await query.answer("Question not found.")
            return

        correct = q_row["correct_idx"]

        # Clean up pending record
        await conn.execute(
            "DELETE FROM welcome_quiz_pending WHERE chat_id=$1 AND user_id=$2",
            chat_id,
            user_id,
        )

    if selected_idx == correct:
        await query.answer("Correct! Welcome to the group!")
        try:
            await query.edit_message_text(
                f"{query.from_user.full_name} passed the welcome quiz!"
            )
        except Exception:
            pass
        log.info(f"[QUIZ] Passed | chat={chat_id} user={user_id}")
    else:
        await query.answer("Wrong answer!", show_alert=True)
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)
            await query.edit_message_text(
                f"User {query.from_user.full_name} failed the welcome quiz and was removed."
            )
        except Exception as e:
            log.warning(f"[QUIZ] Failed to kick user: {e}")
        log.info(f"[QUIZ] Failed | chat={chat_id} user={user_id}")


quiz_handlers = [
    CommandHandler("quizadd", cmd_quizadd),
    CommandHandler("quizlist", cmd_quizlist),
    CommandHandler("quizdel", cmd_quizdel),
    CommandHandler("quizmode", cmd_quizmode),
    CallbackQueryHandler(handle_quiz_callback, pattern=r"^quiz:"),
]
