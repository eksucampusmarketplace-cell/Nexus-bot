"""
bot/handlers/economy.py

User-facing economy commands:
  /redeem <code>    — redeem promo code
  /referral         — get referral link + stats
  /mystars          — show bonus Stars balance + active purchases

Admin-only commands (OWNER_ID only):
  /grantbonus <user_id> <amount> [reason]  — give bonus Stars to user
  /createpromo <code> <type> <value> [...] — create promo code
  /promoinfo <code>                        — show code stats
  /disablepromo <code>                     — deactivate code

Logs prefix: [ECONOMY_CMD]
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from config import settings
from bot.billing.stars_economy import (
    get_bonus_balance, grant_bonus_stars, spend_bonus_stars,
    redeem_promo_code, create_promo_code, get_referral_link,
    get_referral_stats, record_referral, REFERRAL_BONUS_STARS
)
from bot.billing.entitlements import STARS_PRICES, ITEM_LABELS

log = logging.getLogger("economy_cmd")


async def cmd_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /redeem <code>
    Redeem a promo code.
    Works in private chat only.
    """
    user = update.effective_user
    db   = context.bot_data.get("db")

    if update.effective_chat.type != "private":
        await update.message.reply_text("Please use /redeem in our private chat.")
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Usage: /redeem <code>\n\nExample: /redeem NEXUS2024"
        )
        return

    code   = context.args[0]
    result = await redeem_promo_code(db, context.bot, user.id, code)

    if not result["ok"]:
        await update.message.reply_text(
            f"❌ {result['message']}\n\n"
            f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
        )
        return

    await update.message.reply_text(
        f"{result['message']}\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}",
        parse_mode=ParseMode.HTML
    )
    log.info(f"[ECONOMY_CMD] Redeemed | user={user.id} code={code}")


async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /referral
    Show referral link and stats.
    """
    user = update.effective_user
    db   = context.bot_data.get("db")
    me   = await context.bot.get_me()

    link  = await get_referral_link(me.username, user.id)
    stats = await get_referral_stats(db, user.id)

    await update.message.reply_text(
        f"🔗 <b>Your Referral Link</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"Share this link. When someone signs up and makes their first purchase:\n"
        f"  • You earn <b>⭐{REFERRAL_BONUS_STARS} bonus Stars</b>\n"
        f"  • They get a welcome bonus too\n\n"
        f"<b>Your Stats:</b>\n"
        f"  Total referrals: {stats['total_referrals']}\n"
        f"  Converted:       {stats['rewarded']}\n"
        f"  Pending:         {stats['pending']}\n"
        f"  Stars earned:    ⭐{stats['stars_earned']}\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📤 Share Link", switch_inline_query=link)
        ]])
    )


async def cmd_mystars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /mystars
    Show bonus Stars balance and active feature purchases.
    """
    user = update.effective_user
    db   = context.bot_data.get("db")

    balance = await get_bonus_balance(db, user.id)

    # Get active purchases
    rows = await db.fetch(
        """
        SELECT item_type, MAX(expires_at) as expires_at
        FROM stars_purchases
        WHERE owner_id=$1 AND expires_at > NOW()
        GROUP BY item_type
        ORDER BY expires_at ASC
        """,
        user.id
    )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    active_lines = []
    for r in rows:
        days  = (r["expires_at"] - now).days
        label = ITEM_LABELS.get(r["item_type"], r["item_type"])
        active_lines.append(f"  ✅ {label} — {days}d left")

    active_str = "\n".join(active_lines) if active_lines else "  None"

    await update.message.reply_text(
        f"⭐ <b>Your Stars</b>\n\n"
        f"Bonus Stars balance: <b>⭐{balance}</b>\n"
        f"<i>Earned via referrals and promo codes</i>\n\n"
        f"<b>Active Features:</b>\n{active_str}\n\n"
        f"Use /referral to earn more bonus Stars.\n"
        f"Use /redeem <code> to redeem promo codes.\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}",
        parse_mode=ParseMode.HTML
    )


