"""
api/routes/economy.py

API endpoints for Community Economy system.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from db.client import db

router = APIRouter(prefix="/api/economy", tags=["economy"])


class EconomyConfigResponse(BaseModel):
    currency_name: str
    currency_symbol: str
    enabled: bool
    daily_bonus: int


class BalanceResponse(BaseModel):
    user_id: int
    balance: int


class ShopItemResponse(BaseModel):
    id: int
    name: str
    description: str
    price: int
    type: str
    value: str
    emoji: str


class LeaderboardResponse(BaseModel):
    users: list[dict]


@router.get("/config/{chat_id}/{bot_id}", response_model=EconomyConfigResponse)
async def get_economy_config(chat_id: int, bot_id: int):
    """Get economy configuration for a group."""
    from bot.engagement.community_economy import get_group_economy_config

    config = await get_group_economy_config(db.pool, chat_id, bot_id)
    return config


@router.post("/config/{chat_id}/{bot_id}")
async def set_economy_config(
    chat_id: int,
    bot_id: int,
    currency_name: str,
    currency_symbol: str,
    enabled: bool = True,
    daily_bonus: int = 10,
):
    """Configure economy for a group (admin only in Mini App)."""
    from bot.engagement.community_economy import set_group_economy_config

    result = await set_group_economy_config(
        db.pool, chat_id, bot_id, currency_name, currency_symbol, enabled, daily_bonus
    )
    return result


@router.get("/balance/{chat_id}/{user_id}/{bot_id}", response_model=BalanceResponse)
async def get_balance(chat_id: int, user_id: int, bot_id: int):
    """Get user's currency balance in a group."""
    from bot.engagement.community_economy import get_user_balance

    balance = await get_user_balance(db.pool, chat_id, user_id, bot_id)
    return {"user_id": user_id, "balance": balance}


@router.get("/shop/{chat_id}/{bot_id}", response_model=list[ShopItemResponse])
async def get_shop_items(chat_id: int, bot_id: int):
    """Get shop items available in a group."""
    from bot.engagement.community_economy import get_shop_items

    items = await get_shop_items(db.pool, chat_id, bot_id)
    return items


@router.post("/shop/{chat_id}/{bot_id}/add")
async def add_shop_item(
    chat_id: int,
    bot_id: int,
    name: str,
    description: str,
    price: int,
    item_type: str,
    item_value: str,
    emoji: str = "🎁",
):
    """Add an item to the group shop (admin only)."""
    from bot.engagement.community_economy import add_shop_item

    result = await add_shop_item(
        db.pool, chat_id, bot_id, name, description, price, item_type, item_value, emoji
    )
    return result


@router.post("/purchase/{chat_id}/{user_id}/{bot_id}/{item_id}")
async def purchase_item(chat_id: int, user_id: int, bot_id: int, item_id: int):
    """Purchase an item from the shop."""
    from bot.engagement.community_economy import purchase_item

    result = await purchase_item(db.pool, chat_id, user_id, bot_id, item_id)
    return result


@router.get("/leaderboard/{chat_id}/{bot_id}", response_model=LeaderboardResponse)
async def get_economy_leaderboard(chat_id: int, bot_id: int, limit: int = 10):
    """Get richest users in the group."""
    from bot.engagement.community_economy import get_economy_leaderboard

    users = await get_economy_leaderboard(db.pool, chat_id, bot_id, limit)
    return {"users": users}


@router.post("/daily-bonus/{chat_id}/{user_id}/{bot_id}")
async def claim_daily_bonus(chat_id: int, user_id: int, bot_id: int):
    """Claim daily bonus."""
    from bot.engagement.community_economy import claim_daily_bonus

    result = await claim_daily_bonus(db.pool, chat_id, user_id, bot_id)
    return result