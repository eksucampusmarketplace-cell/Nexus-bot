"""
bot/handlers/engagement.py

Bot commands for the XP, leveling, reputation, badge, and network systems.
"""

import asyncio
import logging
from datetime import date

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

from db.client import db

log = logging.getLogger("engagement.handlers")

GROUP = filters.ChatType.GROUPS


def _progress_bar(pct: int, width: int = 10) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def _get_pool(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("db") or context.bot_data.get("db_pool")


def _get_redis(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("redis")


async def _resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    if context.args:
        username = context.args[0].lstrip("@")
        try:
            member = await update.effective_chat.get_member(username)
            return member.user
        except Exception:
            pass
    return update.effective_user


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await update.effective_chat.get_member(update.effective_user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def _get_bot_id(context: ContextTypes.DEFAULT_TYPE) -> int:
    cached = context.bot_data.get("cached_bot_info")
    if cached:
        return cached["id"]
    me = await context.bot.get_me()
    return me.id


async def cmd_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)
    target = await _resolve_target(update, context)
    user_id = target.id

    from bot.engagement.xp import get_member_rank
    from bot.engagement.badges import get_member_badges

    rank_data = await get_member_rank(pool, chat_id, user_id, bot_id)
    badges = await get_member_badges(pool, chat_id, user_id, bot_id)

    if not rank_data:
        await update.message.reply_text("No XP data found for this user yet.")
        return

    name = target.full_name or target.first_name
    level = rank_data.get("level", 1)
    xp = rank_data.get("xp", 0)
    xp_to_next = rank_data.get("xp_to_next", 0)
    pct = rank_data.get("progress_pct", 0)
    rank = rank_data.get("rank", "?")
    total = rank_data.get("total_members", "?")

    badge_icons = " ".join(b["emoji"] for b in badges[:5])
    more_badges = f" +{len(badges) - 5} more" if len(badges) > 5 else ""

    from db.ops.engagement import get_member_xp
    xp_row = await get_member_xp(pool, chat_id, user_id, bot_id)
    streak = xp_row.get("streak_days", 0)

    text = (
        f"⭐ <b>{name}</b> — Level {level}\n\n"
        f"XP: {xp:,} / {xp + xp_to_next:,}\n"
        f"Progress: {_progress_bar(pct)} {pct}%\n\n"
        f"Rank: #{rank} of {total} in this group\n"
    )
    if streak:
        text += f"Streak: 🔥 {streak} days\n"
    if badge_icons:
        text += f"\nBadges: {badge_icons}{more_badges}"

    await update.message.reply_html(text)


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)

    from bot.engagement.xp import get_leaderboard
    entries = await get_leaderboard(pool, chat_id, bot_id, limit=10)

    if not entries:
        await update.message.reply_text("No XP data yet. Start chatting to earn XP!")
        return

    group_name = update.effective_chat.title or "Group"
    lines = [f"🏆 <b>Top Members — {group_name}</b>\n"]
    medals = {1: "👑", 2: "⭐", 3: "🌟"}
    for entry in entries:
        rank = entry["rank"]
        medal = medals.get(rank, f"{rank}.")
        lines.append(
            f"{medal} user {entry['user_id']} — Lv.{entry['level']} {entry['xp']:,} XP"
        )

    from db.ops.engagement import get_member_rank
    my_rank = await get_member_rank(pool, chat_id, update.effective_user.id, bot_id)
    from db.ops.engagement import get_member_xp
    my_xp = await get_member_xp(pool, chat_id, update.effective_user.id, bot_id)
    if my_rank:
        lines.append(
            f"\nYou: #{my_rank.get('rank', '?')} — Lv.{my_xp.get('level', 1)} — {my_xp.get('xp', 0):,} XP"
        )

    await update.message.reply_html("\n".join(lines))


async def cmd_levels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.engagement.xp import xp_for_level
    lines = ["📈 <b>Level Guide</b>\n"]
    milestones = [1, 2, 3, 5, 10, 20, 50]
    for lvl in milestones:
        xp = xp_for_level(lvl)
        lines.append(f"Lv.{lvl} → {xp:,} XP")
    await update.message.reply_html("\n".join(lines))


async def cmd_rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)
    from_user = update.effective_user

    if not update.message.reply_to_message and not context.args:
        await update.message.reply_text("Reply to a message or use /rep @username to give rep.")
        return

    target = await _resolve_target(update, context)
    if target.id == from_user.id:
        await update.message.reply_text("❌ You can't give rep to yourself.")
        return
    if target.is_bot:
        await update.message.reply_text("❌ You can't give rep to bots.")
        return

    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else None
    is_admin = await _is_admin(update, context)

    from bot.engagement.reputation import give_rep, get_daily_remaining
    ok, msg = await give_rep(
        pool, chat_id, from_user.id, target.id, bot_id,
        amount=1, reason=reason, is_admin=is_admin
    )

    if ok:
        from db.ops.engagement import get_member_rep
        rep_data = await get_member_rep(pool, chat_id, target.id, bot_id)
        remaining = await get_daily_remaining(pool, chat_id, from_user.id, bot_id)
        text = (
            f"👍 +1 rep given to {target.mention_html()}\n"
        )
        if reason:
            text += f"Reason: \"{reason}\"\n"
        text += (
            f"Their rep: {rep_data.get('rep_score', 0)} (+1)\n"
            f"You have {remaining} more rep to give today."
        )
        await update.message.reply_html(text)
    else:
        await update.message.reply_text(msg)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    if not pool:
        return
    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)
    target = await _resolve_target(update, context)

    from db.ops.engagement import get_member_xp, get_member_rep
    from bot.engagement.badges import get_member_badges
    from bot.engagement.xp import get_member_rank

    xp_data = await get_member_xp(pool, chat_id, target.id, bot_id)
    rep_data = await get_member_rep(pool, chat_id, target.id, bot_id)
    badges = await get_member_badges(pool, chat_id, target.id, bot_id)
    rank_data = await get_member_rank(pool, chat_id, target.id, bot_id)

    name = target.full_name or target.first_name
    level = xp_data.get("level", 1)
    xp = xp_data.get("xp", 0)
    streak = xp_data.get("streak_days", 0)
    messages = xp_data.get("total_messages", 0)
    rep = rep_data.get("rep_score", 0)
    rank = rank_data.get("rank", "?")

    badge_display = " ".join(f"{b['emoji']} {b['name']}" for b in badges[:6])

    text = (
        f"👤 <b>{name}</b>"
        + (f" @{target.username}" if target.username else "") + "\n\n"
        f"Level: {level} ⭐ | XP: {xp:,}\n"
        f"Rep: {rep} 👍 | Rank: #{rank}\n"
        f"Streak: 🔥 {streak} days\n"
        f"Messages: {messages:,}\n"
    )
    if badge_display:
        text += f"\n<b>Badges:</b>\n{badge_display}"

    await update.message.reply_html(text)


