"""
bot/billing/entitlements.py

Manages feature entitlements and purchases via Telegram Stars.
Caches active purchases in memory per owner.

Features can be:
  - One-time unlocks (e.g., extra group slot)
  - Time-based subscriptions (e.g., music player for 30 days)

Logs prefix: [ENTITLEMENT]
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from functools import lru_cache

from config import settings

log = logging.getLogger("entitlements")


# ── PRICING & LABELS ─────────────────────────────────────────────────────────

STARS_PRICES = {
    "feat_music": 100,
    "feat_autojoin": 50,
    "feat_analytics": 200,
    "feat_webhooks": 150,
    "group_slot": 500,
    "clone_slot": 1000,
}

ITEM_LABELS = {
    "feat_music": "Music Player",
    "feat_autojoin": "Auto Join",
    "feat_analytics": "Analytics",
    "feat_webhooks": "Webhooks",
    "group_slot": "Additional Group Slot",
    "clone_slot": "Additional Clone Slot",
}


# ── IN-MEMORY CACHE ───────────────────────────────────────────────────────────

# owner_id -> { item_type: expires_at }
_entitlement_cache: Dict[int, Dict[str, datetime]] = {}


def _get_cache(owner_id: int) -> Dict[str, datetime]:
    """Get or create entitlement cache for owner."""
    if owner_id not in _entitlement_cache:
        _entitlement_cache[owner_id] = {}
    return _entitlement_cache[owner_id]


def invalidate_cache(owner_id: int):
    """Clear entitlement cache for owner (call after purchase)."""
    if owner_id in _entitlement_cache:
        del _entitlement_cache[owner_id]
        log.debug(f"[ENTITLEMENT] Cache invalidated | owner={owner_id}")


# ── ENTITLEMENT CHECKS ───────────────────────────────────────────────────────


async def has_entitlement(db, owner_id: int, item_type: str) -> bool:
    """
    Check if owner has active entitlement for item_type.
    Uses in-memory cache with DB fallback.
    """
    cache = _get_cache(owner_id)
    now = datetime.now(timezone.utc)

    # Check cache first
    if item_type in cache:
        if cache[item_type] > now:
            return True
        else:
            # Expired, remove from cache
            del cache[item_type]

    # Fallback to DB
    row = await db.fetchrow(
        """
        SELECT MAX(expires_at) as expires_at
        FROM stars_purchases
        WHERE owner_id=$1 AND item_type=$2 AND expires_at > NOW()
        """,
        owner_id,
        item_type,
    )

    if row and row["expires_at"]:
        cache[item_type] = row["expires_at"]
        return True

    return False


async def get_entitlement_expiry(db, owner_id: int, item_type: str) -> Optional[datetime]:
    """Get expiry date for an entitlement, or None if not active."""
    cache = _get_cache(owner_id)
    now = datetime.now(timezone.utc)

    if item_type in cache:
        if cache[item_type] > now:
            return cache[item_type]
        else:
            del cache[item_type]

    row = await db.fetchrow(
        """
        SELECT MAX(expires_at) as expires_at
        FROM stars_purchases
        WHERE owner_id=$1 AND item_type=$2 AND expires_at > NOW()
        """,
        owner_id,
        item_type,
    )

    if row and row["expires_at"]:
        cache[item_type] = row["expires_at"]
        return row["expires_at"]

    return None


# ── ENTITLEMENT GRANTING ─────────────────────────────────────────────────────


async def grant_entitlement(db, owner_id: int, item_type: str, days: int = 30):
    """
    Grant or extend an entitlement for owner.
    Creates/extends a stars_purchases record.
    """
    from datetime import timedelta

    # Calculate expiry (extend from current expiry if exists)
    current = await get_entitlement_expiry(db, owner_id, item_type)
    if current:
        expires_at = current + timedelta(days=days)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(days=days)

    # Insert purchase record
    await db.execute(
        """
        INSERT INTO stars_purchases
            (owner_id, telegram_charge_id, item_type, stars_paid, expires_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (telegram_charge_id) DO UPDATE
        SET expires_at = EXCLUDED.expires_at
        """,
        owner_id,
        f"grant_{item_type}_{owner_id}_{int(datetime.now(timezone.utc).timestamp())}",
        item_type,
        0,  # granted via bonus or admin
        expires_at,
    )

    # Update cache
    cache = _get_cache(owner_id)
    cache[item_type] = expires_at

    log.info(f"[ENTITLEMENT] Granted | owner={owner_id} item={item_type} expires={expires_at}")


async def revoke_entitlement(db, owner_id: int, item_type: str):
    """
    Revoke an entitlement immediately.
    Sets expiry to now in DB and clears cache.
    """
    await db.execute(
        """
        UPDATE stars_purchases
        SET expires_at = NOW()
        WHERE owner_id=$1 AND item_type=$2 AND expires_at > NOW()
        """,
        owner_id,
        item_type,
    )

    invalidate_cache(owner_id)
    log.info(f"[ENTITLEMENT] Revoked | owner={owner_id} item={item_type}")


# ── UTILITIES ────────────────────────────────────────────────────────────────


async def get_all_entitlements(db, owner_id: int) -> Dict[str, datetime]:
    """Get all active entitlements for owner."""
    rows = await db.fetch(
        """
        SELECT item_type, MAX(expires_at) as expires_at
        FROM stars_purchases
        WHERE owner_id=$1 AND expires_at > NOW()
        GROUP BY item_type
        """,
        owner_id,
    )

    result = {}
    for row in rows:
        result[row["item_type"]] = row["expires_at"]

    # Update cache
    _entitlement_cache[owner_id] = result
    return result


def get_price(item_type: str) -> int:
    """Get price in Stars for an item."""
    return STARS_PRICES.get(item_type, 0)


def get_label(item_type: str) -> str:
    """Get human-readable label for an item."""
    return ITEM_LABELS.get(item_type, item_type)