async def cmd_spend_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /spendbonus <item_type>
    Spend bonus Stars to unlock a feature.
    Shows available items if no args.
    """
    user = update.effective_user
    db   = context.bot_data.get("db")

    if not context.args:
        balance = await get_bonus_balance(db, user.id)
        lines   = [f"⭐ <b>Spend Bonus Stars</b>\n\nBalance: ⭐{balance}\n\nAvailable:\n"]
        for item, stars in STARS_PRICES.items():
            label = ITEM_LABELS.get(item, item)
            lines.append(f"  /spendbonus {item} — ⭐{stars} — {label}\n")
        await update.message.reply_text(
            "".join(lines) + f"\n⚡ Powered by {settings.BOT_DISPLAY_NAME}",
            parse_mode=ParseMode.HTML
        )
        return

    item_type = context.args[0]
    if item_type not in STARS_PRICES:
        await update.message.reply_text("❌ Unknown item. Use /spendbonus to see options.")
        return

    cost   = STARS_PRICES[item_type]
    result = await spend_bonus_stars(db, user.id, cost, item_type)

    if not result["ok"]:
        await update.message.reply_text(
            f"❌ {result['error']}\n\n"
            f"Use /referral to earn more bonus Stars.\n\n"
            f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
        )
        return

    label = ITEM_LABELS.get(item_type, item_type)
    await update.message.reply_text(
        f"✅ <b>{label}</b> unlocked using ⭐{cost} bonus Stars!\n\n"
        f"Remaining balance: ⭐{result['remaining_balance']}\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}",
        parse_mode=ParseMode.HTML
    )


# ── ADMIN COMMANDS (OWNER_ID only) ────────────────────────────────────────

async def cmd_grant_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /grantbonus <user_id> <amount> [reason]
    Grant bonus Stars to any user. Owner only.
    """
    if update.effective_user.id != settings.OWNER_ID:
        return
    db = context.bot_data.get("db")
    try:
        target_id = int(context.args[0])
        amount    = int(context.args[1])
        reason    = " ".join(context.args[2:]) if len(context.args) > 2 else "admin_grant"
    except (IndexError, ValueError):
        await update.message.reply_text("❓ Usage: /grantbonus <user_id> <amount> [reason]")
        return

    balance = await grant_bonus_stars(db, target_id, amount, reason,
                                       granted_by=update.effective_user.id)

    # Notify recipient
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"🎁 <b>Bonus Stars received!</b>\n\n"
                f"You were granted <b>⭐{amount} bonus Stars</b>.\n"
                f"New balance: ⭐{balance}\n\n"
                f"Use /spendbonus to unlock features.\n\n"
                f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
            ),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Granted ⭐{amount} to user {target_id}. New balance: ⭐{balance}"
    )
    log.info(f"[ECONOMY_CMD] Admin grant | target={target_id} amount={amount}")


