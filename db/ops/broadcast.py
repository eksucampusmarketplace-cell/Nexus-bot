import asyncpg
import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── PM Tracking ──────────────────────────────────────────────────────────────

async def upsert_pm(pool: asyncpg.Pool, bot_id: int, user_id: int, username: str = None, first_name: str = None):
    """Record that a user has PMed a specific bot."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_pms (bot_id, user_id, username, first_name, last_seen)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (bot_id, user_id) DO UPDATE
            SET username = COALESCE(EXCLUDED.username, bot_pms.username),
                first_name = COALESCE(EXCLUDED.first_name, bot_pms.first_name),
                last_seen = NOW()
        """, bot_id, user_id, username, first_name)

async def get_bot_pms_count(pool: asyncpg.Pool, bot_id: int) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM bot_pms WHERE bot_id = $1", bot_id)

async def get_bot_pms(pool: asyncpg.Pool, bot_id: int) -> List[int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM bot_pms WHERE bot_id = $1", bot_id)
        return [r['user_id'] for r in rows]

# ── Broadcast Tasks ─────────────────────────────────────────────────────────

async def create_broadcast_task(pool: asyncpg.Pool, task_data: dict) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO broadcast_tasks (
                owner_id, bot_id, target_type, content, media_file_id, media_type, status, total_targets
            ) VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
            RETURNING id
        """, 
        task_data['owner_id'], task_data['bot_id'], task_data['target_type'],
        task_data['content'], task_data.get('media_file_id'), task_data.get('media_type'),
        task_data.get('total_targets', 0))
        return row['id']

async def get_broadcast_task(pool: asyncpg.Pool, task_id: int) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM broadcast_tasks WHERE id = $1", task_id)
        return dict(row) if row else None

async def update_broadcast_progress(pool: asyncpg.Pool, task_id: int, sent_inc: int = 0, failed_inc: int = 0, status: str = None):
    async with pool.acquire() as conn:
        updates = ["updated_at = NOW()"]
        params = [task_id]
        idx = 2
        if sent_inc:
            updates.append(f"sent_count = sent_count + ${idx}")
            params.append(sent_inc)
            idx += 1
        if failed_inc:
            updates.append(f"failed_count = failed_count + ${idx}")
            params.append(failed_inc)
            idx += 1
        if status:
            updates.append(f"status = ${idx}")
            params.append(status)
            idx += 1
            if status in ('completed', 'failed', 'cancelled'):
                updates.append("finished_at = NOW()")
        
        query = f"UPDATE broadcast_tasks SET {', '.join(updates)} WHERE id = $1"
        await conn.execute(query, *params)

async def get_pending_broadcast_tasks(pool: asyncpg.Pool) -> List[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM broadcast_tasks WHERE status = 'pending' ORDER BY created_at ASC")
        return [dict(r) for r in rows]

async def get_active_broadcast_tasks(pool: asyncpg.Pool) -> List[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM broadcast_tasks WHERE status = 'running' ORDER BY created_at ASC")
        return [dict(r) for r in rows]

async def get_bot_broadcasts(pool: asyncpg.Pool, bot_id: int, limit: int = 10) -> List[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM broadcast_tasks 
            WHERE bot_id = $1 
            ORDER BY created_at DESC 
            LIMIT $2
        """, bot_id, limit)
        return [dict(r) for r in rows]

# ── Targets ──────────────────────────────────────────────────────────────────

async def get_broadcast_targets(pool: asyncpg.Pool, bot_id: int, target_type: str) -> List[int]:
    """Get list of chat_ids/user_ids for broadcast."""
    targets = []
    async with pool.acquire() as conn:
        if target_type in ('pms', 'all'):
            rows = await conn.fetch("SELECT user_id FROM bot_pms WHERE bot_id = $1", bot_id)
            targets.extend([r['user_id'] for r in rows])
        
        if target_type in ('groups', 'all'):
            # Use clone_bot_groups to find groups where this bot is active
            rows = await conn.fetch("""
                SELECT chat_id FROM clone_bot_groups 
                WHERE bot_id = $1 AND is_active = TRUE AND access_status = 'active'
            """, bot_id)
            targets.extend([r['chat_id'] for r in rows])
            
            # If it's the primary bot, also check groups where bot_token_hash matches
            # Primary bot usually doesn't have its token_hash in clone_bot_groups? 
            # Actually, the primary bot is also in the bots table.
            bot = await conn.fetchrow("SELECT token_hash, is_primary FROM bots WHERE bot_id = $1", bot_id)
            if bot and bot['is_primary']:
                rows = await conn.fetch("SELECT chat_id FROM groups WHERE bot_token_hash = $1", bot['token_hash'])
                group_ids = [r['chat_id'] for r in rows]
                # Avoid duplicates
                for gid in group_ids:
                    if gid not in targets:
                        targets.append(gid)
    
    return list(set(targets))
