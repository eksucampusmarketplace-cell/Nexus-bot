"""
bot/handlers/stake_polls.py

Polls with Stakes — bet bonus Stars on poll outcomes.

Commands:
  /betpoll <question> | <opt1> | <opt2> [| min=N] [| max=N]
      — Create a poll with staking
  /bet <amount> <option_number>
      — Place a bet on a stake poll (reply to poll message)
  /closepoll [winner_option_number]
      — Close a stake poll and distribute winnings (reply to poll, admin only)
  /mybets
      — Show your active bets

Log prefix: [STAKES]
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.billing.stars_economy import get_bonus_balance, grant_bonus_stars
from bot.utils.permissions import is_admin

log = logging.getLogger("stakes")


async def cmd_betpoll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a poll with stakes."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command only works in groups.")
        return

    text = " ".join(context.args)
    if "|" not in text:
        await update.message.reply_text(
            "<b>Polls with Stakes</b>\n\n"
            "Create a poll where users bet bonus Stars:\n\n"
            "<code>/betpoll What wins? | Option A | Option B</code>\n"
            "<code>/betpoll Who wins? | Team A | Team B | min=5 | max=50</code>\n\n"
            "Users bet with: <code>/bet &lt;amount&gt; &lt;option#&gt;</code>\n"
            "(reply to the poll message)",
            parse_mode=ParseMode.HTML,
        )
        return

    parts = [p.strip() for p in text.split("|")]
    question = parts[0]
    options = []
    min_bet = 1
    max_bet = 100

    for p in parts[1:]:
        if p.lower().startswith("min="):
            try:
                min_bet = int(p.split("=")[1])
            except ValueError:
                pass
        elif p.lower().startswith("max="):
            try:
                max_bet = int(p.split("=")[1])
            except ValueError:
                pass
        else:
            options.append(p)

    if len(options) < 2:
        await update.message.reply_text("Need at least 2 options.")
        return

    import json

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    # Send the poll message
    options_text = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(options))
    msg = await update.message.reply_text(
        f"<b>Stake Poll</b>\n\n"
        f"<b>{question}</b>\n\n"
        f"{options_text}\n\n"
        f"Bet range: {min_bet}-{max_bet} Stars\n"
        f"Reply to this message with <code>/bet &lt;amount&gt; &lt;option#&gt;</code>",
        parse_mode=ParseMode.HTML,
    )

    async with db.acquire() as conn:
        await conn.execute(
            """INSERT INTO stake_polls
               (chat_id, creator_id, question, options,
                tg_message_id, min_bet, max_bet)
               VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)""",
            chat.id,
            user.id,
            question,
            json.dumps(options),
            msg.message_id,
            min_bet,
            max_bet,
        )

    log.info(f"[STAKES] Poll created | chat={chat.id} user={user.id}")


async def cmd_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Place a bet on a stake poll."""
    chat = update.effective_chat
    user = update.effective_user
    reply = update.message.reply_to_message

    if not reply:
        await update.message.reply_text("Reply to a stake poll message to place a bet.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /bet <amount> <option_number>")
        return

    try:
        amount = int(context.args[0])
        option_idx = int(context.args[1]) - 1  # 1-based to 0-based
    except ValueError:
        await update.message.reply_text("Amount and option must be numbers.")
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    async with db.acquire() as conn:
        # Find the poll
        poll = await conn.fetchrow(
            """SELECT * FROM stake_polls
               WHERE chat_id=$1 AND tg_message_id=$2 AND status='open'""",
            chat.id,
            reply.message_id,
        )

        if not poll:
            await update.message.reply_text(
                "No active stake poll found on that message."
            )
            return

        import json

        options = (
            json.loads(poll["options"])
            if isinstance(poll["options"], str)
            else poll["options"]
        )
        if option_idx < 0 or option_idx >= len(options):
            await update.message.reply_text(f"Invalid option. Choose 1-{len(options)}.")
            return

        if amount < poll["min_bet"] or amount > poll["max_bet"]:
            await update.message.reply_text(
                f"Bet must be between {poll['min_bet']} and {poll['max_bet']} Stars."
            )
            return

        # Check balance
        balance = await get_bonus_balance(conn, user.id)
        if balance < amount:
            await update.message.reply_text(
                f"Not enough bonus Stars. You have {balance}, need {amount}."
            )
            return

        # Check if already bet
        existing = await conn.fetchval(
            "SELECT 1 FROM stake_bets WHERE poll_id=$1 AND user_id=$2",
            poll["id"],
            user.id,
        )
        if existing:
            await update.message.reply_text("You already placed a bet on this poll.")
            return

        # Deduct Stars and place bet
        await conn.execute(
            """INSERT INTO bonus_stars (owner_id, amount, reason)
               VALUES ($1, $2, 'poll_bet')""",
            user.id,
            -amount,
        )

        await conn.execute(
            """INSERT INTO stake_bets (poll_id, user_id, option_idx, amount)
               VALUES ($1, $2, $3, $4)""",
            poll["id"],
            user.id,
            option_idx,
            amount,
        )

        await conn.execute(
            "UPDATE stake_polls SET total_pool = total_pool + $1 WHERE id=$2",
            amount,
            poll["id"],
        )

    await update.message.reply_text(
        f"Bet placed: {amount} Stars on <b>{options[option_idx]}</b>",
        parse_mode=ParseMode.HTML,
    )
    log.info(
        f"[STAKES] Bet | chat={chat.id} user={user.id} "
        f"amount={amount} option={option_idx}"
    )


