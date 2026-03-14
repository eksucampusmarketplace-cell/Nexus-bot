from db.client import db


async def log_action(
    chat_id: int,
    action: str,
    target_user_id: int,
    target_username: str,
    by_user_id: int,
    by_username: str,
    reason: str,
    bot_token_hash: str,
):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO actions_log (chat_id, action, target_user_id, target_username, by_user_id, by_username, reason, bot_token_hash)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
            chat_id,
            action,
            target_user_id,
            target_username,
            by_user_id,
            by_username,
            reason,
            bot_token_hash,
        )


async def get_recent_logs(chat_id: int, limit: int = 50):
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM actions_log WHERE chat_id = $1 ORDER BY timestamp DESC LIMIT $2",
            chat_id,
            limit,
        )
        return [dict(row) for row in rows]
