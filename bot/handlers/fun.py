"""
bot/handlers/fun.py

Fun and utility commands for users:
  /afk <reason>            — Set AFK status with optional reason
  /back                    — Clear AFK status
  /poll <question>         — Create a simple poll
  /dice                    — Roll a dice
  /coin                    — Flip a coin
  /choose <option1|option2> — Randomly choose between options
  /8ball <question>        — Magic 8-ball response
  /roll <max>              — Roll random number (1-max)
  /joke                    — Get a random joke
  /quote                   — Get an inspirational quote
  /weather <city>          — Get weather info (placeholder)
  /time <timezone>         — Get time in timezone (placeholder)

Logs prefix: [FUN_CMD]
"""

import logging
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Dice
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

from config import settings
from bot.utils.permissions import is_admin

log = logging.getLogger("fun_cmd")

# AFK storage: {chat_id: {user_id: {"reason": str, "since": datetime}}}
afk_users = {}

EIGHT_BALL_RESPONSES = [
    "🎱 It is certain",
    "🎱 It is decidedly so",
    "🎱 Without a doubt",
    "🎱 Yes definitely",
    "🎱 You may rely on it",
    "🎱 As I see it, yes",
    "🎱 Most likely",
    "🎱 Outlook good",
    "🎱 Yes",
    "🎱 Signs point to yes",
    "🎱 Reply hazy, try again",
    "🎱 Ask again later",
    "🎱 Better not tell you now",
    "🎱 Cannot predict now",
    "🎱 Concentrate and ask again",
    "🎱 Don't count on it",
    "🎱 My reply is no",
    "🎱 My sources say no",
    "🎱 Outlook not so good",
    "🎱 Very doubtful",
]

JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
    "Why don't skeletons fight each other? They don't have the guts!",
    "What do you call a fake noodle? An impasta!",
    "Why did the coffee file a police report? It got mugged!",
    "How does a penguin build its house? Igloos it together!",
    "Why don't eggs tell jokes? They'd crack each other up!",
    "What do you call a bear with no teeth? A gummy bear!",
    "Why did the math book look sad? Because it had too many problems!",
    "What do you call a sleeping dinosaur? A dino-snore!",
]

QUOTES = [
    "The only way to do great work is to love what you do. — Steve Jobs",
    "Innovation distinguishes between a leader and a follower. — Steve Jobs",
    "Life is what happens when you're busy making other plans. — John Lennon",
    "The future belongs to those who believe in the beauty of their dreams. — Eleanor Roosevelt",
    "It is during our darkest moments that we must focus to see the light. — Aristotle",
    "Do not go where the path may lead, go instead where there is no path and leave a trail. — Ralph Waldo Emerson",
    "The only impossible journey is the one you never begin. — Tony Robbins",
    "In the end, it's not the years in your life that count. It's the life in your years. — Abraham Lincoln",
    "Success is not final, failure is not fatal: it is the courage to continue that counts. — Winston Churchill",
    "Believe you can and you're halfway there. — Theodore Roosevelt",
]


async def cmd_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set AFK status with optional reason."""
    user = update.effective_user
    chat = update.effective_chat

    reason = " ".join(context.args) if context.args else "No reason given"

    if chat.id not in afk_users:
        afk_users[chat.id] = {}

    afk_users[chat.id][user.id] = {"reason": reason, "since": datetime.now(timezone.utc)}

    await update.message.reply_text(
        f"😴 <b>{user.first_name}</b> is now AFK\n" f"Reason: {reason}", parse_mode=ParseMode.HTML
    )
    log.info(f"[FUN_CMD] AFK set | user={user.id} chat={chat.id}")


async def cmd_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear AFK status."""
    user = update.effective_user
    chat = update.effective_chat

    if chat.id in afk_users and user.id in afk_users[chat.id]:
        afk_data = afk_users[chat.id].pop(user.id)
        since = afk_data["since"]
        duration = datetime.now(timezone.utc) - since
        minutes = int(duration.total_seconds() / 60)

        await update.message.reply_text(
            f"👋 <b>Welcome back!</b>\n" f"You were AFK for {minutes} minutes.",
            parse_mode=ParseMode.HTML,
        )
        log.info(f"[FUN_CMD] AFK cleared | user={user.id} chat={chat.id}")
    else:
        await update.message.reply_text("You weren't marked as AFK.")


async def check_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if mentioned user is AFK."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # Check for mentions
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mentioned_username = message.text[entity.offset : entity.offset + entity.length]
                # Try to find user by mention - simplified
                pass

    # Check reply to AFK user
    if message.reply_to_message:
        replied_user = message.reply_to_message.from_user
        if chat.id in afk_users and replied_user.id in afk_users[chat.id]:
            afk_data = afk_users[chat.id][replied_user.id]
            since = afk_data["since"]
            duration = datetime.now(timezone.utc) - since
            minutes = int(duration.total_seconds() / 60)

            await message.reply_text(
                f"💤 <b>{replied_user.first_name}</b> is AFK\n"
                f"Reason: {afk_data['reason']}\n"
                f"Duration: {minutes} minutes",
                parse_mode=ParseMode.HTML,
            )


