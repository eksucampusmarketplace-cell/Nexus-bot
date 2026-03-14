"""
Database operations for webhook system.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from db.client import db


async def create_webhook(
    chat_id: int,
    name: str,
    url: str,
    events: List[str],
    secret: Optional[str] = None,
    created_by: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a new webhook configuration."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO webhook_configs (chat_id, name, url, events, secret, created_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (chat_id, name) DO UPDATE
            SET url = EXCLUDED.url,
                events = EXCLUDED.events,
                secret = EXCLUDED.secret,
                is_active = TRUE,
                updated_at = NOW()
            RETURNING *
            """,
            chat_id,
            name,
            url,
            events,
            secret,
            created_by,
        )
        return dict(row) if row else None


async def get_webhooks(chat_id: int) -> List[Dict[str, Any]]:
    """Get all webhooks for a group."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, chat_id, name, url, events, is_active, created_at, updated_at,
                   retry_count, last_error, last_triggered_at
            FROM webhook_configs
            WHERE chat_id = $1
            ORDER BY created_at DESC
            """,
            chat_id,
        )
        return [dict(r) for r in rows]


async def get_active_webhooks_for_event(chat_id: int, event_type: str) -> List[Dict[str, Any]]:
    """Get all active webhooks subscribed to a specific event."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, chat_id, name, url, secret, events
            FROM webhook_configs
            WHERE chat_id = $1
              AND is_active = TRUE
              AND ($2 = ANY(events) OR 'all' = ANY(events))
            """,
            chat_id,
            event_type,
        )
        return [dict(r) for r in rows]


async def get_webhook_by_id(webhook_id: int) -> Optional[Dict[str, Any]]:
    """Get a single webhook by ID."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM webhook_configs WHERE id = $1", webhook_id)
        return dict(row) if row else None


async def update_webhook(
    webhook_id: int,
    name: Optional[str] = None,
    url: Optional[str] = None,
    events: Optional[List[str]] = None,
    secret: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Update webhook configuration."""
    updates = []
    params = [webhook_id]
    param_idx = 2

    if name is not None:
        updates.append(f"name = ${param_idx}")
        params.append(name)
        param_idx += 1
    if url is not None:
        updates.append(f"url = ${param_idx}")
        params.append(url)
        param_idx += 1
    if events is not None:
        updates.append(f"events = ${param_idx}")
        params.append(events)
        param_idx += 1
    if secret is not None:
        updates.append(f"secret = ${param_idx}")
        params.append(secret)
        param_idx += 1
    if is_active is not None:
        updates.append(f"is_active = ${param_idx}")
        params.append(is_active)
        param_idx += 1

    if not updates:
        return await get_webhook_by_id(webhook_id)

    updates.append("updated_at = NOW()")

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE webhook_configs
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING *
            """,
            *params,
        )
        return dict(row) if row else None


async def delete_webhook(webhook_id: int) -> bool:
    """Delete a webhook configuration."""
    async with db.pool.acquire() as conn:
        result = await conn.execute("DELETE FROM webhook_configs WHERE id = $1", webhook_id)
        return result != "DELETE 0"


async def log_webhook_delivery(
    webhook_id: int,
    event_type: str,
    payload: Dict[str, Any],
    success: bool,
    response_status: Optional[int] = None,
    response_body: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Log a webhook delivery attempt."""
    async with db.pool.acquire() as conn:
        # Insert delivery log
        await conn.execute(
            """
            INSERT INTO webhook_deliveries 
            (webhook_id, event_type, payload, success, response_status, response_body, delivery_duration_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            webhook_id,
            event_type,
            json.dumps(payload),
            success,
            response_status,
            response_body,
            duration_ms,
        )

        # Update webhook stats
        await conn.execute(
            """
            UPDATE webhook_configs
            SET last_triggered_at = NOW(),
                retry_count = CASE WHEN $2 THEN retry_count ELSE retry_count + 1 END,
                last_error = CASE WHEN $2 THEN NULL ELSE $3 END
            WHERE id = $1
            """,
            webhook_id,
            success,
            response_body[:500] if response_body and not success else None,
        )


async def get_webhook_deliveries(webhook_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get delivery history for a webhook."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, event_type, success, response_status, delivery_duration_ms, created_at
            FROM webhook_deliveries
            WHERE webhook_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            webhook_id,
            limit,
        )
        return [dict(r) for r in rows]


async def get_chat_webhook_stats(chat_id: int) -> Dict[str, Any]:
    """Get webhook statistics for a group."""
    async with db.pool.acquire() as conn:
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) FILTER (WHERE is_active) as active_count,
                COUNT(*) FILTER (WHERE NOT is_active) as inactive_count,
                COUNT(*) as total_count
            FROM webhook_configs
            WHERE chat_id = $1
            """,
            chat_id,
        )

        recent_deliveries = await conn.fetchval(
            """
            SELECT COUNT(*) 
            FROM webhook_deliveries wd
            JOIN webhook_configs wc ON wd.webhook_id = wc.id
            WHERE wc.chat_id = $1 AND wd.created_at > NOW() - INTERVAL '24 hours'
            """,
            chat_id,
        )

        return {
            "active": stats["active_count"] or 0,
            "inactive": stats["inactive_count"] or 0,
            "total": stats["total_count"] or 0,
            "deliveries_24h": recent_deliveries or 0,
        }
