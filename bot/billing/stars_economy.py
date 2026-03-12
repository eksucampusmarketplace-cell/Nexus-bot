"""
bot/billing/stars_economy.py

Manages bonus Stars, referrals, and promo codes.

Bonus Stars:
  Internal credits, NOT real Telegram Stars.
  Granted by admin or earned via referrals/promos.
  Spent exactly like real Stars for feature unlocks.
  Balance tracked in bonus_stars table (ledger model).

Referral system:
  Owner shares /start?ref={their_user_id} link.
  When referred user makes first real Stars purchase:
    → referrer earns REFERRAL_BONUS_STARS bonus Stars
    → referred user earns REFERRAL_REFERRED_BONUS bonus Stars
  No reward for just clicking link — requires purchase.

Promo codes:
  Admin creates codes via /createpromo command.
  Types: bonus_stars | feature_unlock | group_slot | clone_slot
  Max uses, expiry date, one use per user.

Logs prefix: [ECONOMY]
"""

import logging
from datetime import datetime, timezone, timedelta

from config import settings
from bot.billing.entitlements import (
    grant_entitlement, invalidate_cache
)

log = logging.getLogger("economy")


# ── BONUS STARS ─────────────────────────────────────────────────────────────

async def get_bonus_balance(db, owner_id: int) -> int:
    """Get current bonus Stars balance for owner."""
    row = await db.fetchrow(
        "SELECT balance FROM bonus_stars_balance WHERE owner_id=$1",
        owner_id
    )
    return row["balance"] if row else 0


async def grant_bonus_stars(
    db,
    owner_id: int,
    amount: int,
    reason: str,
    granted_by: int = 0
) -> int:
    """
    Grant bonus Stars to owner.
    Returns new balance.
    Logs to bonus_stars ledger.
    """
    await db.execute(
        """
        INSERT INTO bonus_stars (owner_id, amount, reason, granted_by)
        VALUES ($1,$2,$3,$4)
        """,
        owner_id, amount, reason, granted_by or None
    )
    balance = await get_bonus_balance(db, owner_id)
    log.info(f"[ECONOMY] Bonus granted | owner={owner_id} amount={amount} reason={reason} balance={balance}")
    return balance


async def spend_bonus_stars(
    db,
    owner_id: int,
    amount: int,
    item_type: str
) -> dict:
    """
    Spend bonus Stars to unlock a feature.
    Returns { ok, error, remaining_balance }

    Steps:
      1. Check balance >= amount
      2. Deduct from ledger (negative entry)
      3. Grant entitlement
      4. Invalidate cache
    """
    balance = await get_bonus_balance(db, owner_id)
    if balance < amount:
        return {
            "ok":    False,
            "error": f"Not enough bonus Stars. You have ⭐{balance}, need ⭐{amount}.",
        }

    # Deduct
    await db.execute(
        """
        INSERT INTO bonus_stars (owner_id, amount, reason)
        VALUES ($1,$2,'purchase_spend')
        """,
        owner_id, -amount
    )

    # Grant entitlement (same as real Stars)
    await grant_entitlement(db, owner_id, item_type)
    invalidate_cache(owner_id)

    # Record in payment_events
    await db.execute(
        """
        INSERT INTO payment_events (owner_id, event_type, item_type, stars_paid)
        VALUES ($1,'bonus_stars_spend',$2,$3)
        """,
        owner_id, item_type, amount
    )

    new_balance = await get_bonus_balance(db, owner_id)
    log.info(f"[ECONOMY] Bonus spent | owner={owner_id} amount={amount} item={item_type} remaining={new_balance}")
    return {"ok": True, "remaining_balance": new_balance}


# ── REFERRALS ────────────────────────────────────────────────────────────────

REFERRAL_BONUS_STARS    = getattr(settings, "REFERRAL_BONUS_STARS",    100)
REFERRAL_REFERRED_BONUS = getattr(settings, "REFERRAL_REFERRED_BONUS",  50)


async def record_referral(db, referrer_id: int, referred_id: int) -> bool:
    """
    Record that referred_id joined via referrer_id's link.
    Returns False if referred_id already has a referral record.
    """
    if referrer_id == referred_id:
        return False

    try:
        await db.execute(
            """
            INSERT INTO referrals (referrer_id, referred_id, bonus_stars)
            VALUES ($1,$2,$3)
            ON CONFLICT (referred_id) DO NOTHING
            """,
            referrer_id, referred_id, REFERRAL_BONUS_STARS
        )
        log.info(f"[ECONOMY] Referral recorded | referrer={referrer_id} referred={referred_id}")
        return True
    except Exception as e:
        log.warning(f"[ECONOMY] Referral record failed | {e}")
        return False


