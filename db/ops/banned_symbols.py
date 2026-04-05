"""
db/ops/banned_symbols.py

Database operations for banned symbols feature (UltraPro only).
Allows groups to ban users with specific symbols in their usernames.
"""

from db.client import db


async def get_banned_symbols(chat_id: int) -> list:
    """Get all banned symbols for a chat."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT symbol, action FROM banned_symbols WHERE chat_id = $1",
            chat_id,
        )
    return [{"symbol": row["symbol"], "action": row["action"]} for row in rows]


async def add_banned_symbol(chat_id: int, symbol: str, added_by: int, action: str = "ban"):
    """Add a banned symbol to a chat."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO banned_symbols (chat_id, symbol, action, added_by)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (chat_id, symbol) DO UPDATE
            SET action = EXCLUDED.action, added_by = EXCLUDED.added_by
            """,
            chat_id, symbol, action, added_by
        )


async def remove_banned_symbol(chat_id: int, symbol: str) -> bool:
    """Remove a banned symbol from a chat. Returns True if deleted."""
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM banned_symbols WHERE chat_id = $1 AND symbol = $2",
            chat_id, symbol
        )
        return "DELETE 1" in result


async def clear_banned_symbols(chat_id: int):
    """Remove all banned symbols from a chat."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM banned_symbols WHERE chat_id = $1",
            chat_id
        )


async def log_banned_symbol_match(chat_id: int, user_id: int, username: str, matched_symbol: str, action_taken: str):
    """Log when a user's username matches a banned symbol."""
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO banned_symbol_matches
            (chat_id, user_id, username, matched_symbol, action_taken)
            VALUES ($1, $2, $3, $4, $5)
            """,
            chat_id, user_id, username, matched_symbol, action_taken
        )


async def check_username_against_symbols(chat_id: int, username: str) -> dict | None:
    """
    Check if a username contains any banned symbols.
    Returns the first match found with its action, or None if no match.
    """
    if not username:
        return None

    symbols = await get_banned_symbols(chat_id)
    if not symbols:
        return None

    for item in symbols:
        symbol = item["symbol"]
        if symbol in username:
            return {"symbol": symbol, "action": item["action"]}

    return None