async def cmd_givexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    pool = _get_pool(context)
    redis = _get_redis(context)
    if not pool:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /givexp @user <amount> [reason]")
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)
    target = await _resolve_target(update, context)

    try:
        amount = int(context.args[1] if not context.args[0].startswith("@") else context.args[1])
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /givexp @user <amount> [reason]")
        return

    reason_parts = context.args[2:] if not context.args[0].startswith("@") else context.args[2:]
    reason = " ".join(reason_parts) if reason_parts else "admin_grant"

    from bot.engagement.xp import award_xp
    result = await award_xp(
        pool, redis, context.bot, chat_id, target.id, bot_id,
        amount, reason, given_by=update.effective_user.id
    )

    if result["ok"]:
        await update.message.reply_html(
            f"✅ +{amount} XP given to {target.mention_html()}\n"
            f"Reason: \"{reason}\"\n"
            f"New total: {result['new_xp']:,} XP (Level {result['new_level']})\n"
            f"👮 By: {update.effective_user.mention_html()}"
        )
    else:
        await update.message.reply_text(f"❌ Failed: {result.get('reason', 'unknown error')}")


async def cmd_removexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    pool = _get_pool(context)
    redis = _get_redis(context)
    if not pool:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removexp @user <amount> [reason]")
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)
    target = await _resolve_target(update, context)

    try:
        amount = int(context.args[1])
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid amount.")
        return

    reason = " ".join(context.args[2:]) if len(context.args) > 2 else "admin_remove"

    from bot.engagement.xp import deduct_xp
    result = await deduct_xp(
        pool, redis, chat_id, target.id, bot_id,
        amount, reason, given_by=update.effective_user.id
    )

    if result["ok"]:
        await update.message.reply_html(
            f"✅ -{amount} XP removed from {target.mention_html()}\n"
            f"New total: {result['new_xp']:,} XP (Level {result['new_level']})"
        )
    else:
        await update.message.reply_text(f"❌ Failed: {result.get('reason')}")