async def cmd_closepoll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close a stake poll and distribute winnings."""
    chat = update.effective_chat
    user = update.effective_user
    reply = update.message.reply_to_message

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can close stake polls.")
        return

    if not reply:
        await update.message.reply_text("Reply to the stake poll message to close it.")
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    async with db.acquire() as conn:
        poll = await conn.fetchrow(
            """SELECT * FROM stake_polls
               WHERE chat_id=$1 AND tg_message_id=$2 AND status='open'""",
            chat.id,
            reply.message_id,
        )

        if not poll:
            await update.message.reply_text("No active stake poll found.")
            return

        import json

        options = (
            json.loads(poll["options"])
            if isinstance(poll["options"], str)
            else poll["options"]
        )

        # Determine winner
        if context.args:
            try:
                winner_idx = int(context.args[0]) - 1
            except ValueError:
                await update.message.reply_text("Winner must be a number.")
                return
        else:
            await update.message.reply_text(
                f"Usage: /closepoll <winner_option>\n"
                f"Options: {', '.join(f'{i+1}={o}' for i, o in enumerate(options))}"
            )
            return

        if winner_idx < 0 or winner_idx >= len(options):
            await update.message.reply_text(f"Invalid option. Choose 1-{len(options)}.")
            return

        # Get all bets
        bets = await conn.fetch("SELECT * FROM stake_bets WHERE poll_id=$1", poll["id"])

        winning_bets = [b for b in bets if b["option_idx"] == winner_idx]
        total_pool = poll["total_pool"]
        winning_total = sum(b["amount"] for b in winning_bets)

        # Distribute winnings proportionally
        payouts = []
        for bet in winning_bets:
            if winning_total > 0:
                payout = int(total_pool * bet["amount"] / winning_total)
            else:
                payout = 0

            await grant_bonus_stars(conn, bet["user_id"], payout, "poll_win")
            await conn.execute(
                "UPDATE stake_bets SET payout=$1 WHERE id=$2", payout, bet["id"]
            )
            payouts.append((bet["user_id"], payout))

        # Close poll
        await conn.execute(
            """UPDATE stake_polls
               SET status='closed', winning_option=$1, closed_at=NOW()
               WHERE id=$2""",
            winner_idx,
            poll["id"],
        )

    # Build results message
    lines = [
        f"<b>Stake Poll Closed!</b>\n",
        f"Winner: <b>{options[winner_idx]}</b>\n",
        f"Total pool: {total_pool} Stars",
        f"Winners: {len(winning_bets)} / {len(bets)} bettors\n",
    ]

    if payouts:
        lines.append("Payouts:")
        for uid, payout in payouts[:10]:
            lines.append(f"  User {uid}: +{payout} Stars")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    log.info(
        f"[STAKES] Closed | chat={chat.id} pool={total_pool} winners={len(winning_bets)}"
    )


async def cmd_mybets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show your active bets."""
    user = update.effective_user
    chat = update.effective_chat

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT sb.amount, sb.option_idx, sb.payout,
                      sp.question, sp.options, sp.status
               FROM stake_bets sb
               JOIN stake_polls sp ON sp.id = sb.poll_id
               WHERE sb.user_id=$1 AND sp.chat_id=$2
               ORDER BY sb.created_at DESC
               LIMIT 10""",
            user.id,
            chat.id,
        )

    if not rows:
        await update.message.reply_text("You have no bets in this group.")
        return

    import json

    lines = ["<b>Your Bets</b>\n"]
    for r in rows:
        opts = (
            json.loads(r["options"]) if isinstance(r["options"], str) else r["options"]
        )
        chosen = opts[r["option_idx"]] if r["option_idx"] < len(opts) else "?"
        status = r["status"]
        payout_str = f" | Won {r['payout']} Stars" if r["payout"] else ""
        lines.append(
            f"{r['question'][:30]}: {r['amount']} Stars on {chosen} [{status}]{payout_str}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


stake_poll_handlers = [
    CommandHandler("betpoll", cmd_betpoll),
    CommandHandler("bet", cmd_bet),
    CommandHandler("closepoll", cmd_closepoll),
    CommandHandler("mybets", cmd_mybets),
]
