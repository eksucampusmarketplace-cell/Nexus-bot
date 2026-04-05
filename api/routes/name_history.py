"""
api/routes/name_history.py

Name history (Sangmata) API endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user, require_auth
from db.client import db

router = APIRouter(prefix="/api/groups/{chat_id}/name-history", tags=["name_history"])
logger = logging.getLogger(__name__)


class HistorySettings(BaseModel):
    enabled: bool = False
    limit: int = 10
    retention_days: int = 0  # F-06: retention period (0 = never purge)
    alert_enabled: bool = False
    alert_threshold: int = 1
    federation_sync: bool = False
    track_photos: bool = True


@router.get("")
async def get_history_settings(chat_id: int, user: dict = Depends(require_auth)):
    """Get name history settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT name_history_enabled, name_history_limit, name_history_retention_days,
                          settings->>'name_history_alert_enabled' as alert_enabled,
                          settings->>'name_history_alert_threshold' as alert_threshold,
                          settings->>'name_history_federation_sync' as federation_sync,
                          settings->>'name_history_track_photos' as track_photos
                   FROM groups WHERE chat_id = $1""",
                chat_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Group not found")

        # Parse boolean/numeric values from JSON strings
        def parse_bool(val, default=False):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            return str(val).lower() in ('true', '1', 'yes', 'on')

        def parse_int(val, default=0):
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        return {
            "enabled": row["name_history_enabled"] if row else False,
            "limit": row["name_history_limit"] if row else 10,
            "retention_days": row["name_history_retention_days"] if row else 0,
            "alert_enabled": parse_bool(row["alert_enabled"] if row else None, False),
            "alert_threshold": parse_int(row["alert_threshold"] if row else None, 1),
            "federation_sync": parse_bool(row["federation_sync"] if row else None, False),
            "track_photos": parse_bool(row["track_photos"] if row else None, True),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get history settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history settings")


@router.post("")
async def save_history_settings(
    chat_id: int, settings: HistorySettings, user: dict = Depends(require_auth)
):
    """Save name history settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            # Update main columns
            await conn.execute(
                """UPDATE groups 
                   SET name_history_enabled = $1, name_history_limit = $2,
                       name_history_retention_days = $3
                   WHERE chat_id = $4""",
                settings.enabled,
                settings.limit,
                settings.retention_days,
                chat_id,
            )
            
            # Update settings JSONB with alert and federation settings
            await conn.execute(
                """UPDATE groups 
                   SET settings = COALESCE(settings, '{}'::jsonb) || jsonb_build_object(
                       'name_history_alert_enabled', $1,
                       'name_history_alert_threshold', $2,
                       'name_history_federation_sync', $3,
                       'name_history_track_photos', $4
                   )
                   WHERE chat_id = $5""",
                settings.alert_enabled,
                settings.alert_threshold,
                settings.federation_sync,
                settings.track_photos,
                chat_id,
            )

        return {
            "ok": True, 
            "enabled": settings.enabled, 
            "limit": settings.limit, 
            "retention_days": settings.retention_days,
            "alert_enabled": settings.alert_enabled,
            "alert_threshold": settings.alert_threshold,
            "federation_sync": settings.federation_sync,
            "track_photos": settings.track_photos,
        }
    except Exception as e:
        logger.error(f"Failed to save history settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save history settings")


