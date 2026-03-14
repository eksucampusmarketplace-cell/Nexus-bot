"""
bot/handlers/engagement.py

Engagement system command handlers:
- /rank [@user|reply] — Show XP rank card
- /top or /leaderboard — Group XP leaderboard
- /levels — Show level progression
- /rep [@user|reply] [reason] — Give +1 rep
- /profile [@user|reply] — Full member profile
- /givexp @user <amount> [reason] — Admin gives XP
- /removexp @user <amount> [reason] — Admin removes XP
- /setlevel @user <level> — Admin sets level directly
- /checkin — Daily check-in for XP
- /badges [@user] — Show badges
- /repboard — Reputation leaderboard
- /xpsettings — Admin: configure XP settings
- /setlevelreward <level> <title|role> <value> — Admin: set reward
- /doublexp <hours> — Admin: enable double XP event
- /resetxp @user — Admin: reset a member's XP
- /network — Show network status
- /joinnetwork <code> — Join a network
- /createnetwork <name> — Create a network
- /leavenetwork <network_id> — Leave network
- /networktop — Unified network leaderboard
- /networkcast <message> — Broadcast to network (owner only)

Log prefix: [ENGAGE]
"""

import logging
from datetime import date, datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from bot.engagement.xp import XPEngine, calculate_level, xp_for_level, xp_to_next_level
from bot.engagement.reputation import give_rep, get_reputation, get_rep_leaderboard, get_daily_remaining
from bot.engagement.badges import get_member_badges, get_all_badges
from bot.engagement.network import (
    create_network, join_network, leave_network,
    get_member_networks, get_network_leaderboard, is_network_owner,
    broadcast_to_network
)

log = logging.getLogger("engage")


async def get_xp_engine(context: ContextTypes.DEFAULT_TYPE) -> XPEngine:
    """Get or create XP engine from bot_data."""
    if "xp_engine" not in context.bot_data:
        context.bot_data["xp_engine"] = XPEngine()
    return context.bot_data["xp_engine"]


def _get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[int, str]:
    """Extract target user from mention, reply, or args."""
    message = update.effective_message

    # Check reply first
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        return user.id, user.full_name

    # Check mentions in args
    if context.args:
        arg = context.args[0]
        if arg.startswith("@"):
            # Try to resolve username - this is simplified
            # In practice, you'd need to track usernames
            return None, arg[1:]
        try:
            return int(arg), f"User {arg}"
        except ValueError:
            pass

    return None, None


