"""
Security Logger Module

Logs security events to the database for monitoring and analysis.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from db.client import db

log = logging.getLogger(__name__)


async def log_security_event(
    event_type: str,
    severity: str,
    user_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    endpoint: Optional[str] = None,
    input_data: Optional[str] = None,
    pattern_matched: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """
    Log a security event to the database.
    
    Args:
        event_type: Type of security event ('sql_injection', 'xss', 'spam', 'rate_limit', etc.)
        severity: Severity level ('low', 'medium', 'high', 'critical')
        user_id: Telegram user ID if available
        chat_id: Chat ID if applicable
        ip_address: Client IP address
        endpoint: API endpoint or bot command
        input_data: Sanitized input sample
        pattern_matched: Pattern that triggered the event
        additional_info: Extra details as dictionary
    
    Returns:
        int: ID of inserted record, or None if failed
    """
    if not db.pool:
        return None
    
    try:
        # Truncate input_data to avoid storing too much data
        if input_data and len(input_data) > 500:
            input_data = input_data[:500] + '...'
        
        # Convert additional_info to JSON
        info_json = json.dumps(additional_info) if additional_info else None
        
        async with db.pool.acquire() as conn:
            event_id = await conn.fetchval(
                """INSERT INTO security_events
                   (event_type, severity, user_id, chat_id, ip_address, endpoint,
                    input_data, pattern_matched, additional_info)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   RETURNING id""",
                event_type,
                severity,
                user_id,
                chat_id,
                ip_address,
                endpoint,
                input_data,
                pattern_matched,
                info_json
            )
        
        log.info(
            f"[SECURITY_LOG] Event logged: {event_type} | severity={severity} | "
            f"user_id={user_id} | chat_id={chat_id} | endpoint={endpoint}"
        )
        
        return event_id
    
    except Exception as e:
        log.error(f"[SECURITY_LOG] Failed to log security event: {e}")
        return None


async def get_security_events(
    user_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> list:
    """
    Retrieve security events from database.
    
    Args:
        user_id: Filter by user ID
        chat_id: Filter by chat ID
        event_type: Filter by event type
        severity: Filter by severity
        limit: Maximum number of records to return
        offset: Offset for pagination
    
    Returns:
        list: List of security event dictionaries
    """
    if not db.pool:
        return []
    
    try:
        conditions = []
        params = []
        param_count = 1
        
        if user_id:
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)
            param_count += 1
        
        if chat_id:
            conditions.append(f"chat_id = ${param_count}")
            params.append(chat_id)
            param_count += 1
        
        if event_type:
            conditions.append(f"event_type = ${param_count}")
            params.append(event_type)
            param_count += 1
        
        if severity:
            conditions.append(f"severity = ${param_count}")
            params.append(severity)
            param_count += 1
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        params.extend([limit, offset])
        
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM security_events
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${param_count} OFFSET ${param_count + 1}""",
                *params
            )
        
        return [dict(row) for row in rows]
    
    except Exception as e:
        log.error(f"[SECURITY_LOG] Failed to retrieve security events: {e}")
        return []


async def get_user_violation_count(
    user_id: int,
    hours: int = 24
) -> int:
    """
    Get count of security violations for a user in the last N hours.
    
    Args:
        user_id: Telegram user ID
        hours: Number of hours to look back
    
    Returns:
        int: Number of violations
    """
    if not db.pool:
        return 0
    
    try:
        async with db.pool.acquire() as conn:
            count = await conn.fetchval(
                """SELECT COUNT(*) FROM security_events
                   WHERE user_id = $1
                   AND created_at > NOW() - INTERVAL '1 hour' * $2""",
                user_id, hours
            )
        
        return count
    
    except Exception as e:
        log.error(f"[SECURITY_LOG] Failed to get user violation count: {e}")
        return 0


