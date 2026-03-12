"""
db/ops/approval.py
Database operations for the approval system.
"""

async def add_approved_member(db, chat_id: int, user_id: int, approved_by: int = None):
    await db.execute(
        """INSERT INTO approved_members (chat_id, user_id, approved_by)
           VALUES ($1, $2, $3)
           ON CONFLICT (chat_id, user_id) DO NOTHING""",
        chat_id, user_id, approved_by
    )

async def remove_approved_member(db, chat_id: int, user_id: int):
    await db.execute(
        "DELETE FROM approved_members WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )

async def get_approved_members(db, chat_id: int):
    # Joining with users table to get usernames if available
    return await db.fetch(
        """SELECT am.*, u.username 
           FROM approved_members am
           LEFT JOIN users u ON am.user_id = u.user_id AND am.chat_id = u.chat_id
           WHERE am.chat_id = $1
           ORDER BY am.approved_at DESC""",
        chat_id
    )

async def is_member_approved(db, chat_id: int, user_id: int) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM approved_members WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )
    return row is not None