async def cmd_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show XP rank card for a member."""
    chat_id = update.effective_chat.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    target_id, target_name = _get_target_user(update, context)
    if not target_id:
        target_id = update.effective_user.id
        target_name = update.effective_user.full_name

    xp_engine = await get_xp_engine(context)
    rank_info = await xp_engine.get_member_rank(pool, chat_id, target_id, bot_id)

    if not rank_info or rank_info.get("rank") is None:
        await update.message.reply_text(
            f"⭐ {target_name} has no XP yet.\nSend messages to earn XP!"
        )
        return

    progress_bar = "█" * (rank_info["progress_pct"] // 10) + "░" * (10 - rank_info["progress_pct"] // 10)

    text = (
        f"⭐ <b>{target_name}</b> — Level {rank_info['level']}\n\n"
        f"XP: {rank_info['xp']:,} / {rank_info['xp'] + rank_info['xp_to_next']:,}\n"
        f"Progress: {progress_bar} {rank_info['progress_pct']}%\n\n"
        f"Rank: #{rank_info['rank']} of {rank_info['total_members']}\n"
        f"⚡ Powered by Nexus Bot"
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group XP leaderboard."""
    chat_id = update.effective_chat.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    xp_engine = await get_xp_engine(context)
    leaderboard = await xp_engine.get_leaderboard(pool, chat_id, bot_id, limit=10)

    if not leaderboard:
        await update.message.reply_text(
            "🏆 <b>Leaderboard</b>\n\nNo XP earned yet!\nBe the first to start chatting.",
            parse_mode=ParseMode.HTML
        )
        return

    lines = ["🏆 <b>Top Members</b>", ""]
    medals = ["👑", "⭐", "🌟"]

    for i, entry in enumerate(leaderboard, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        lines.append(
            f"{medal} User {entry['user_id']} — Lv.{entry['level']} {entry['xp']:,} XP"
        )

    lines.append("")
    lines.append("⚡ Powered by Nexus Bot")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_levels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show level progression guide."""
    chat_id = update.effective_chat.id

    lines = [
        "📈 <b>Level Guide</b>",
        "",
        "Lv.1 → 0 XP — Member",
        "Lv.2 → 100 XP — Regular",
        "Lv.3 → 250 XP — Active Member",
        "Lv.5 → 900 XP — ⭐ Trusted",
        "Lv.10 → 3,200 XP — 🌟 Veteran",
        "Lv.20 → 12,000 XP — 💫 Legend",
        "Lv.50 → 60,000 XP — 👑 Elite",
        "",
        "Earn XP by sending messages, playing games, and daily check-ins!",
        "⚡ Powered by Nexus Bot"
    ]

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Give reputation to a member."""
    chat_id = update.effective_chat.id
    bot_id = context.bot.id
    from_user = update.effective_user
    pool = context.bot_data.get("db")

    target_id, target_name = _get_target_user(update, context)
    if not target_id:
        await update.message.reply_text(
            "👍 <b>Give Reputation</b>\n\n"
            "Usage: /rep @username [reason]\n"
            "Or reply to a message with /rep [reason]",
            parse_mode=ParseMode.HTML
        )
        return

    # Build reason from remaining args
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else None

    success, message = await give_rep(
        pool, chat_id, from_user.id, target_id, bot_id,
        amount=1, reason=reason, is_admin=False
    )

    if success:
        remaining = await get_daily_remaining(pool, chat_id, from_user.id, bot_id)
        text = f"👍 {message}\n\nYou have {remaining} more rep to give today."
    else:
        text = f"❌ {message}"

    await update.message.reply_text(text)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show full member profile."""
    chat_id = update.effective_chat.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    target_id, target_name = _get_target_user(update, context)
    if not target_id:
        target_id = update.effective_user.id
        target_name = update.effective_user.full_name

    # Get XP info
    xp_engine = await get_xp_engine(context)
    rank_info = await xp_engine.get_member_rank(pool, chat_id, target_id, bot_id)

    # Get rep info
    rep_info = await get_reputation(pool, chat_id, target_id, bot_id)

    # Get badges
    badges = await get_member_badges(pool, chat_id, target_id, bot_id)

    lines = [
        f"👤 <b>{target_name}</b>",
        "",
        f"Level: {rank_info.get('level', 1)} | XP: {rank_info.get('xp', 0):,}",
        f"Rep: {rep_info.get('rep_score', 0)} 👍 | Rank: #{rank_info.get('rank', '?')}",
    ]

    if badges:
        badge_str = " ".join([f"{b['emoji']}" for b in badges[:5]])
        lines.append(f"\nBadges: {badge_str}")

    lines.append("\n⚡ Powered by Nexus Bot")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Daily check-in for XP."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")
    redis = context.bot_data.get("redis")

    # Check if already checked in today
    today = date.today()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT last_daily_checkin, streak_days FROM member_xp
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
            """,
            chat_id, user_id, bot_id
        )

        if row and row["last_daily_checkin"] == today:
            await update.message.reply_text(
                "✅ You already checked in today!\nCome back tomorrow for more XP."
            )
            return

        # Calculate streak
        streak = row["streak_days"] if row else 0
        if row and row["last_daily_checkin"]:
            last_checkin = row["last_daily_checkin"]
            if (today - last_checkin).days == 1:
                streak += 1
            elif (today - last_checkin).days > 1:
                streak = 1
        else:
            streak = 1

        # Award XP
        xp_engine = await get_xp_engine(context)
        base_xp = 10
        streak_bonus = min(streak // 3, 5)  # +5 XP max for streaks
        total_xp = base_xp + streak_bonus

        result = await xp_engine.award_xp(
            pool, redis, context.bot, chat_id, user_id, bot_id,
            total_xp, "daily"
        )

        # Update checkin
        await conn.execute(
            """
            UPDATE member_xp
            SET last_daily_checkin=$1, streak_days=$2
            WHERE chat_id=$3 AND user_id=$4 AND bot_id=$5
            """,
            today, streak, chat_id, user_id, bot_id
        )

    streak_emoji = "🔥" if streak >= 7 else "✨"
    text = (
        f"✅ <b>Daily Check-in!</b>\n\n"
        f"+{total_xp} XP earned\n"
        f"Streak: {streak_emoji} {streak} days\n"
    )
    if streak_bonus > 0:
        text += f"Streak bonus: +{streak_bonus} XP\n"

    text += f"\nTotal XP: {result.get('new_xp', 0):,}\n⚡ Powered by Nexus Bot"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show badges for a member."""
    chat_id = update.effective_chat.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    target_id, target_name = _get_target_user(update, context)
    if not target_id:
        target_id = update.effective_user.id
        target_name = update.effective_user.full_name

    badges = await get_member_badges(pool, chat_id, target_id, bot_id)
    all_badges = await get_all_badges(pool, bot_id)

    if not badges:
        await update.message.reply_text(
            f"🏅 <b>{target_name}'s Badges</b>\n\n"
            "No badges earned yet!\n"
            "Keep chatting and participating to earn badges.",
            parse_mode=ParseMode.HTML
        )
        return

    earned_ids = {b["id"] for b in badges}
    locked = [b for b in all_badges if b["id"] not in earned_ids]

    lines = [f"🏅 <b>{target_name}'s Badges</b>", ""]
    lines.append("Earned:")
    for b in badges:
        lines.append(f"{b['emoji']} {b['name']}")

    if locked[:3]:
        lines.append("\nNext to unlock:")
        for b in locked[:3]:
            lines.append(f"🔒 {b['emoji']} {b['name']} — {b['description']}")

    lines.append("\n⚡ Powered by Nexus Bot")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_repboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show reputation leaderboard."""
    chat_id = update.effective_chat.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    leaderboard = await get_rep_leaderboard(pool, chat_id, bot_id, limit=10)

    if not leaderboard:
        await update.message.reply_text(
            "👍 <b>Reputation Board</b>\n\nNo reputation given yet!\n"
            "Use /rep @username to give rep to helpful members.",
            parse_mode=ParseMode.HTML
        )
        return

    lines = ["👍 <b>Reputation Board</b>", ""]

    for i, entry in enumerate(leaderboard, 1):
        medal = "🏆" if i == 1 else f"{i}."
        lines.append(
            f"{medal} User {entry['user_id']} — {entry['rep_score']} rep"
        )

    lines.append("\n⚡ Powered by Nexus Bot")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ── Admin Commands ────────────────────────────────────────────────────────────

async def cmd_givexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin gives XP to a member."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")
    redis = context.bot_data.get("redis")

    # Check admin
    member = await update.effective_chat.get_member(admin_id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("❌ Admins only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /givexp @username <amount> [reason]"
        )
        return

    target_id, _ = _get_target_user(update, context)
    if not target_id:
        await update.message.reply_text("Please mention a user or reply to their message.")
        return

    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Amount must be a number.")
        return

    reason = " ".join(context.args[2:]) if len(context.args) > 2 else "Admin grant"

    xp_engine = await get_xp_engine(context)
    result = await xp_engine.award_xp(
        pool, redis, context.bot, chat_id, target_id, bot_id,
        amount, reason, given_by=admin_id
    )

    if result["ok"]:
        await update.message.reply_text(
            f"✅ +{amount} XP given!\n"
            f"New total: {result['new_xp']:,} XP (Level {result['new_level']})"
        )
    else:
        await update.message.reply_text(f"❌ Error: {result.get('error')}")


async def cmd_removexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin removes XP from a member."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")
    redis = context.bot_data.get("redis")

    member = await update.effective_chat.get_member(admin_id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("❌ Admins only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removexp @username <amount> [reason]")
        return

    target_id, _ = _get_target_user(update, context)
    if not target_id:
        await update.message.reply_text("Please mention a user or reply to their message.")
        return

    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Amount must be a number.")
        return

    reason = " ".join(context.args[2:]) if len(context.args) > 2 else "Admin penalty"

    xp_engine = await get_xp_engine(context)
    result = await xp_engine.deduct_xp(
        pool, redis, chat_id, target_id, bot_id,
        amount, reason, admin_id
    )

    if result["ok"]:
        await update.message.reply_text(
            f"✅ -{amount} XP removed.\n"
            f"New total: {result['new_xp']:,} XP (Level {result['new_level']})"
        )
    else:
        await update.message.reply_text(f"❌ Error: {result.get('error')}")


async def cmd_doublexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin enables double XP event."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    member = await update.effective_chat.get_member(admin_id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("❌ Admins only.")
        return

    try:
        hours = int(context.args[0]) if context.args else 2
    except ValueError:
        hours = 2

    xp_engine = await get_xp_engine(context)
    success = await xp_engine.start_double_xp(pool, chat_id, bot_id, hours)

    if success:
        await update.message.reply_text(
            f"⚡ <b>Double XP Event Started!</b>\n\n"
            f"All XP earnings are now doubled for {hours} hours!\n"
            f"Chat and earn XP faster! 🚀",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("❌ Failed to start double XP event.")


# ── Network Commands ──────────────────────────────────────────────────────────

async def cmd_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show network status for the group."""
    chat_id = update.effective_chat.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    networks = await get_member_networks(pool, chat_id)

    if not networks:
        await update.message.reply_text(
            "🌐 <b>Network Status</b>\n\n"
            "This group is not in any networks.\n\n"
            "Join a network with /joinnetwork <code>\n"
            "Create a network with /createnetwork <name>",
            parse_mode=ParseMode.HTML
        )
        return

    lines = ["🌐 <b>Your Networks</b>", ""]

    for net in networks:
        lines.append(f"• <b>{net['name']}</b>")
        lines.append(f"  {net['member_count']} groups • Role: {net['role']}")

    lines.append("\nUse /networktop to see the unified leaderboard!")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_joinnetwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join a network using invite code."""
    chat_id = update.effective_chat.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    if not context.args:
        await update.message.reply_text("Usage: /joinnetwork <invite_code>")
        return

    invite_code = context.args[0]
    success, message = await join_network(pool, invite_code, chat_id, bot_id)

    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")


async def cmd_createnetwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new network."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot_id = context.bot.id
    pool = context.bot_data.get("db")

    member = await update.effective_chat.get_member(user_id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("❌ Only group admins can create networks.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /createnetwork <name>")
        return

    name = " ".join(context.args)
    result = await create_network(pool, name, "", user_id, bot_id)

    if result["ok"]:
        await update.message.reply_text(
            f"✅ <b>Network Created!</b>\n\n"
            f"Name: {name}\n"
            f"Invite code: <code>{result['invite_code']}</code>\n\n"
            f"Share this code with other groups to join your network!",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(f"❌ {result.get('error', 'Failed to create network')}")


async def cmd_networktop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show unified network leaderboard."""
    chat_id = update.effective_chat.id
    pool = context.bot_data.get("db")

    networks = await get_member_networks(pool, chat_id)
    if not networks:
        await update.message.reply_text("This group is not in any networks.")
        return

    # Show first network's leaderboard
    network_id = networks[0]["id"]
    network_name = networks[0]["name"]

    leaderboard = await get_network_leaderboard(pool, network_id, limit=10)

    if not leaderboard:
        await update.message.reply_text(
            f"🏆 <b>{network_name} Leaderboard</b>\n\nNo XP recorded yet!"
        )
        return

    lines = [f"🏆 <b>{network_name} Leaderboard</b>", ""]

    for i, entry in enumerate(leaderboard, 1):
        medal = "👑" if i == 1 else f"{i}."
        lines.append(
            f"{medal} User {entry['user_id']} — {entry['total_xp']:,} XP "
            f"({entry['contributing_groups']} groups)"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ── Handler Registration ─────────────────────────────────────────────────────

engagement_handlers = [
    CommandHandler("rank", cmd_rank, filters=filters.ChatType.GROUPS),
    CommandHandler("top", cmd_top, filters=filters.ChatType.GROUPS),
    CommandHandler("leaderboard", cmd_top, filters=filters.ChatType.GROUPS),
    CommandHandler("levels", cmd_levels, filters=filters.ChatType.GROUPS),
    CommandHandler("rep", cmd_rep, filters=filters.ChatType.GROUPS),
    CommandHandler("profile", cmd_profile, filters=filters.ChatType.GROUPS),
    CommandHandler("checkin", cmd_checkin, filters=filters.ChatType.GROUPS),
    CommandHandler("badges", cmd_badges, filters=filters.ChatType.GROUPS),
    CommandHandler("repboard", cmd_repboard, filters=filters.ChatType.GROUPS),
    CommandHandler("givexp", cmd_givexp, filters=filters.ChatType.GROUPS),
    CommandHandler("removexp", cmd_removexp, filters=filters.ChatType.GROUPS),
    CommandHandler("doublexp", cmd_doublexp, filters=filters.ChatType.GROUPS),
    CommandHandler("network", cmd_network, filters=filters.ChatType.GROUPS),
    CommandHandler("joinnetwork", cmd_joinnetwork, filters=filters.ChatType.GROUPS),
    CommandHandler("createnetwork", cmd_createnetwork, filters=filters.ChatType.GROUPS),
    CommandHandler("networktop", cmd_networktop, filters=filters.ChatType.GROUPS),
]
