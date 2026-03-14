from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth import get_current_user
from db.client import db
from db.ops.groups import get_user_managed_groups, get_group, update_group_settings
from db.ops.logs import get_recent_logs
import json

router = APIRouter()

@router.get("")
async def list_groups(user: dict = Depends(get_current_user)):
    bot_token = user.get("validated_bot_token")
    if not bot_token:
        # Fallback to all groups if no bot context (unlikely with get_current_user)
        return await get_user_managed_groups(user['id'])
    
    import hashlib
    token_hash = hashlib.sha256(bot_token.encode()).hexdigest()[:10]
    
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM groups WHERE bot_token_hash = $1", token_hash)
        res = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get('settings'), str):
                try:
                    d['settings'] = json.loads(d['settings'])
                except Exception:
                    d['settings'] = {}
            elif not d.get('settings'):
                d['settings'] = {}
            res.append(d)
        return res

@router.get("/{chat_id}")
async def group_details(chat_id: int, user: dict = Depends(get_current_user)):
    group = await get_group(chat_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

@router.put("/{chat_id}/settings")
async def update_settings(chat_id: int, settings: dict, user: dict = Depends(get_current_user)):
    # In a real app, verify user is admin in chat_id
    await update_group_settings(chat_id, settings)
    return {"status": "ok"}

@router.put("/{chat_id}/settings/bulk")
async def bulk_update_settings(chat_id: int, request: Request):
    """Bulk update multiple settings at once (for templates)."""
    body = await request.json()
    settings = body.get("settings", {})
    
    from db.ops.automod import bulk_update_group_settings
    await bulk_update_group_settings(db.pool, chat_id, settings)
    
    # Publish SSE event
    from api.routes.events import EventBus
    await EventBus.publish(chat_id, "settings_change", {"settings": settings})
    
    return {"status": "ok"}

@router.get("/{chat_id}/logs")
async def group_logs(chat_id: int, user: dict = Depends(get_current_user)):
    logs = await get_recent_logs(chat_id)
    return logs


@router.get("/{chat_id}/leaderboard")
async def group_leaderboard(chat_id: int, limit: int = 20, user: dict = Depends(get_current_user)):
    """Get leaderboard for a group (top members by XP/message count)."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                user_id,
                first_name,
                username,
                message_count,
                trust_score
            FROM users
            WHERE chat_id = $1
            ORDER BY message_count DESC
            LIMIT $2
        """, chat_id, limit)

    leaderboard = []
    for row in rows:
        # Approximate XP from message count (10 XP per message)
        xp = (row['message_count'] or 0) * 10
        # Approximate level from XP (simple formula)
        level = max(1, int((xp / 1000) ** 0.5)) if xp > 0 else 1

        # Determine badges (simplified)
        badges = []
        if xp >= 10000:
            badges.append('first_1000')
        if xp >= 5000:
            badges.append('level_10')
        if xp >= 1000:
            badges.append('level_5')
        if xp >= 500:
            badges.append('first_100')

        leaderboard.append({
            'user_id': row['user_id'],
            'first_name': row['first_name'] or 'User',
            'username': row['username'],
            'xp': xp,
            'level': level,
            'badges': badges
        })

    return {'chat_id': chat_id, 'leaderboard': leaderboard}


@router.get("/{chat_id}/member-stats")
async def group_member_stats(chat_id: int, limit: int = 20, user: dict = Depends(get_current_user)):
    """Get member statistics for a group."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                user_id,
                first_name,
                username,
                message_count,
                trust_score
            FROM users
            WHERE chat_id = $1
            ORDER BY message_count DESC
            LIMIT $2
        """, chat_id, limit)

    members = []
    for row in rows:
        members.append({
            'user_id': row['user_id'],
            'first_name': row['first_name'] or 'User',
            'username': row['username'],
            'message_count': row['message_count'] or 0,
            'trust_score': row['trust_score'] or 50
        })

    return {'chat_id': chat_id, 'top_members': members}
