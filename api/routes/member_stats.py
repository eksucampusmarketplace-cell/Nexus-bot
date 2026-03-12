"""
Member-specific API routes for the Mini App member view.
These endpoints return personal stats, rankings, and invite links for regular members.
"""

from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from db.client import db
from db.ops.booster import (
    get_boost_record, get_user_invites, get_boost_stats,
    get_channel_record, get_channel_gate_config
)
from db.ops.groups import get_group
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me")


@router.get("/groups/{chat_id}/stats")
async def get_member_group_stats(
    chat_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Get member's personal stats for a specific group:
    - invited_count, message_count, trust_score
    - warn_count, warn_limit, boost_record
    - channel_verified, reputation
    """
    user_id = user.get('id')

    async with db.pool.acquire() as conn:
        # Get user record
        user_row = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id
        )

        # Get boost record
        boost_row = await conn.fetchrow(
            "SELECT * FROM member_boost_records WHERE group_id = $1 AND user_id = $2",
            chat_id, user_id
        )

        # Get invite events count
        invited_count = await conn.fetchval(
            "SELECT COUNT(*) FROM member_invite_events WHERE group_id = $1 AND inviter_user_id = $2",
            chat_id, user_id
        ) or 0

        # Get channel record
        channel_row = await conn.fetchrow(
            "SELECT * FROM force_channel_records WHERE group_id = $1 AND user_id = $2",
            chat_id, user_id
        )

    # Parse warns
    warns = []
    if user_row and user_row['warns']:
        import json
        warns = user_row['warns'] if isinstance(user_row['warns'], list) else json.loads(user_row['warns'])

    # Get group settings for warn limit
    group = await get_group(chat_id)
    warn_limit = 3
    if group and group.get('settings'):
        warn_limit = group['settings'].get('warnings', {}).get('threshold', 3)

    return {
        "invited_count": invited_count,
        "message_count": user_row['message_count'] if user_row else 0,
        "trust_score": user_row['trust_score'] if user_row else 50,
        "warn_count": len(warns),
        "warn_limit": warn_limit,
        "warns": warns,
        "boost": {
            "enabled": bool(boost_row),
            "current": (boost_row['invited_count'] + boost_row['manual_credits']) if boost_row else 0,
            "required": boost_row['required_count'] if boost_row else 5,
            "is_unlocked": boost_row['is_unlocked'] if boost_row else True,
            "invite_link": boost_row['invite_link'] if boost_row else None,
            "is_exempted": boost_row['is_exempted'] if boost_row else False
        },
        "channel": {
            "enabled": bool(channel_row),
            "is_verified": channel_row['is_verified'] if channel_row else True,
            "channel_id": channel_row['channel_id'] if channel_row else None
        },
        "join_date": user_row['join_date'].isoformat() if user_row and user_row['join_date'] else None
    }


@router.get("/groups/{chat_id}/rankings")
async def get_member_group_rankings(
    chat_id: int,
    type: str = "boost",  # boost | trust | messages
    page: int = 1,
    user: dict = Depends(get_current_user)
):
    """
    Get leaderboard with user's position highlighted.
    Types: boost (invites), trust (trust_score), messages (message_count)
    """
    user_id = user.get('id')
    limit = 10
    offset = (page - 1) * limit

    async with db.pool.acquire() as conn:
        if type == "boost":
            # Get invite leaderboard
            rows = await conn.fetch("""
                SELECT user_id, username, first_name,
                       (invited_count + manual_credits) as total_invites
                FROM member_boost_records
                WHERE group_id = $1
                ORDER BY total_invites DESC
                LIMIT $2 OFFSET $3
            """, chat_id, limit, offset)

            # Get user's rank
            user_rank = await conn.fetchval("""
                SELECT COUNT(*) + 1
                FROM member_boost_records
                WHERE group_id = $1 AND (invited_count + manual_credits) > (
                    SELECT invited_count + manual_credits
                    FROM member_boost_records
                    WHERE group_id = $1 AND user_id = $2
                )
            """, chat_id, user_id)

            # Get user's total
            user_total = await conn.fetchval("""
                SELECT (invited_count + manual_credits)
                FROM member_boost_records
                WHERE group_id = $1 AND user_id = $2
            """, chat_id, user_id) or 0

        elif type == "trust":
            rows = await conn.fetch("""
                SELECT user_id, username, first_name, trust_score as score
                FROM users
                WHERE chat_id = $1
                ORDER BY trust_score DESC
                LIMIT $2 OFFSET $3
            """, chat_id, limit, offset)

            user_rank = await conn.fetchval("""
                SELECT COUNT(*) + 1
                FROM users
                WHERE chat_id = $1 AND trust_score > (
                    SELECT trust_score FROM users WHERE chat_id = $1 AND user_id = $2
                )
            """, chat_id, user_id)

            user_total = await conn.fetchval(
                "SELECT trust_score FROM users WHERE chat_id = $1 AND user_id = $2",
                chat_id, user_id
            ) or 0

        else:  # messages
            rows = await conn.fetch("""
                SELECT user_id, username, first_name, message_count as count
                FROM users
                WHERE chat_id = $1
                ORDER BY message_count DESC
                LIMIT $2 OFFSET $3
            """, chat_id, limit, offset)

            user_rank = await conn.fetchval("""
                SELECT COUNT(*) + 1
                FROM users
                WHERE chat_id = $1 AND message_count > (
                    SELECT message_count FROM users WHERE chat_id = $1 AND user_id = $2
                )
            """, chat_id, user_id)

            user_total = await conn.fetchval(
                "SELECT message_count FROM users WHERE chat_id = $1 AND user_id = $2",
                chat_id, user_id
            ) or 0

    leaderboard = []
    for i, row in enumerate(rows):
        rank = offset + i + 1
        entry = {
            "rank": rank,
            "user_id": row['user_id'],
            "username": row['username'],
            "first_name": row['first_name'],
            "value": row.get('total_invites') or row.get('score') or row.get('count', 0),
            "is_you": row['user_id'] == user_id
        }
        leaderboard.append(entry)

    return {
        "type": type,
        "page": page,
        "leaderboard": leaderboard,
        "you": {
            "rank": user_rank or 0,
            "value": user_total
        }
    }


@router.get("/groups/{chat_id}/invitelink")
async def get_member_invite_link(
    chat_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Return user's personal invite link for that group.
    Creates one if it doesn't exist yet.
    """
    user_id = user.get('id')

    # Check if we have a record with invite link
    boost_record = await get_boost_record(chat_id, user_id)

    if boost_record and boost_record.get('invite_link'):
        return {
            "invite_link": boost_record['invite_link'],
            "invite_link_name": boost_record.get('invite_link_name'),
            "invited_count": boost_record['invited_count'],
            "created": False
        }

    # Need to create an invite link via Telegram bot
    from bot.registry import get_all
    bots = get_all()
    if not bots:
        raise HTTPException(status_code=503, detail="Bot service unavailable")

    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break

    try:
        # Create a named invite link for this user
        invite_name = f"user_{user_id}"
        result = await bot_app.bot.create_chat_invite_link(
            chat_id=chat_id,
            name=invite_name,
            creates_join_request=False
        )

        # Save to database
        from db.ops.booster import create_boost_record
        await create_boost_record(
            group_id=chat_id,
            user_id=user_id,
            username=user.get('username'),
            first_name=user.get('first_name'),
            invite_link=result.invite_link,
            invite_link_name=invite_name,
            required_count=5  # Default
        )

        return {
            "invite_link": result.invite_link,
            "invite_link_name": invite_name,
            "invited_count": 0,
            "created": True
        }

    except Exception as e:
        logger.error(f"[ME] Failed to create invite link | chat_id={chat_id} user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create invite link")


@router.get("/groups/{chat_id}/rules")
async def get_group_rules(
    chat_id: int,
    user: dict = Depends(get_current_user)
):
    """Get group rules text for display to member."""
    group = await get_group(chat_id)

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    settings = group.get('settings', {})
    rules = settings.get('rules', [])

    return {
        "chat_id": chat_id,
        "title": group.get('title'),
        "rules": rules,
        "rules_text": "\n".join(f"{i+1}. {rule}" for i, rule in enumerate(rules)) if rules else "No rules set for this group."
    }


@router.get("/groups/{chat_id}/activity")
async def get_member_activity(
    chat_id: int,
    user: dict = Depends(get_current_user)
):
    """
    Get member's activity data for charts (last 7 days of messages).
    """
    user_id = user.get('id')

    # For now return mock data - in production this would query a message history table
    # Could be implemented with proper message tracking
    from datetime import datetime, timedelta

    days = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        # Mock message count - would be real data from analytics
        days.append({
            "date": date.strftime("%Y-%m-%d"),
            "day": date.strftime("%a"),
            "messages": 0  # Placeholder
        })

    return {
        "chat_id": chat_id,
        "user_id": user_id,
        "activity": days
    }