async def cmd_setlevel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    pool = _get_pool(context)
    redis = _get_redis(context)
    if not pool:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setlevel @user <level>")
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)
    target = await _resolve_target(update, context)

    try:
        new_level = int(context.args[-1])
    except ValueError:
        await update.message.reply_text("Invalid level number.")
        return

    from bot.engagement.xp import xp_for_level
    from db.ops.engagement import update_member_xp_direct
    new_xp = xp_for_level(new_level)
    await update_member_xp_direct(pool, chat_id, target.id, bot_id, new_xp, new_level)

    await update.message.reply_html(
        f"✅ {target.mention_html()} set to Level {new_level} ({new_xp:,} XP)"
    )


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    redis = _get_redis(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot_id = await _get_bot_id(context)

    from db.ops.engagement import get_member_xp, update_daily_checkin
    from bot.engagement.xp import award_xp

    xp_data = await get_member_xp(pool, chat_id, user_id, bot_id)
    today = date.today()
    last_checkin = xp_data.get("last_daily_checkin")

    if last_checkin and last_checkin == today:
        await update.message.reply_text("✅ Already checked in today! Come back tomorrow.")
        return

    streak = xp_data.get("streak_days", 0)
    from datetime import timedelta
    yesterday = today - timedelta(days=1)
    if last_checkin == yesterday:
        streak += 1
    else:
        streak = 1

    base_xp = 10
    bonus_xp = 5 if streak >= 3 else 0
    total_xp = base_xp + bonus_xp

    result = await award_xp(
        pool, redis, context.bot, chat_id, user_id, bot_id,
        total_xp, "daily", given_by=None
    )
    await update_daily_checkin(pool, chat_id, user_id, bot_id, today, streak)

    text = f"✅ Daily check-in! +{base_xp} XP\n\nStreak: 🔥 {streak} days\n"
    if bonus_xp:
        text += f"Bonus: +{bonus_xp} XP streak bonus ({streak}+ days)\n"
    text += f"Total earned today: {total_xp} XP\n\nCurrent: Level {result.get('new_level', 1)} — {result.get('new_xp', 0):,} XP"

    await update.message.reply_text(text)


async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)
    target = await _resolve_target(update, context)

    from bot.engagement.badges import get_member_badges
    from db.ops.engagement import get_all_badges

    earned = await get_member_badges(pool, chat_id, target.id, bot_id)
    all_badges = await get_all_badges(pool, bot_id, chat_id)
    earned_ids = {b["badge_id"] for b in earned}

    name = target.full_name or target.first_name
    lines = [f"🏅 <b>Badges — {name}</b>\n"]

    earned_list = [b for b in all_badges if b["id"] in earned_ids]
    locked_list = [b for b in all_badges if b["id"] not in earned_ids]

    if earned_list:
        lines.append(f"<b>Earned ({len(earned_list)}):</b>")
        icons = " ".join(f"{b['emoji']} {b['name']}" for b in earned_list[:8])
        lines.append(icons)
    else:
        lines.append("No badges yet. Keep chatting!")

    if locked_list:
        lines.append(f"\n<b>Locked ({len(locked_list)}):</b>")
        for b in locked_list[:5]:
            lines.append(f"🔒 {b['emoji']} {b['name']} — {b.get('description', '')}")

    await update.message.reply_html("\n".join(lines))