async def cmd_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a simple yes/no poll."""
    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /poll <question>\n" "Example: /poll Should we have a game night?"
        )
        return

    question = " ".join(context.args)

    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=question,
        options=["👍 Yes", "👎 No", "🤷 Maybe"],
        is_anonymous=False,
    )
    log.info(f"[FUN_CMD] Poll created | chat={update.effective_chat.id}")


async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roll a dice."""
    await context.bot.send_dice(chat_id=update.effective_chat.id, emoji="🎲")


async def cmd_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Flip a coin."""
    result = random.choice(["🪙 Heads", "🪙 Tails"])
    await update.message.reply_text(result)


async def cmd_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Randomly choose between options."""
    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /choose option1|option2|option3\n" "Example: /choose pizza|burger|sushi"
        )
        return

    options_text = " ".join(context.args)
    options = [opt.strip() for opt in options_text.split("|")]

    if len(options) < 2:
        await update.message.reply_text("Please provide at least 2 options separated by |")
        return

    chosen = random.choice(options)
    await update.message.reply_text(f"🎯 I choose:\n<b>{chosen}</b>", parse_mode=ParseMode.HTML)


async def cmd_8ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Magic 8-ball response."""
    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /8ball <question>\n" "Example: /8ball Will I win the lottery?"
        )
        return

    response = random.choice(EIGHT_BALL_RESPONSES)
    await update.message.reply_text(response)


async def cmd_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roll a random number."""
    max_val = 100
    if context.args:
        try:
            max_val = int(context.args[0])
            if max_val < 1:
                max_val = 100
            if max_val > 1000000:
                max_val = 1000000
        except ValueError:
            pass

    result = random.randint(1, max_val)
    await update.message.reply_text(
        f"🎲 Rolled: <b>{result}</b> (1-{max_val})", parse_mode=ParseMode.HTML
    )


async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get a random joke."""
    joke = random.choice(JOKES)
    await update.message.reply_text(f"😄 {joke}")


async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get an inspirational quote."""
    quote = random.choice(QUOTES)
    await update.message.reply_text(f"💭 {quote}")


async def cmd_roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Playful roast command (reply to someone)."""
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to roast them! 🔥")
        return

    roasts = [
        "is as useful as a screen door on a submarine 🚪",
        "has the reflexes of a sloth on sleeping pills 🦥",
        "is living proof that evolution can go in reverse 🧬",
        "brings everyone a lot of joy... when they leave the room ✌️",
        "has a face for radio and a voice for silent movies 📻",
        "is the reason why we have warning labels on everything ⚠️",
        "is like a cloud - when they disappear, it's a beautiful day ☀️",
        "would lose a battle of wits with a houseplant 🌱",
    ]

    target = update.message.reply_to_message.from_user
    roast = random.choice(roasts)

    await update.message.reply_text(
        f"🔥 <b>{target.first_name}</b> {roast}", parse_mode=ParseMode.HTML
    )


async def cmd_compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Give a compliment to someone."""
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to compliment them! 💝")
        return

    compliments = [
        "is an absolute legend! 🌟",
        "makes everything better just by being here! ✨",
        "has the most infectious smile! 😊",
        "is smarter than Google! 🧠",
        "is the friend everyone wishes they had! 🤗",
        "lights up every room they enter! 💡",
        "is proof that nice people still exist! 💎",
        "deserves all the good things coming their way! 🎁",
    ]

    target = update.message.reply_to_message.from_user
    compliment = random.choice(compliments)

    await update.message.reply_text(
        f"💝 <b>{target.first_name}</b> {compliment}", parse_mode=ParseMode.HTML
    )


async def cmd_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple calculator."""
    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /calc <expression>\n"
            "Example: /calc 5 + 3\n"
            "Supported: +, -, *, /, ** (power)"
        )
        return

    expression = " ".join(context.args)

    # Security: only allow safe characters
    allowed_chars = set("0123456789+-*/.() **")
    if not all(c in allowed_chars for c in expression.replace(" ", "")):
        await update.message.reply_text("❌ Invalid characters in expression")
        return

    try:
        # Safe evaluation
        result = eval(expression, {"__builtins__": {}}, {})
        await update.message.reply_text(
            f"🧮 <code>{expression}</code> = <b>{result}</b>", parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


# ── Handler objects ───────────────────────────────────────────────────────
fun_handlers = [
    CommandHandler("afk", cmd_afk),
    CommandHandler("back", cmd_back),
    CommandHandler("poll", cmd_poll),
    CommandHandler("dice", cmd_dice),
    CommandHandler("coin", cmd_coin),
    CommandHandler("choose", cmd_choose),
    CommandHandler("8ball", cmd_8ball),
    CommandHandler("roll", cmd_roll),
    CommandHandler("joke", cmd_joke),
    CommandHandler("quote", cmd_quote),
    CommandHandler("roast", cmd_roast),
    CommandHandler("compliment", cmd_compliment),
    CommandHandler("calc", cmd_calc),
    # Check AFK on regular messages
    MessageHandler(filters.TEXT & ~filters.COMMAND, check_afk),
]