async def process_referral_reward(db, bot, referred_id: int):
    """
    Called after referred user makes their FIRST real Stars purchase.
    Grants bonus Stars to both referrer and referred user.
    Sends notification DMs.
    """
    row = await db.fetchrow(
        "SELECT * FROM referrals WHERE referred_id=$1 AND rewarded=FALSE",
        referred_id
    )
    if not row:
        return

    referrer_id = row["referrer_id"]

    # Grant to referrer
    referrer_balance = await grant_bonus_stars(
        db, referrer_id, REFERRAL_BONUS_STARS, "referral_reward"
    )

    # Grant to referred user
    referred_balance = await grant_bonus_stars(
        db, referred_id, REFERRAL_REFERRED_BONUS, "referral_reward"
    )

    # Mark rewarded
    await db.execute(
        "UPDATE referrals SET rewarded=TRUE, rewarded_at=NOW() WHERE referred_id=$1",
        referred_id
    )

    # DM referrer
    try:
        await bot.send_message(
            chat_id=referrer_id,
            text=(
                f"🎉 <b>Referral reward!</b>\n\n"
                f"Someone you referred just made their first purchase.\n"
                f"You earned <b>⭐{REFERRAL_BONUS_STARS} bonus Stars</b>!\n\n"
                f"Balance: ⭐{referrer_balance} bonus Stars\n\n"
                f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    # DM referred user
    try:
        await bot.send_message(
            chat_id=referred_id,
            text=(
                f"🎁 <b>Welcome bonus!</b>\n\n"
                f"You earned <b>⭐{REFERRAL_REFERRED_BONUS} bonus Stars</b> "
                f"for joining via a referral.\n\n"
                f"Balance: ⭐{referred_balance} bonus Stars\n"
                f"Use them to unlock features!\n\n"
                f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    log.info(f"[ECONOMY] Referral rewarded | referrer={referrer_id} referred={referred_id}")


async def get_referral_link(bot_username: str, owner_id: int) -> str:
    """Generate referral link for owner."""
    return f"https://t.me/{bot_username}?start=ref_{owner_id}"


async def get_referral_stats(db, owner_id: int) -> dict:
    """Get referral stats for owner."""
    total = await db.fetchval(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id=$1", owner_id
    )
    rewarded = await db.fetchval(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id=$1 AND rewarded=TRUE", owner_id
    )
    pending = total - rewarded
    earned  = rewarded * REFERRAL_BONUS_STARS
    return {
        "total_referrals":   total,
        "rewarded":          rewarded,
        "pending":           pending,
        "stars_earned":      earned,
        "bonus_per_referral": REFERRAL_BONUS_STARS,
    }


# ── PROMO CODES ──────────────────────────────────────────────────────────────

async def redeem_promo_code(
    db,
    bot,
    owner_id: int,
    code: str
) -> dict:
    """
    Redeem a promo code for owner.
    Returns { ok, message, reward_type, reward_value }

    Validation:
      - Code exists and is_active
      - Not expired
      - Not exceeded max_uses (0 = unlimited)
      - Owner hasn't already redeemed this code
    """
    code = code.strip().upper()

    promo = await db.fetchrow(
        "SELECT * FROM promo_codes WHERE UPPER(code)=$1 AND is_active=TRUE",
        code
    )

    if not promo:
        return {"ok": False, "message": "Invalid or expired promo code."}

    # Check expiry
    if promo["expires_at"] and promo["expires_at"] < datetime.now(timezone.utc):
        return {"ok": False, "message": "This promo code has expired."}

    # Check max uses
    if promo["max_uses"] > 0 and promo["current_uses"] >= promo["max_uses"]:
        return {"ok": False, "message": "This promo code has been fully redeemed."}

    # Check if already redeemed by this user
    already = await db.fetchval(
        "SELECT COUNT(*) FROM promo_redemptions WHERE code_id=$1 AND owner_id=$2",
        promo["id"], owner_id
    )
    if already:
        return {"ok": False, "message": "You've already redeemed this code."}

    # Apply reward
    reward_type    = promo["reward_type"]
    reward_value   = promo["reward_value"]
    reward_feature = promo["reward_feature"]
    reward_days    = promo["reward_days"]
    message        = ""

    ITEM_LABELS = {
        "feat_music": "Music Player",
        "feat_autojoin": "Auto Join",
        "feat_analytics": "Analytics",
        "feat_webhooks": "Webhooks",
        "group_slot": "Additional Group Slot",
        "clone_slot": "Additional Clone Slot",
    }

    if reward_type == "bonus_stars":
        await grant_bonus_stars(db, owner_id, reward_value, "promo_code")
        balance = await get_bonus_balance(db, owner_id)
        message = f"🎉 You received ⭐{reward_value} bonus Stars! Balance: ⭐{balance}"

    elif reward_type == "feature_unlock":
        # Grant via stars_purchases (same as Stars payment, but free)
        expires_at = datetime.now(timezone.utc) + timedelta(days=reward_days)
        await db.execute(
            """
            INSERT INTO stars_purchases
                (owner_id, telegram_charge_id, item_type, stars_paid, expires_at)
            VALUES ($1,$2,$3,0,$4)
            ON CONFLICT (telegram_charge_id) DO NOTHING
            """,
            owner_id,
            f"promo_{code}_{owner_id}",
            reward_feature,
            expires_at
        )
        await grant_entitlement(db, owner_id, reward_feature)
        invalidate_cache(owner_id)
        label   = ITEM_LABELS.get(reward_feature, reward_feature)
        message = f"🎉 <b>{label}</b> unlocked for {reward_days} days!"

    elif reward_type in ("group_slot", "clone_slot"):
        expires_at = datetime.now(timezone.utc) + timedelta(days=reward_days)
        await db.execute(
            """
            INSERT INTO stars_purchases
                (owner_id, telegram_charge_id, item_type, stars_paid, expires_at)
            VALUES ($1,$2,$3,0,$4)
            ON CONFLICT (telegram_charge_id) DO NOTHING
            """,
            owner_id,
            f"promo_{code}_{owner_id}",
            reward_type,
            expires_at
        )
        await grant_entitlement(db, owner_id, reward_type)
        invalidate_cache(owner_id)
        label   = ITEM_LABELS.get(reward_type, reward_type)
        message = f"🎉 <b>{label}</b> unlocked for {reward_days} days!"

    # Record redemption
    await db.execute(
        "INSERT INTO promo_redemptions (code_id, owner_id) VALUES ($1,$2)",
        promo["id"], owner_id
    )
    await db.execute(
        "UPDATE promo_codes SET current_uses=current_uses+1 WHERE id=$1",
        promo["id"]
    )
    await db.execute(
        """
        INSERT INTO payment_events (owner_id, event_type, item_type, stars_paid,
                                     metadata)
        VALUES ($1,'promo_redemption',$2,0,$3)
        """,
        owner_id, reward_feature or reward_type,
        {"code": code, "reward_type": reward_type}
    )

    log.info(f"[ECONOMY] Promo redeemed | owner={owner_id} code={code} reward={reward_type}")
    return {
        "ok":           True,
        "message":      message,
        "reward_type":  reward_type,
        "reward_value": reward_value,
    }


async def create_promo_code(
    db,
    created_by: int,
    code: str,
    reward_type: str,
    reward_value: int = 0,
    reward_feature: str = "",
    reward_days: int = 30,
    max_uses: int = 1,
    expires_days: int = 0,
) -> dict:
    """
    Create a new promo code. Admin only.
    Returns { ok, code } or { ok: False, error }
    """
    code = code.strip().upper()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_days)
        if expires_days else None
    )
    try:
        await db.execute(
            """
            INSERT INTO promo_codes
                (code, reward_type, reward_value, reward_feature,
                 reward_days, max_uses, expires_at, created_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            code, reward_type, reward_value, reward_feature,
            reward_days, max_uses, expires_at, created_by
        )
        log.info(f"[ECONOMY] Promo created | code={code} type={reward_type} by={created_by}")
        return {"ok": True, "code": code}
    except Exception as e:
        if "unique" in str(e).lower():
            return {"ok": False, "error": "Code already exists."}
        return {"ok": False, "error": str(e)}