async def cmd_repboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)

    from bot.engagement.reputation import get_rep_leaderboard
    entries = await get_rep_leaderboard(pool, chat_id, bot_id, limit=10)

    if not entries:
        await update.message.reply_text("No reputation data yet.")
        return

    group_name = update.effective_chat.title or "Group"
    lines = [f"👍 <b>Reputation Board — {group_name}</b>\n"]
    medals = {1: "🏆", 2: "", 3: ""}
    for entry in entries:
        rank = entry["rank"]
        medal = medals.get(rank, "")
        lines.append(f"{rank}. user {entry['user_id']} — {entry['rep_score']} rep {medal}")

    await update.message.reply_html("\n".join(lines))


async def cmd_xpsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)

    from db.ops.engagement import get_xp_settings
    s = await get_xp_settings(pool, chat_id, bot_id)

    text = (
        f"⚙️ <b>XP Settings</b>\n\n"
        f"Enabled: {'✅' if s.get('enabled') else '❌'}\n"
        f"XP per message: {s.get('xp_per_message', 1)}\n"
        f"Cooldown: {s.get('message_cooldown_s', 60)}s\n"
        f"XP per daily: {s.get('xp_per_daily', 10)}\n"
        f"XP per game win: {s.get('xp_per_game_win', 5)}\n"
        f"Admin grant max: {s.get('xp_admin_grant', 20)}\n"
        f"Level-up announce: {'✅' if s.get('level_up_announce') else '❌'}\n"
        f"Double XP: {'⚡ ACTIVE' if s.get('double_xp_active') else '❌'}\n"
    )
    await update.message.reply_html(text)


async def cmd_doublexp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)

    hours = 2
    if context.args:
        try:
            hours = int(context.args[0])
        except ValueError:
            pass

    from bot.engagement.xp import start_double_xp
    await start_double_xp(pool, chat_id, bot_id, hours)
    await update.message.reply_text(f"⚡ Double XP enabled for {hours} hours!")


async def cmd_resetxp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)
    target = await _resolve_target(update, context)

    from db.ops.engagement import update_member_xp_direct
    await update_member_xp_direct(pool, chat_id, target.id, bot_id, 0, 1)
    await update.message.reply_html(f"✅ XP reset for {target.mention_html()}")


async def cmd_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    from bot.engagement.network import get_member_networks
    networks = await get_member_networks(pool, chat_id)

    if not networks:
        await update.message.reply_text(
            "🌐 No networks joined.\n\n"
            "Use /joinnetwork <code> to join or /createnetwork <name> to create one."
        )
        return

    group_name = update.effective_chat.title or "Group"
    lines = [f"🌐 <b>Network Status — {group_name}</b>\n", f"Networks joined: {len(networks)}\n"]
    for net in networks:
        lines.append(
            f"<b>{net['name']}</b>\n"
            f"Groups: {net.get('member_count', '?')} | Code: <code>{net['invite_code']}</code>\n"
        )

    await update.message.reply_html("\n".join(lines))


async def cmd_joinnetwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /joinnetwork <invite_code>")
        return

    pool = _get_pool(context)
    if not pool:
        return

    bot_id = await _get_bot_id(context)
    code = context.args[0].upper()

    from bot.engagement.network import join_network
    ok, msg = await join_network(pool, code, update.effective_chat.id, bot_id)
    await update.message.reply_text(msg)


async def cmd_createnetwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /createnetwork <name>")
        return

    pool = _get_pool(context)
    if not pool:
        return

    bot_id = await _get_bot_id(context)
    name = " ".join(context.args)

    from bot.engagement.network import create_network
    result = await create_network(
        pool, name, None,
        update.effective_user.id, bot_id
    )

    if result["ok"]:
        await update.message.reply_html(
            f"✅ Network <b>{name}</b> created!\n"
            f"Invite code: <code>{result['invite_code']}</code>\n\n"
            f"Share this code with other groups to join your network."
        )
    else:
        await update.message.reply_text("❌ Failed to create network.")


async def cmd_leavenetwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /leavenetwork <network_id>")
        return

    pool = _get_pool(context)
    if not pool:
        return

    try:
        network_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid network ID.")
        return

    from bot.engagement.network import leave_network
    ok = await leave_network(pool, network_id, update.effective_chat.id)
    if ok:
        await update.message.reply_text("✅ Left the network.")
    else:
        await update.message.reply_text("❌ Failed to leave network (not a member?).")