@router.get("/recent")
async def get_recent_name_changes(chat_id: int, user: dict = Depends(require_auth)):
    """Get recent name changes for a group."""
    try:
        async with db.pool.acquire() as conn:
            # Check if history tracking is enabled
            enabled = await conn.fetchval(
                "SELECT name_history_enabled FROM groups WHERE chat_id = $1", chat_id
            )

            if not enabled:
                return []

            # Get the configured limit (NH-03 fix: honor the configured limit, not hardcoded 20)
            limit_val = await conn.fetchval(
                "SELECT COALESCE(name_history_limit, 20) FROM groups WHERE chat_id = $1",
                chat_id,
            )
            
            # Check if federation sync is enabled
            federation_sync = await conn.fetchval(
                """SELECT COALESCE(settings->>'name_history_federation_sync', 'false')::boolean
                   FROM groups WHERE chat_id = $1""",
                chat_id
            )
            
            # Build query - include federated entries if sync is enabled
            if federation_sync:
                # Get all federations this group is in
                fed_ids = await conn.fetch(
                    "SELECT federation_id FROM federation_members WHERE chat_id = $1",
                    chat_id
                )
                fed_id_list = [f["federation_id"] for f in fed_ids]
                
                if fed_id_list:
                    # Get all groups in these federations
                    fed_groups = await conn.fetch(
                        "SELECT chat_id FROM federation_members WHERE federation_id = ANY($1)",
                        fed_id_list
                    )
                    fed_chat_ids = list(set([g["chat_id"] for g in fed_groups]))
                    
                    # Get recent name changes from all federation groups
                    rows = await conn.fetch(
                        """SELECT uhh.user_id,
                                  CASE
                                    WHEN uhh.last_name IS NOT NULL AND uhh.last_name != '' 
                                    THEN COALESCE(NULLIF(uhh.first_name,''), uhh.username, 'Unknown') || ' ' || uhh.last_name
                                    ELSE COALESCE(NULLIF(uhh.first_name,''), uhh.username, 'Unknown')
                                  END as user_name,
                                  CASE
                                    WHEN uhh.old_last_name IS NOT NULL AND uhh.old_last_name != '' 
                                    THEN COALESCE(uhh.old_first_name, '') || ' ' || COALESCE(uhh.old_last_name, '')
                                    ELSE COALESCE(uhh.old_first_name, '')
                                  END as old_name,
                                  uhh.old_username,
                                  uhh.username,
                                  uhh.changed_at,
                                  uhh.is_federated,
                                  uhh.source_chat_id,
                                  g.title as group_name
                           FROM user_name_history uhh
                           LEFT JOIN groups g ON g.chat_id = uhh.source_chat_id
                           WHERE uhh.source_chat_id = ANY($1)
                             AND (uhh.old_first_name IS NOT NULL OR uhh.old_username IS NOT NULL)
                           ORDER BY uhh.changed_at DESC
                           LIMIT $2""",
                        fed_chat_ids,
                        limit_val,
                    )
                else:
                    # No federations, just get this group's history
                    rows = await conn.fetch(
                        """SELECT uhh.user_id,
                                  CASE
                                    WHEN uhh.last_name IS NOT NULL AND uhh.last_name != '' 
                                    THEN COALESCE(NULLIF(uhh.first_name,''), uhh.username, 'Unknown') || ' ' || uhh.last_name
                                    ELSE COALESCE(NULLIF(uhh.first_name,''), uhh.username, 'Unknown')
                                  END as user_name,
                                  CASE
                                    WHEN uhh.old_last_name IS NOT NULL AND uhh.old_last_name != '' 
                                    THEN COALESCE(uhh.old_first_name, '') || ' ' || COALESCE(uhh.old_last_name, '')
                                    ELSE COALESCE(uhh.old_first_name, '')
                                  END as old_name,
                                  uhh.old_username,
                                  uhh.username,
                                  uhh.changed_at,
                                  uhh.is_federated,
                                  uhh.source_chat_id,
                                  g.title as group_name
                           FROM user_name_history uhh
                           LEFT JOIN groups g ON g.chat_id = uhh.source_chat_id
                           WHERE uhh.source_chat_id = $1
                             AND (uhh.old_first_name IS NOT NULL OR uhh.old_username IS NOT NULL)
                           ORDER BY uhh.changed_at DESC
                           LIMIT $2""",
                        chat_id,
                        limit_val,
                    )
            else:
                # Get recent name changes with proper old/new name fields (non-federated)
                # NH-03 fix: include username-only changes (WHERE old_first_name OR old_username)
                # NH-03 fix: use username as fallback when first_name is empty
                rows = await conn.fetch(
                    """SELECT uhh.user_id,
                              CASE
                                WHEN uhh.last_name IS NOT NULL AND uhh.last_name != '' 
                                THEN COALESCE(NULLIF(uhh.first_name,''), uhh.username, 'Unknown') || ' ' || uhh.last_name
                                ELSE COALESCE(NULLIF(uhh.first_name,''), uhh.username, 'Unknown')
                              END as user_name,
                              CASE
                                WHEN uhh.old_last_name IS NOT NULL AND uhh.old_last_name != '' 
                                THEN COALESCE(uhh.old_first_name, '') || ' ' || COALESCE(uhh.old_last_name, '')
                                ELSE COALESCE(uhh.old_first_name, '')
                              END as old_name,
                              uhh.old_username,
                              uhh.username,
                              uhh.changed_at,
                              uhh.is_federated,
                              uhh.source_chat_id,
                              g.title as group_name
                       FROM user_name_history uhh
                       LEFT JOIN groups g ON g.chat_id = uhh.source_chat_id
                       WHERE uhh.source_chat_id = $1
                         AND (uhh.old_first_name IS NOT NULL OR uhh.old_username IS NOT NULL)
                       ORDER BY uhh.changed_at DESC
                       LIMIT $2""",
                    chat_id,
                    limit_val,
                )

        return [
            {
                "user_id": r["user_id"],
                "user_name": r["user_name"] or r["username"] or "Unknown",
                "old_name": r["old_name"] or r["old_username"] or "",
                "changed_at": r["changed_at"].isoformat() if r["changed_at"] else None,
                "is_federated": r["is_federated"] or False,
                "source_chat_id": r["source_chat_id"],
                "group_name": r["group_name"] or f"Group {r['source_chat_id']}",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get recent name changes: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch name history")


# F-01: Username Change Leaderboard
@router.get("/stats")
async def get_name_change_stats(chat_id: int, user: dict = Depends(require_auth)):
    """Get name change statistics (leaderboard) for a group."""
    try:
        async with db.pool.acquire() as conn:
            # Get top 20 users by name change count
            rows = await conn.fetch(
                """SELECT 
                    user_id,
                    COUNT(*) as change_count,
                    MAX(changed_at) as last_changed,
                    -- Get most recent name for this user
                    (SELECT CASE
                        WHEN last_name IS NOT NULL AND last_name != '' 
                        THEN COALESCE(NULLIF(first_name,''), username, 'Unknown') || ' ' || last_name
                        ELSE COALESCE(NULLIF(first_name,''), username, 'Unknown')
                     END 
                     FROM user_name_history u2 
                     WHERE u2.user_id = u1.user_id AND u2.source_chat_id = u1.source_chat_id
                     ORDER BY changed_at DESC LIMIT 1) as user_name
                   FROM user_name_history u1
                   WHERE source_chat_id = $1
                   GROUP BY user_id, source_chat_id
                   ORDER BY change_count DESC
                   LIMIT 20""",
                chat_id,
            )

        return [
            {
                "user_id": r["user_id"],
                "user_name": r["user_name"] or "Unknown",
                "change_count": r["change_count"],
                "last_changed": r["last_changed"].isoformat() if r["last_changed"] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get name change stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch name change statistics")


# F-03: Search Name History by Old Name
@router.get("/search")
async def search_name_history(chat_id: int, q: str = "", user: dict = Depends(require_auth)):
    """Search name history by old name or username."""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
    
    try:
        search_term = f"%{q.lower()}%"
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT DISTINCT ON (user_id)
                    user_id,
                    first_name,
                    last_name,
                    username,
                    old_first_name,
                    old_last_name,
                    old_username,
                    changed_at,
                    CASE
                        WHEN LOWER(old_first_name) LIKE $2 THEN 'first_name'
                        WHEN LOWER(old_last_name) LIKE $2 THEN 'last_name'
                        WHEN LOWER(old_username) LIKE $2 THEN 'username'
                        ELSE 'name'
                    END as matched_field,
                    CASE
                        WHEN LOWER(old_first_name) LIKE $2 THEN old_first_name
                        WHEN LOWER(old_last_name) LIKE $2 THEN old_last_name
                        WHEN LOWER(old_username) LIKE $2 THEN old_username
                        ELSE old_first_name
                    END as matched_value
                   FROM user_name_history
                   WHERE source_chat_id = $1
                     AND (LOWER(old_first_name) LIKE $2 
                          OR LOWER(old_last_name) LIKE $2 
                          OR LOWER(old_username) LIKE $2)
                   ORDER BY user_id, changed_at DESC""",
                chat_id,
                search_term,
            )

        return [
            {
                "user_id": r["user_id"],
                "current_name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or r['username'] or "Unknown",
                "matched_field": r["matched_field"],
                "matched_value": r["matched_value"],
                "changed_at": r["changed_at"].isoformat() if r["changed_at"] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to search name history: {e}")
        raise HTTPException(status_code=500, detail="Failed to search name history")


# F-04: Name Change Timeline per User
@router.get("/user/{user_id}")
async def get_user_name_timeline(chat_id: int, user_id: int, user: dict = Depends(require_auth)):
    """Get full name change timeline for a specific user."""
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT 
                    old_first_name,
                    old_last_name,
                    old_username,
                    first_name,
                    last_name,
                    username,
                    changed_at
                   FROM user_name_history
                   WHERE user_id = $1 AND source_chat_id = $2
                   ORDER BY changed_at ASC""",
                user_id,
                chat_id,
            )

        timeline = []
        for r in rows:
            old_name = f"{r['old_first_name'] or ''} {r['old_last_name'] or ''}".strip() or r['old_username'] or "(unknown)"
            new_name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or r['username'] or "(unknown)"
            
            # Determine change type
            name_changed = (r['old_first_name'] != r['first_name']) or (r['old_last_name'] != r['last_name'])
            username_changed = r['old_username'] != r['username']
            
            if username_changed and not name_changed:
                change_type = "username"
            elif name_changed and not username_changed:
                change_type = "name"
            else:
                change_type = "both"
            
            timeline.append({
                "old_name": old_name,
                "new_name": new_name,
                "old_username": r['old_username'],
                "new_username": r['username'],
                "change_type": change_type,
                "changed_at": r["changed_at"].isoformat() if r["changed_at"] else None,
            })

        return timeline
    except Exception as e:
        logger.error(f"Failed to get user timeline: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user timeline")


# F-05: Export Name History as CSV
@router.get("/export")
async def export_name_history(chat_id: int, user: dict = Depends(require_auth)):
    """Export all name history for a group as JSON (frontend converts to CSV)."""
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT 
                    user_id,
                    old_first_name,
                    old_last_name,
                    old_username,
                    first_name,
                    last_name,
                    username,
                    changed_at
                   FROM user_name_history
                   WHERE source_chat_id = $1
                   ORDER BY changed_at DESC""",
                chat_id,
            )

        return [
            {
                "user_id": r["user_id"],
                "old_name": f"{r['old_first_name'] or ''} {r['old_last_name'] or ''}".strip() or r['old_username'] or "",
                "new_name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or r['username'] or "",
                "old_username": r["old_username"] or "",
                "new_username": r["username"] or "",
                "changed_at": r["changed_at"].isoformat() if r["changed_at"] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to export name history: {e}")
        raise HTTPException(status_code=500, detail="Failed to export name history")