async def cmd_create_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /createpromo <code> <type> <value> [days] [max_uses] [expire_days]

    Types:
      bonus_stars <amount>
      feature_unlock <feat_name>
      group_slot
      clone_slot

    Examples:
      /createpromo NEXUS100 bonus_stars 100
      /createpromo VIPMUSIC feature_unlock feat_music 30 50
      /createpromo NEWUSER group_slot 0 30 100 7
    """
    if update.effective_user.id != settings.OWNER_ID:
        return
    db = context.bot_data.get("db")

    try:
        code        = context.args[0]
        reward_type = context.args[1]
        raw_value   = context.args[2] if len(context.args) > 2 else "0"
        days        = int(context.args[3]) if len(context.args) > 3 else 30
        max_uses    = int(context.args[4]) if len(context.args) > 4 else 1
        expire_days = int(context.args[5]) if len(context.args) > 5 else 0
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❓ Usage: /createpromo <code> <type> <value> [days] [max_uses] [expire_days]\n\n"
            "Types: bonus_stars, feature_unlock, group_slot, clone_slot"
        )
        return

    reward_value   = 0
    reward_feature = ""

    if reward_type == "bonus_stars":
        reward_value = int(raw_value)
    elif reward_type == "feature_unlock":
        reward_feature = raw_value
    elif reward_type in ("group_slot", "clone_slot"):
        pass
    else:
        await update.message.reply_text(f"❌ Unknown type: {reward_type}")
        return

    result = await create_promo_code(
        db,
        created_by=update.effective_user.id,
        code=code,
        reward_type=reward_type,
        reward_value=reward_value,
        reward_feature=reward_feature,
        reward_days=days,
        max_uses=max_uses,
        expires_days=expire_days,
    )

    if result["ok"]:
        await update.message.reply_text(
            f"✅ Promo code created: <code>{result['code']}</code>\n\n"
            f"Type: {reward_type}\n"
            f"Value: {reward_value or reward_feature or reward_type}\n"
            f"Days: {days}\n"
            f"Max uses: {max_uses} (0=unlimited)\n"
            f"Expires: {'Never' if not expire_days else f'{expire_days} days'}",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(f"❌ {result['error']}")


async def cmd_promo_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/promoinfo <code> — Show code stats. Owner only."""
    if update.effective_user.id != settings.OWNER_ID:
        return
    db   = context.bot_data.get("db")
    code = (context.args[0] if context.args else "").upper()
    if not code:
        await update.message.reply_text("❓ Usage: /promoinfo <code>")
        return

    row = await db.fetchrow(
        "SELECT * FROM promo_codes WHERE UPPER(code)=$1", code
    )
    if not row:
        await update.message.reply_text("❌ Code not found.")
        return

    await update.message.reply_text(
        f"📊 <b>Promo: {row['code']}</b>\n\n"
        f"Type: {row['reward_type']}\n"
        f"Value: {row['reward_value'] or row['reward_feature'] or '-'}\n"
        f"Days: {row['reward_days']}\n"
        f"Uses: {row['current_uses']}/{row['max_uses'] or '∞'}\n"
        f"Active: {'✅' if row['is_active'] else '❌'}\n"
        f"Expires: {row['expires_at'] or 'Never'}",
        parse_mode=ParseMode.HTML
    )


async def cmd_disable_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/disablepromo <code> — Deactivate a code. Owner only."""
    if update.effective_user.id != settings.OWNER_ID:
        return
    db   = context.bot_data.get("db")
    code = (context.args[0] if context.args else "").upper()
    await db.execute(
        "UPDATE promo_codes SET is_active=FALSE WHERE UPPER(code)=$1", code
    )
    await update.message.reply_text(f"✅ Code {code} disabled.")


# ── /start referral handler ───────────────────────────────────────────────

async def handle_start_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Called from /start handler when payload is ref_{user_id}.
    Records referral if not already referred.
    """
    user = update.effective_user
    db   = context.bot_data.get("db")

    payload = context.args[0] if context.args else ""
    if not payload.startswith("ref_"):
        return False  # not a referral

    try:
        referrer_id = int(payload[4:])
        await record_referral(db, referrer_id, user.id)
    except (ValueError, Exception):
        pass

    return True  # was a referral start


# ── Handler objects ───────────────────────────────────────────────────────
economy_handlers = [
    CommandHandler("redeem",       cmd_redeem),
    CommandHandler("referral",     cmd_referral),
    CommandHandler("mystars",      cmd_mystars),
    CommandHandler("spendbonus",   cmd_spend_bonus),
    CommandHandler("grantbonus",   cmd_grant_bonus),
    CommandHandler("createpromo",  cmd_create_promo),
    CommandHandler("promoinfo",    cmd_promo_info),
    CommandHandler("disablepromo", cmd_disable_promo),
]
