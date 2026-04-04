"""
bot/engagement/community_economy.py

Community Economy System - Per-group virtual currency and shop.

Every Telegram group can have its own virtual economy:
- Currency: Groups can have custom-named currency (coins, gems, points, etc.)
- Earning: Users earn through messages, daily checkin, quests, admin grants
- Spending: Group shop with items like roles, badges, XP boosts, features
- Quests: Scheduled tasks for users to complete (post X messages, invite friends, etc.)
- Leaderboards: Top earners/spenders in the group

Economy is powered by Telegram Stars under the hood:
- Groups can optionally accept Stars payments to convert to group currency
- Admins can set exchange rates
- Creates monetization opportunities for group owners
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("community_economy")

DEFAULT_CURRENCY_NAME = "coins"
DEFAULT_CURRENCY_SYMBOL = "🪙"


async def get_group_economy_config(pool, chat_id: int, bot_id: int) -> dict:
    """
    Get economy configuration for a group.
    Returns config with currency_name, currency_symbol, enabled status, etc.
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT currency_name, currency_symbol, enabled, xp_to_currency_rate,
                       stars_exchange_rate, daily_bonus, min_tip
                FROM community_economy_config
                WHERE chat_id = $1 AND bot_id = $2
                """,
                chat_id,
                bot_id,
            )
            
            if row:
                return {
                    "currency_name": row["currency_name"] or DEFAULT_CURRENCY_NAME,
                    "currency_symbol": row["currency_symbol"] or DEFAULT_CURRENCY_SYMBOL,
                    "enabled": row["enabled"] or False,
                    "xp_to_currency_rate": row["xp_to_currency_rate"] or 1,
                    "stars_exchange_rate": row["stars_exchange_rate"] or 100,
                    "daily_bonus": row["daily_bonus"] or 10,
                    "min_tip": row["min_tip"] or 1,
                }
            
            # Return defaults
            return {
                "currency_name": DEFAULT_CURRENCY_NAME,
                "currency_symbol": DEFAULT_CURRENCY_SYMBOL,
                "enabled": False,
                "xp_to_currency_rate": 1,
                "stars_exchange_rate": 100,
                "daily_bonus": 10,
                "min_tip": 1,
            }
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error getting config: {e}")
        return {
            "currency_name": DEFAULT_CURRENCY_NAME,
            "currency_symbol": DEFAULT_CURRENCY_SYMBOL,
            "enabled": False,
        }


async def set_group_economy_config(
    pool,
    chat_id: int,
    bot_id: int,
    currency_name: str,
    currency_symbol: str,
    enabled: bool = True,
    daily_bonus: int = 10,
) -> dict:
    """
    Configure economy for a group.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO community_economy_config
                    (chat_id, bot_id, currency_name, currency_symbol, enabled, daily_bonus)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (chat_id, bot_id) DO UPDATE SET
                    currency_name = $3,
                    currency_symbol = $4,
                    enabled = $5,
                    daily_bonus = $6
                """,
                chat_id,
                bot_id,
                currency_name,
                currency_symbol,
                enabled,
                daily_bonus,
            )
            
        return {"ok": True}
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error setting config: {e}")
        return {"ok": False, "error": str(e)}


async def get_user_balance(pool, chat_id: int, user_id: int, bot_id: int) -> int:
    """
    Get user's currency balance in a group.
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT balance FROM community_currency
                WHERE chat_id = $1 AND user_id = $2 AND bot_id = $3
                """,
                chat_id,
                user_id,
                bot_id,
            )
            return row["balance"] if row else 0
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error getting balance: {e}")
        return 0


async def add_currency(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
    amount: int,
    reason: str,
) -> int:
    """
    Add currency to a user's balance.
    Returns new balance.
    """
    try:
        async with pool.acquire() as conn:
            # Update balance
            await conn.execute(
                """
                INSERT INTO community_currency (chat_id, user_id, bot_id, balance)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (chat_id, user_id, bot_id) DO UPDATE SET
                    balance = community_currency.balance + $4
                """,
                chat_id,
                user_id,
                bot_id,
                amount,
            )
            
            # Log transaction
            await conn.execute(
                """
                INSERT INTO community_transactions
                    (chat_id, user_id, bot_id, amount, transaction_type, note)
                VALUES ($1, $2, $3, $4, 'earn', $5)
                """,
                chat_id,
                user_id,
                bot_id,
                amount,
                reason,
            )
            
            # Get new balance
            row = await conn.fetchrow(
                "SELECT balance FROM community_currency WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3",
                chat_id,
                user_id,
                bot_id,
            )
            return row["balance"] if row else amount
            
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error adding currency: {e}")
        return 0


async def spend_currency(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
    amount: int,
    reason: str,
) -> dict:
    """
    Spend currency from user's balance.
    Returns {ok, new_balance, error}
    """
    current = await get_user_balance(pool, chat_id, user_id, bot_id)
    
    if current < amount:
        return {
            "ok": False,
            "new_balance": current,
            "error": f"Insufficient balance. Need {amount}, have {current}.",
        }
    
    try:
        async with pool.acquire() as conn:
            # Deduct balance
            await conn.execute(
                """
                UPDATE community_currency
                SET balance = balance - $4
                WHERE chat_id = $1 AND user_id = $2 AND bot_id = $3
                """,
                chat_id,
                user_id,
                bot_id,
                amount,
            )
            
            # Log transaction
            await conn.execute(
                """
                INSERT INTO community_transactions
                    (chat_id, user_id, bot_id, amount, transaction_type, note)
                VALUES ($1, $2, $3, $4, 'spend', $5)
                """,
                chat_id,
                user_id,
                bot_id,
                -amount,
                reason,
            )
            
            new_balance = current - amount
            
        return {"ok": True, "new_balance": new_balance}
        
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error spending currency: {e}")
        return {"ok": False, "error": str(e)}


async def get_shop_items(pool, chat_id: int, bot_id: int) -> list[dict]:
    """
    Get available shop items for a group.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, description, price, item_type, item_value, emoji, is_active
                FROM community_shop_items
                WHERE chat_id = $1 AND bot_id = $2 AND is_active = TRUE
                ORDER BY price ASC
                """,
                chat_id,
                bot_id,
            )
            
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "price": row["price"],
                    "type": row["item_type"],
                    "value": row["item_value"],
                    "emoji": row["emoji"],
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error getting shop items: {e}")
        return []


async def add_shop_item(
    pool,
    chat_id: int,
    bot_id: int,
    name: str,
    description: str,
    price: int,
    item_type: str,
    item_value: str,
    emoji: str = "🎁",
) -> dict:
    """
    Add an item to the group shop.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO community_shop_items
                    (chat_id, bot_id, name, description, price, item_type, item_value, emoji)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                chat_id,
                bot_id,
                name,
                description,
                price,
                item_type,
                item_value,
                emoji,
            )
            
        return {"ok": True}
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error adding shop item: {e}")
        return {"ok": False, "error": str(e)}


