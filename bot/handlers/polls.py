"""
bot/handlers/polls.py

Native Telegram poll commands for creating polls and surveys.
Uses Telegram's native Bot API poll support.
"""

import logging
from telegram import Update, Poll
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.utils.rate_limiter import command_limiter, format_wait_time

logger = logging.getLogger(__name__)


async def poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Create a native Telegram poll.

    Usage: /poll Question | Option1 | Option2 | Option3
    Flags: --anon (anonymous), --quiz (quiz mode), --multi (multi-answer)

    Examples:
      /poll What's for lunch? | Pizza | Sushi | Salad
      /poll --quiz What is 2+2? | 3 | 4 | 5
    """
    # Rate limiting
    user_id = str(update.effective_user.id)
    if not command_limiter.allow(user_id):
        wait = command_limiter.get_reset_time(user_id)
        await update.message.reply_text(f"⚠️ Rate limited. Try again in {format_wait_time(wait)}.")
        return

    args = " ".join(context.args)
    if "|" not in args:
        await update.message.reply_text(
            "Usage: `/poll Question | Option1 | Option2`\n"
            "Flags: `--anon` (anonymous), `--quiz` (quiz mode), `--multi` (multi-answer)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Parse flags
    is_anonymous = "--anon" in args
    is_quiz = "--quiz" in args
    allows_multiple = "--multi" in args

    # Remove flags from args for parsing
    clean_args = args.replace("--anon", "").replace("--quiz", "").replace("--multi", "").strip()

    parts = [p.strip() for p in clean_args.split("|")]
    if len(parts) < 2:
        await update.message.reply_text("Please provide at least a question and one option.")
        return

    question = parts[0][:300]  # Max 300 chars
    options = parts[1:][:10]  # Max 10 options

    # For quiz mode, first option is correct by default
    correct_option_id = 0 if is_quiz else None

    try:
        poll = await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=question,
            options=options,
            is_anonymous=is_anonymous,
            type=Poll.QUIZ if is_quiz else Poll.REGULAR,
            allows_multiple_answers=allows_multiple and not is_quiz,
            correct_option_id=correct_option_id,
        )

        logger.info(
            f"[POLL] Created | chat_id={update.effective_chat.id} | "
            f"user_id={update.effective_user.id} | type={'quiz' if is_quiz else 'poll'}"
        )

    except Exception as e:
        logger.error(f"[POLL] Failed to create poll: {e}")
        await update.message.reply_text(f"❌ Failed to create poll: {e}")


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Quick shortcut for creating quiz polls.

    Usage: /quiz Question | Correct Answer | Wrong1 | Wrong2

    The first option is always the correct answer in quiz mode.
    """
    # Add --quiz flag and delegate to poll_command
    context.args = ["--quiz"] + list(context.args)
    await poll_command(update, context)


async def stop_poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Stop a poll and show results.
    Must reply to the poll message.
    """
    message = update.message.reply_to_message

    if not message or not message.poll:
        await update.message.reply_text("Reply to a poll message to stop it.")
        return

    try:
        await context.bot.stop_poll(chat_id=update.effective_chat.id, message_id=message.message_id)
        await update.message.reply_text("📊 Poll stopped.")
        logger.info(f"[POLL] Stopped | chat_id={update.effective_chat.id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to stop poll: {e}")


async def poll_results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Get detailed poll results.
    Must reply to the poll message.
    """
    message = update.message.reply_to_message

    if not message or not message.poll:
        await update.message.reply_text("Reply to a poll message to see results.")
        return

    poll = message.poll
    total_votes = poll.total_voter_count

    text = f"📊 *{poll.question}*\n\n"

    for option in poll.options:
        votes = option.voter_count
        pct = (votes / total_votes * 100) if total_votes > 0 else 0
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        text += f"{option.text}: {votes} votes ({pct:.1f}%)\n`{bar}`\n\n"

    text += f"Total voters: {total_votes}"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
