"""
db/ops/notes.py

Database operations for the notes system.
"""

import logging
from typing import Optional

log = logging.getLogger("[DB_NOTES]")


async def get_notes(pool, chat_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM notes WHERE chat_id = $1 ORDER BY name ASC",
            chat_id,
        )
    return [dict(r) for r in rows]


async def get_note(pool, chat_id: int, name: str) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM notes WHERE chat_id = $1 AND name = $2",
            chat_id, name.lower(),
        )
    return dict(row) if row else None


async def save_note(
    pool,
    chat_id: int,
    name: str,
    content: Optional[str],
    file_id: Optional[str],
    media_type: Optional[str],
    buttons: list,
    added_by: int,
) -> dict:
    import json
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO notes (chat_id, name, content, file_id, media_type, buttons, added_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               ON CONFLICT (chat_id, name) DO UPDATE
               SET content = EXCLUDED.content,
                   file_id = EXCLUDED.file_id,
                   media_type = EXCLUDED.media_type,
                   buttons = EXCLUDED.buttons,
                   added_by = EXCLUDED.added_by,
                   added_at = NOW()
               RETURNING *""",
            chat_id, name.lower(), content, file_id, media_type,
            json.dumps(buttons) if buttons else "[]",
            added_by,
        )
    return dict(row)


async def delete_note(pool, chat_id: int, name: str) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM notes WHERE chat_id = $1 AND name = $2",
            chat_id, name.lower(),
        )
    return "DELETE 1" in result
