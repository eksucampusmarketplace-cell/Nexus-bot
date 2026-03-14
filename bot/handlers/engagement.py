"""
bot/handlers/engagement.py

Engagement system bot commands:
/rank, /top, /leaderboard, /levels, /rep, /profile, /givexp, /removexp,
/setlevel, /checkin, /badges, /repboard, /xpsettings, /doublexp, /resetxp
/network, /joinnetwork, /createnetwork, /leavenetwork, /networktop, /networkcast
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes, filters

from bot.engagement.xp import (
    award_xp, deduct_xp, calculate_level, xp_to_next_level, xp_for_level,
    get_leaderboard, get_member_rank, start_double_xp,
)
from bot.engagement.reputation import give_rep, get_reputation, get_rep_leaderboard, get_daily_remaining
from bot.engagement.badges import check_and_award_badges, get_member_badges, grant_badge_manually
from bot.engagement.network import (
    create_network, join_network, leave_network, broadcast_to_network,
    get_network_leaderboard, get_member_networks,
)

log = logging.getLogger("engagement")

GROUP = filters.ChatType.GROUPS


def _pool(context):
    return context.bot_data.get("db") or context.bot_data.get("db_pool")


def _redis(context):
    return context.bot_data.get("redis")


def _bot_id(context):
    info = context.bot_data.get("cached_bot_info", {})
    return info.get("id", 0)


def _progress_bar(pct: int, length: int = 10) -> str:
    filled = int(length * pct / 100)
    return "█" * filled + "░" * (length - filled)


async def cmd_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)

    target = update.message.reply_to_message
    if target and target.from_user:
        user = target.from_user
    elif context.args:
        await update.message.reply_text("❌ Please reply to a message to check another user's rank.")
        return
    else:
        user = update.effective_user

    rank_data = await get_member_rank(pool, chat_id, user.id, bot_id)
    badges = await get_member_badges(pool, chat_id, user.id, bot_id)
    badge_str = " ".join(b["emoji"] for b in badges[:5])
    extra = f"+{len(badges) - 5} more" if len(badges) > 5 else ""

    xp = rank_data.get("xp", 0)
    level = rank_data.get("level", 1)
    needed, next_total = xp_to_next_level(xp)
    pct = rank_data.get("progress_pct", 0)
    bar = _progress_bar(pct)
    streak = rank_data.get("streak_days", 0)
    rank_pos = rank_data.get("rank", 0)
    total = rank_data.get("total_members", 0)

    name = user.full_name
    text = (
        f"⭐ <b>{name}</b> — Level {level}\n\n"
        f"XP: {xp:,} / {next_total:,}\n"
        f"Progress: {bar} {pct}%\n\n"
        f"Rank: #{rank_pos} in this group ({total} members)\n"
        f"Streak: 🔥 {streak} days\n"
    )
    if badges:
        text += f"\nBadges: {badge_str} {extra}"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)

    board = await get_leaderboard(pool, chat_id, bot_id, limit=10)
    if not board:
        await update.message.reply_text("📊 No XP data yet. Start chatting to earn XP!")
        return

    medals = ["👑", "⭐", "🌟", "🏅", "🔹"]
    lines = [f"🏆 <b>Top Members</b>\n"]
    for i, entry in enumerate(board):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lines.append(
            f"{medal} User {entry['user_id']} — Lv.{entry['level']} {entry['xp']:,} XP"
        )

    user_rank = await get_member_rank(pool, chat_id, update.effective_user.id, bot_id)
    if user_rank.get("rank"):
        lines.append(
            f"\nYou: #{user_rank['rank']} — Lv.{user_rank['level']} — {user_rank['xp']:,} XP"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Full Leaderboard", callback_data="engagement:leaderboard"),
         InlineKeyboardButton("🏅 Rep Board", callback_data="engagement:repboard")]
    ])
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)


async def cmd_levels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    default_levels = [
        (1, 0, "Member"),
        (2, xp_for_level(2), "Regular"),
        (3, xp_for_level(3), "Active Member"),
        (5, xp_for_level(5), "⭐ Trusted"),
        (10, xp_for_level(10), "🌟 Veteran"),
        (20, xp_for_level(20), "💫 Legend"),
        (50, xp_for_level(50), "👑 Elite"),
    ]
    lines = ["📈 <b>Level Guide</b>\n"]
    for lvl, xp, title in default_levels:
        lines.append(f"Lv.{lvl} → {xp:,} XP — {title}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)

    target = update.message.reply_to_message
    if not target or not target.from_user:
        await update.message.reply_text("❌ Reply to a message to give +rep.")
        return

    to_user = target.from_user
    from_user = update.effective_user
    reason = " ".join(context.args) if context.args else None

    is_admin = False
    try:
        member = await context.bot.get_chat_member(chat_id, from_user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception:
        pass

    success, msg = await give_rep(
        pool, chat_id, from_user.id, to_user.id, bot_id,
        amount=1, reason=reason, is_admin=is_admin,
    )

    if success:
        rep_data = await get_reputation(pool, chat_id, to_user.id, bot_id)
        remaining = await get_daily_remaining(pool, chat_id, from_user.id, bot_id)
        text = (
            f"👍 +1 rep given to {to_user.mention_html()}\n"
            f"Their rep: {rep_data['rep_score']} (+1)\n"
            f"You have {remaining} more rep to give today."
        )
        if reason:
            text = f'👍 +1 rep given to {to_user.mention_html()}\nReason: "{reason}"\n' \
                   f"Their rep: {rep_data['rep_score']}\nYou have {remaining} more rep to give today."
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(msg)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)

    target = update.message.reply_to_message
    user = target.from_user if (target and target.from_user) else update.effective_user

    rank_data = await get_member_rank(pool, chat_id, user.id, bot_id)
    rep_data = await get_reputation(pool, chat_id, user.id, bot_id)
    badges = await get_member_badges(pool, chat_id, user.id, bot_id)

    badge_display = " ".join(b["emoji"] + " " + b["name"] for b in badges[:5])
    text = (
        f"👤 <b>{user.full_name}</b>"
        + (f" @{user.username}" if user.username else "") + "\n\n"
        f"Level: {rank_data.get('level', 1)} ⭐ | XP: {rank_data.get('xp', 0):,}\n"
        f"Rep: {rep_data.get('rep_score', 0)} 👍 | Rank: #{rank_data.get('rank', 0)}\n"
        f"Streak: 🔥 {rank_data.get('streak_days', 0)} days\n"
        f"Messages: {rank_data.get('total_messages', 0):,}\n"
    )
    if badges:
        text += f"\nBadges:\n{badge_display}"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_givexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    target = update.message.reply_to_message
    if not target or not target.from_user:
        await update.message.reply_text("❌ Reply to a message and provide amount: /givexp <amount> [reason]")
        return

    if not context.args:
        await update.message.reply_text("❌ Usage: /givexp <amount> [reason]")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number.")
        return

    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "admin_grant"
    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)
    to_user = target.from_user

    result = await award_xp(
        pool, _redis(context), context.bot,
        chat_id, to_user.id, bot_id,
        amount, reason, given_by=update.effective_user.id,
    )

    if result.get("ok"):
        await update.message.reply_text(
            f"✅ +{amount} XP given to {to_user.mention_html()}\n"
            f"Reason: \"{reason}\"\n"
            f"New total: {result['new_xp']:,} XP (Level {result['new_level']})\n"
            f"👮 By: {update.effective_user.mention_html()}",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(f"❌ Failed: {result.get('reason')}")


async def cmd_removexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    target = update.message.reply_to_message
    if not target or not target.from_user or not context.args:
        await update.message.reply_text("❌ Reply to a message: /removexp <amount> [reason]")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number.")
        return

    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "admin_remove"
    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)
    to_user = target.from_user

    result = await deduct_xp(
        pool, _redis(context),
        chat_id, to_user.id, bot_id,
        amount, reason, given_by=update.effective_user.id,
    )

    if result.get("ok"):
        await update.message.reply_text(
            f"✅ -{amount} XP removed from {to_user.mention_html()}\n"
            f"New total: {result['new_xp']:,} XP (Level {result['new_level']})",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(f"❌ Failed: {result.get('reason')}")


async def cmd_setlevel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    target = update.message.reply_to_message
    if not target or not target.from_user or not context.args:
        await update.message.reply_text("❌ Reply to a message: /setlevel <level>")
        return

    try:
        level = max(1, int(context.args[0]))
    except ValueError:
        await update.message.reply_text("❌ Level must be a number.")
        return

    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)
    to_user = target.from_user
    new_xp = xp_for_level(level)

    from db.ops.engagement import upsert_member_xp
    await upsert_member_xp(pool, chat_id, to_user.id, bot_id,
                           xp_delta=new_xp, level=level)

    await update.message.reply_text(
        f"✅ {to_user.mention_html()} set to Level {level} ({new_xp:,} XP)",
        parse_mode="HTML",
    )


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    from datetime import date
    from db.ops.engagement import get_member_xp, upsert_member_xp, get_xp_settings

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot_id = _bot_id(context)

    current = await get_member_xp(pool, chat_id, user_id, bot_id)
    settings = await get_xp_settings(pool, chat_id, bot_id)

    today = date.today()
    last_checkin = current.get("last_daily_checkin")
    if last_checkin == today:
        await update.message.reply_text("✅ You already checked in today! Come back tomorrow.")
        return

    xp_daily = settings.get("xp_per_daily", 10)
    streak = current.get("streak_days", 0)
    if last_checkin:
        from datetime import timedelta
        if last_checkin == today - timedelta(days=1):
            streak += 1
        else:
            streak = 1
    else:
        streak = 1

    bonus = 5 if streak >= 3 else 0
    total_xp = xp_daily + bonus

    result = await award_xp(
        pool, _redis(context), context.bot,
        chat_id, user_id, bot_id, total_xp, "daily",
    )

    await upsert_member_xp(pool, chat_id, user_id, bot_id,
                           xp_delta=0, level=result.get("new_level", 1),
                           last_daily_checkin=today, streak_days=streak)

    await check_and_award_badges(pool, chat_id, user_id, bot_id, "streak", streak)

    text = (
        f"✅ Daily check-in! +{xp_daily} XP\n\n"
        f"Streak: 🔥 {streak} days"
    )
    if bonus:
        text += f"\nBonus: +{bonus} XP streak bonus (3+ days)"
    text += f"\nTotal earned today: {total_xp} XP"
    if result.get("ok"):
        text += f"\n\nCurrent: Level {result['new_level']} — {result['new_xp']:,} XP"

    await update.message.reply_text(text)


async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    from db.ops.engagement import get_all_badges

    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)
    target = update.message.reply_to_message
    user = target.from_user if (target and target.from_user) else update.effective_user

    earned = await get_member_badges(pool, chat_id, user.id, bot_id)
    all_badges = await get_all_badges(pool, bot_id, chat_id)
    earned_ids = {b["badge_id"] for b in earned}
    locked = [b for b in all_badges if b["id"] not in earned_ids]

    lines = [f"🏅 <b>Badges — {user.full_name}</b>\n"]
    if earned:
        lines.append(f"<b>Earned ({len(earned)}):</b>")
        lines.append(" ".join(b["emoji"] + " " + b["name"] for b in earned))
    if locked:
        lines.append(f"\n<b>Locked ({len(locked)}):</b>")
        for b in locked[:5]:
            lines.append(f"{b['emoji']} {b['name']} — {b['description']}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_repboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)

    board = await get_rep_leaderboard(pool, chat_id, bot_id, limit=10)
    if not board:
        await update.message.reply_text("👍 No reputation data yet.")
        return

    lines = ["👍 <b>Reputation Board</b>\n"]
    medals = ["🏆", "", ""]
    for i, entry in enumerate(board):
        medal = medals[i] if i < len(medals) else ""
        lines.append(f"{i+1}. User {entry['user_id']} — {entry['rep_score']} rep {medal}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_resetxp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    target = update.message.reply_to_message
    if not target or not target.from_user:
        await update.message.reply_text("❌ Reply to a message to reset XP.")
        return

    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)
    to_user = target.from_user

    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM member_xp WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3",
            chat_id, to_user.id, bot_id,
        )

    await update.message.reply_text(
        f"✅ XP reset for {to_user.mention_html()}", parse_mode="HTML"
    )


async def cmd_doublexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    hours = 2
    if context.args:
        try:
            hours = max(1, min(24, int(context.args[0])))
        except ValueError:
            pass

    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)
    await start_double_xp(pool, chat_id, bot_id, hours)

    await update.message.reply_text(
        f"⚡ <b>Double XP activated for {hours} hours!</b>\n"
        f"All XP earnings are multiplied by 2x.",
        parse_mode="HTML",
    )


async def cmd_xpsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    from db.ops.engagement import get_xp_settings
    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)
    s = await get_xp_settings(pool, chat_id, bot_id)

    text = (
        f"⚙️ <b>XP Settings</b>\n\n"
        f"Enabled: {'✅' if s.get('enabled') else '❌'}\n"
        f"XP per message: {s.get('xp_per_message', 1)}\n"
        f"Message cooldown: {s.get('message_cooldown_s', 60)}s\n"
        f"XP per daily: {s.get('xp_per_daily', 10)}\n"
        f"XP per game win: {s.get('xp_per_game_win', 5)}\n"
        f"Admin grant max: {s.get('xp_admin_grant', 20)}\n"
        f"Level-up announce: {'✅' if s.get('level_up_announce') else '❌'}\n"
        f"Double XP: {'⚡ Active' if s.get('double_xp_active') else '❌'}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    networks = await get_member_networks(pool, chat_id)

    if not networks:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Join Network", callback_data="net:join"),
             InlineKeyboardButton("🆕 Create Network", callback_data="net:create")]
        ])
        await update.message.reply_text(
            "🌐 <b>Network Status</b>\n\nNot joined any networks yet.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return

    lines = ["🌐 <b>Network Status</b>\n", f"Networks joined: {len(networks)}\n"]
    for i, net in enumerate(networks, 1):
        lines.append(
            f"{i}. <b>{net['name']}</b>\n"
            f"   Groups: {net.get('member_count', '?')} | "
            f"Code: <code>{net['invite_code']}</code>"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Join Network", callback_data="net:join"),
         InlineKeyboardButton("🆕 Create Network", callback_data="net:create")]
    ])
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)


async def cmd_joinnetwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /joinnetwork <invite_code>")
        return

    chat_id = update.effective_chat.id
    bot_id = _bot_id(context)
    code = context.args[0]

    try:
        member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    success, msg = await join_network(pool, code, chat_id, bot_id)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_createnetwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /createnetwork <name>")
        return

    bot_id = _bot_id(context)
    name = " ".join(context.args)
    user_id = update.effective_user.id

    result = await create_network(pool, name, "", user_id, bot_id)
    if result["ok"]:
        await update.message.reply_text(
            f"✅ Network <b>{name}</b> created!\n"
            f"Invite code: <code>{result['invite_code']}</code>\n"
            f"Share this code for groups to join.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(f"❌ Failed: {result.get('reason')}")


async def cmd_leavenetwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /leavenetwork <network_id>")
        return

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    try:
        network_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Network ID must be a number.")
        return

    success = await leave_network(pool, network_id, update.effective_chat.id)
    if success:
        await update.message.reply_text("✅ Left the network.")
    else:
        await update.message.reply_text("❌ Not a member of that network.")


async def cmd_networktop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    networks = await get_member_networks(pool, chat_id)

    if not networks:
        await update.message.reply_text("❌ Not in any network. Use /joinnetwork to join one.")
        return

    network = networks[0]
    board = await get_network_leaderboard(pool, network["id"], limit=10)

    if not board:
        await update.message.reply_text("📊 No XP data in network yet.")
        return

    lines = [f"🌐 <b>Network Leaderboard — {network['name']}</b>\n"]
    medals = ["👑", "⭐", "🌟"]
    for i, entry in enumerate(board):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lines.append(
            f"{medal} User {entry['user_id']} — {entry['total_xp']:,} XP "
            f"({entry.get('contributing_groups', 1)} groups)"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_networkcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _pool(context)
    if not pool:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /networkcast <message>")
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text("❌ Admin only.")
            return
    except Exception:
        return

    networks = await get_member_networks(pool, chat_id)
    if not networks:
        await update.message.reply_text("❌ Not in any network.")
        return

    message_text = " ".join(context.args)
    network = networks[0]
    delivered = await broadcast_to_network(
        pool, context.bot, network["id"], chat_id, user_id, message_text
    )

    if delivered == -1:
        await update.message.reply_text("❌ Rate limited — max 1 broadcast per hour.")
    else:
        await update.message.reply_text(f"📢 Broadcast sent to {delivered} groups.")


engagement_handlers = [
    CommandHandler("rank", cmd_rank, filters=GROUP),
    CommandHandler("top", cmd_top, filters=GROUP),
    CommandHandler("leaderboard", cmd_top, filters=GROUP),
    CommandHandler("levels", cmd_levels, filters=GROUP),
    CommandHandler("rep", cmd_rep, filters=GROUP),
    CommandHandler("profile", cmd_profile, filters=GROUP),
    CommandHandler("givexp", cmd_givexp, filters=GROUP),
    CommandHandler("removexp", cmd_removexp, filters=GROUP),
    CommandHandler("setlevel", cmd_setlevel, filters=GROUP),
    CommandHandler("checkin", cmd_checkin, filters=GROUP),
    CommandHandler("badges", cmd_badges, filters=GROUP),
    CommandHandler("repboard", cmd_repboard, filters=GROUP),
    CommandHandler("xpsettings", cmd_xpsettings, filters=GROUP),
    CommandHandler("doublexp", cmd_doublexp, filters=GROUP),
    CommandHandler("resetxp", cmd_resetxp, filters=GROUP),
    CommandHandler("network", cmd_network, filters=GROUP),
    CommandHandler("joinnetwork", cmd_joinnetwork, filters=GROUP),
    CommandHandler("createnetwork", cmd_createnetwork),
    CommandHandler("leavenetwork", cmd_leavenetwork, filters=GROUP),
    CommandHandler("networktop", cmd_networktop, filters=GROUP),
    CommandHandler("networkcast", cmd_networkcast, filters=GROUP),
]