async def cmd_networktop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    from bot.engagement.network import get_member_networks, get_network_leaderboard
    networks = await get_member_networks(pool, chat_id)

    if not networks:
        await update.message.reply_text("Not in any network. Use /joinnetwork to join one.")
        return

    network = networks[0]
    entries = await get_network_leaderboard(pool, network["id"], limit=10)

    if not entries:
        await update.message.reply_text("No network XP data yet.")
        return

    lines = [f"🌐 <b>{network['name']} — Leaderboard</b>\n"]
    for entry in entries:
        lines.append(
            f"{entry['rank']}. user {entry['user_id']} — {entry['total_xp']:,} XP "
            f"({entry['contributing_groups']} groups)"
        )

    await update.message.reply_html("\n".join(lines))


async def cmd_networkcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /networkcast <message>")
        return

    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    message_text = " ".join(context.args)

    from bot.engagement.network import get_member_networks, broadcast_to_network
    networks = await get_member_networks(pool, chat_id)

    if not networks:
        await update.message.reply_text("Not in any network.")
        return

    network = networks[0]
    delivered = await broadcast_to_network(
        pool, context.bot, network["id"], chat_id,
        update.effective_user.id, message_text
    )

    if delivered == -1:
        await update.message.reply_text("❌ Rate limited. Max 1 broadcast per hour per network.")
    else:
        await update.message.reply_text(f"✅ Broadcast sent to {delivered} groups.")


async def cmd_setlevelreward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Admin only command.")
        return
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /setlevelreward <level> <title|role> <value>")
        return

    pool = _get_pool(context)
    if not pool:
        return

    chat_id = update.effective_chat.id
    bot_id = await _get_bot_id(context)

    try:
        level = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid level.")
        return

    reward_type = context.args[1]
    reward_value = " ".join(context.args[2:])

    from db.ops.engagement import add_level_reward
    await add_level_reward(pool, chat_id, bot_id, level, reward_type, reward_value)
    await update.message.reply_text(f"✅ Level {level} reward set: {reward_type} = {reward_value}")


def register_engagement_handlers(app: Application):
    app.add_handler(CommandHandler("rank", cmd_rank, filters=GROUP))
    app.add_handler(CommandHandler("top", cmd_top, filters=GROUP))
    app.add_handler(CommandHandler("leaderboard", cmd_top, filters=GROUP))
    app.add_handler(CommandHandler("levels", cmd_levels, filters=GROUP))
    app.add_handler(CommandHandler("rep", cmd_rep, filters=GROUP))
    app.add_handler(CommandHandler("profile", cmd_profile, filters=GROUP))
    app.add_handler(CommandHandler("givexp", cmd_givexp, filters=GROUP))
    app.add_handler(CommandHandler("removexp", cmd_removexp, filters=GROUP))
    app.add_handler(CommandHandler("setlevel", cmd_setlevel, filters=GROUP))
    app.add_handler(CommandHandler("checkin", cmd_checkin, filters=GROUP))
    app.add_handler(CommandHandler("badges", cmd_badges, filters=GROUP))
    app.add_handler(CommandHandler("repboard", cmd_repboard, filters=GROUP))
    app.add_handler(CommandHandler("xpsettings", cmd_xpsettings, filters=GROUP))
    app.add_handler(CommandHandler("doublexp", cmd_doublexp, filters=GROUP))
    app.add_handler(CommandHandler("resetxp", cmd_resetxp, filters=GROUP))
    app.add_handler(CommandHandler("setlevelreward", cmd_setlevelreward, filters=GROUP))
    app.add_handler(CommandHandler("network", cmd_network, filters=GROUP))
    app.add_handler(CommandHandler("joinnetwork", cmd_joinnetwork, filters=GROUP))
    app.add_handler(CommandHandler("createnetwork", cmd_createnetwork, filters=GROUP))
    app.add_handler(CommandHandler("leavenetwork", cmd_leavenetwork, filters=GROUP))
    app.add_handler(CommandHandler("networktop", cmd_networktop, filters=GROUP))
    app.add_handler(CommandHandler("networkcast", cmd_networkcast, filters=GROUP))