async def purchase_item(
    pool,
    chat_id: int,
    user_id: int,
    bot_id: int,
    item_id: int,
) -> dict:
    """
    User purchases an item from the shop.
    """
    try:
        async with pool.acquire() as conn:
            # Get item
            item = await conn.fetchrow(
                """
                SELECT name, price, item_type, item_value, emoji
                FROM community_shop_items
                WHERE id = $1 AND chat_id = $2 AND bot_id = $3 AND is_active = TRUE
                """,
                item_id,
                chat_id,
                bot_id,
            )
            
            if not item:
                return {"ok": False, "error": "Item not found"}
            
            price = item["price"]
            
            # Check balance
            row = await conn.fetchrow(
                "SELECT balance FROM community_currency WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3",
                chat_id,
                user_id,
                bot_id,
            )
            current_balance = row["balance"] if row else 0
            
            if current_balance < price:
                return {
                    "ok": False,
                    "error": f"Insufficient balance. Need {price}, have {current_balance}.",
                }
            
            # Deduct and log
            await conn.execute(
                """
                UPDATE community_currency
                SET balance = balance - $4
                WHERE chat_id = $1 AND user_id = $2 AND bot_id = $3
                """,
                chat_id,
                user_id,
                bot_id,
                price,
            )
            
            await conn.execute(
                """
                INSERT INTO community_transactions
                    (chat_id, user_id, bot_id, amount, transaction_type, note)
                VALUES ($1, $2, $3, $4, 'spend', $5)
                """,
                chat_id,
                user_id,
                bot_id,
                -price,
                f"purchase:{item['name']}",
            )
            
            # Grant the item (based on item_type)
            if item["item_type"] == "role":
                # Would need to integrate with roles system
                pass
            elif item["item_type"] == "badge":
                # Grant badge
                pass
            elif item["item_type"] == "xp_boost":
                # Grant XP boost
                pass
                
        return {
            "ok": True,
            "item_name": item["name"],
            "price": price,
            "item_type": item["item_type"],
        }
        
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error purchasing item: {e}")
        return {"ok": False, "error": str(e)}


async def get_economy_leaderboard(pool, chat_id: int, bot_id: int, limit: int = 10) -> list[dict]:
    """
    Get richest users in the group.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, balance FROM community_currency
                WHERE chat_id = $1 AND bot_id = $2
                ORDER BY balance DESC
                LIMIT $3
                """,
                chat_id,
                bot_id,
                limit,
            )
            
            return [
                {"user_id": row["user_id"], "balance": row["balance"]}
                for row in rows
            ]
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error getting leaderboard: {e}")
        return []


async def claim_daily_bonus(pool, chat_id: int, user_id: int, bot_id: int) -> dict:
    """
    User claims daily bonus (once per day).
    """
    try:
        async with pool.acquire() as conn:
            # Check if already claimed today
            today = datetime.now(timezone.utc).date()
            row = await conn.fetchrow(
                """
                SELECT last_daily_claim FROM community_currency
                WHERE chat_id = $1 AND user_id = $2 AND bot_id = $3
                """,
                chat_id,
                user_id,
                bot_id,
            )
            
            if row and row["last_daily_claim"]:
                last_claim = row["last_daily_claim"].date() if isinstance(row["last_daily_claim"], datetime) else row["last_daily_claim"]
                if last_claim == today:
                    return {"ok": False, "error": "Already claimed daily bonus today!"}
            
            # Get bonus amount
            config = await get_group_economy_config(pool, chat_id, bot_id)
            bonus = config.get("daily_bonus", 10)
            
            # Add bonus
            await conn.execute(
                """
                INSERT INTO community_currency (chat_id, user_id, bot_id, balance, last_daily_claim)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (chat_id, user_id, bot_id) DO UPDATE SET
                    balance = community_currency.balance + $4,
                    last_daily_claim = NOW()
                """,
                chat_id,
                user_id,
                bot_id,
                bonus,
            )
            
            # Log
            await conn.execute(
                """
                INSERT INTO community_transactions
                    (chat_id, user_id, bot_id, amount, transaction_type, note)
                VALUES ($1, $2, $3, $4, 'earn', 'daily_bonus')
                """,
                chat_id,
                user_id,
                bot_id,
                bonus,
            )
            
        return {"ok": True, "bonus": bonus}
        
    except Exception as e:
        logger.error(f"[COMMUNITY_ECONOMY] Error claiming daily bonus: {e}")
        return {"ok": False, "error": str(e)}