async def block_user(
    user_id: int,
    chat_id: Optional[int] = None,
    blocked_by: Optional[int] = None,
    reason: Optional[str] = None,
    block_type: str = 'temporary',
    duration_hours: Optional[int] = 24
) -> Optional[int]:
    """
    Block a user in the database.
    
    Args:
        user_id: Telegram user ID to block
        chat_id: Chat ID (0 for global block)
        blocked_by: Admin who blocked the user
        reason: Reason for blocking
        block_type: Type of block ('temporary', 'permanent', 'auto')
        duration_hours: Duration in hours (only for temporary blocks)
    
    Returns:
        int: ID of inserted record, or None if failed
    """
    if not db.pool:
        return None
    
    try:
        from datetime import timedelta
        
        expires_at = None
        if block_type == 'temporary' and duration_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        
        # Get current violation count
        violation_count = await get_user_violation_count(user_id, 24)
        
        additional_info = {
            'previous_violations': violation_count,
            'duration_hours': duration_hours
        }
        
        async with db.pool.acquire() as conn:
            block_id = await conn.fetchval(
                """INSERT INTO blocked_users
                   (user_id, chat_id, blocked_by, reason, block_type,
                    expires_at, violation_count, additional_info)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (user_id, chat_id) DO UPDATE SET
                       blocked_by = EXCLUDED.blocked_by,
                       reason = EXCLUDED.reason,
                       block_type = EXCLUDED.block_type,
                       expires_at = EXCLUDED.expires_at,
                       violation_count = EXCLUDED.violation_count + 1,
                       additional_info = EXCLUDED.additional_info,
                       blocked_at = NOW()
                   RETURNING id""",
                user_id,
                chat_id or 0,
                blocked_by,
                reason,
                block_type,
                expires_at,
                violation_count,
                json.dumps(additional_info)
            )
        
        log.info(
            f"[SECURITY] User blocked: user_id={user_id} | "
            f"chat_id={chat_id} | type={block_type} | reason={reason}"
        )
        
        return block_id
    
    except Exception as e:
        log.error(f"[SECURITY] Failed to block user: {e}")
        return None


async def is_user_blocked(
    user_id: int,
    chat_id: Optional[int] = None
) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if a user is blocked.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID to check (None to check any)
    
    Returns:
        tuple: (is_blocked, block_info)
    """
    if not db.pool:
        return False, None
    
    try:
        async with db.pool.acquire() as conn:
            # Check for global block or chat-specific block
            if chat_id:
                row = await conn.fetchrow(
                    """SELECT * FROM blocked_users
                       WHERE user_id = $1
                       AND (chat_id = 0 OR chat_id = $2)
                       AND (expires_at IS NULL OR expires_at > NOW())
                       ORDER BY expires_at DESC NULLS LAST
                       LIMIT 1""",
                    user_id, chat_id
                )
            else:
                row = await conn.fetchrow(
                    """SELECT * FROM blocked_users
                       WHERE user_id = $1
                       AND (expires_at IS NULL OR expires_at > NOW())
                       ORDER BY expires_at DESC NULLS LAST
                       LIMIT 1""",
                    user_id
                )
        
        if row:
            return True, dict(row)
        
        return False, None
    
    except Exception as e:
        log.error(f"[SECURITY] Failed to check if user is blocked: {e}")
        return False, None


async def unblock_user(
    user_id: int,
    chat_id: Optional[int] = None
) -> bool:
    """
    Unblock a user.
    
    Args:
        user_id: Telegram user ID
        chat_id: Chat ID (None to unblock from all)
    
    Returns:
        bool: Success status
    """
    if not db.pool:
        return False
    
    try:
        async with db.pool.acquire() as conn:
            if chat_id:
                await conn.execute(
                    """DELETE FROM blocked_users
                       WHERE user_id = $1 AND chat_id = $2""",
                    user_id, chat_id
                )
            else:
                await conn.execute(
                    """DELETE FROM blocked_users
                       WHERE user_id = $1""",
                    user_id
                )
        
        log.info(f"[SECURITY] User unblocked: user_id={user_id} | chat_id={chat_id}")
        return True
    
    except Exception as e:
        log.error(f"[SECURITY] Failed to unblock user: {e}")
        return False


async def cleanup_old_events() -> int:
    """
    Clean up security events older than 90 days.
    
    Returns:
        int: Number of records deleted
    """
    if not db.pool:
        return 0
    
    try:
        async with db.pool.acquire() as conn:
            result = await conn.execute(
                "SELECT cleanup_old_security_events()"
            )
        
        # Result is in format "DELETE n"
        deleted = int(result.split()[1]) if result else 0
        
        if deleted > 0:
            log.info(f"[SECURITY] Cleaned up {deleted} old security events")
        
        return deleted
    
    except Exception as e:
        log.error(f"[SECURITY] Failed to cleanup old events: {e}")
        return 0
