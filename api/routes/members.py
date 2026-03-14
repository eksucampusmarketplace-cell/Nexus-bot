from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth import get_current_user
from db.client import db
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/groups/{chat_id}")


async def _fetch_admins_from_telegram(chat_id: int) -> list:
    """Fetch admin list from Telegram to get accurate member data."""
    from bot.registry import get_all
    bots = get_all()
    if not bots:
        return []

    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break

    if not bot_app:
        return []

    try:
        admins = await bot_app.bot.get_chat_administrators(chat_id)
        return [
            {
                "user_id": admin.user.id,
                "username": admin.user.username,
                "first_name": admin.user.first_name,
                "last_name": admin.user.last_name,
                "is_admin": True,
                "is_owner": admin.status == "creator",
                "status": "creator" if admin.status == "creator" else "administrator"
            }
            for admin in admins
        ]
    except Exception as e:
        logger.warning(f"[Members] Failed to fetch admins from Telegram for chat {chat_id}: {e}")
        return []


@router.get("/members")
async def list_members(chat_id: int, user: dict = Depends(get_current_user)):
    """
    Get members list for a group.
    Combines data from multiple sources: users table, boost records, and Telegram API.
    """
    members_map = {}

    # 1. Get users from the users table (users who have sent messages)
    async with db.pool.acquire() as conn:
        user_rows = await conn.fetch(
            "SELECT * FROM users WHERE chat_id = $1 ORDER BY last_seen DESC LIMIT 100",
            chat_id
        )
        for r in user_rows:
            d = dict(r)
            if isinstance(d.get('warns'), str):
                d['warns'] = json.loads(d['warns'])
            members_map[d['user_id']] = {
                "user_id": d['user_id'],
                "username": d.get('username'),
                "first_name": d.get('first_name'),
                "warns": d.get('warns', []),
                "is_muted": d.get('is_muted', False),
                "is_banned": d.get('is_banned', False),
                "message_count": d.get('message_count', 0),
                "trust_score": d.get('trust_score', 50),
                "last_seen": d.get('last_seen'),
                "join_date": d.get('join_date'),
                "source": "activity"
            }

    # 2. Get members from member_boost_records (tracked via invite system)
    async with db.pool.acquire() as conn:
        boost_rows = await conn.fetch(
            "SELECT user_id, username, first_name, invited_count, is_unlocked, is_restricted, created_at "
            "FROM member_boost_records WHERE group_id = $1",
            chat_id
        )
        for r in boost_rows:
            user_id = r['user_id']
            if user_id in members_map:
                # Merge with existing data
                members_map[user_id]['boost_data'] = {
                    "invited_count": r.get('invited_count', 0),
                    "is_unlocked": r.get('is_unlocked', True),
                    "is_restricted": r.get('is_restricted', False)
                }
                # Update username/first_name if missing
                if not members_map[user_id].get('username') and r.get('username'):
                    members_map[user_id]['username'] = r['username']
                if not members_map[user_id].get('first_name') and r.get('first_name'):
                    members_map[user_id]['first_name'] = r['first_name']
            else:
                members_map[user_id] = {
                    "user_id": user_id,
                    "username": r.get('username'),
                    "first_name": r.get('first_name'),
                    "warns": [],
                    "is_muted": False,
                    "is_banned": False,
                    "message_count": 0,
                    "trust_score": 50,
                    "last_seen": r.get('created_at'),
                    "join_date": r.get('created_at'),
                    "boost_data": {
                        "invited_count": r.get('invited_count', 0),
                        "is_unlocked": r.get('is_unlocked', True),
                        "is_restricted": r.get('is_restricted', False)
                    },
                    "source": "boost"
                }

    # 3. Get members from force_channel_records (tracked via channel gate)
    async with db.pool.acquire() as conn:
        channel_rows = await conn.fetch(
            "SELECT user_id, username, is_verified, is_restricted, last_checked "
            "FROM force_channel_records WHERE group_id = $1",
            chat_id
        )
        for r in channel_rows:
            user_id = r['user_id']
            if user_id in members_map:
                members_map[user_id]['channel_data'] = {
                    "is_verified": r.get('is_verified', False),
                    "is_restricted": r.get('is_restricted', False)
                }
                if not members_map[user_id].get('username') and r.get('username'):
                    members_map[user_id]['username'] = r['username']
            else:
                members_map[user_id] = {
                    "user_id": user_id,
                    "username": r.get('username'),
                    "first_name": None,
                    "warns": [],
                    "is_muted": False,
                    "is_banned": False,
                    "message_count": 0,
                    "trust_score": 50,
                    "last_seen": r.get('last_checked'),
                    "channel_data": {
                        "is_verified": r.get('is_verified', False),
                        "is_restricted": r.get('is_restricted', False)
                    },
                    "source": "channel_gate"
                }

    # 4. Get admin data from Telegram to enrich member info
    admins = await _fetch_admins_from_telegram(chat_id)
    for admin in admins:
        user_id = admin['user_id']
        if user_id in members_map:
            members_map[user_id]['is_admin'] = True
            members_map[user_id]['is_owner'] = admin.get('is_owner', False)
            members_map[user_id]['status'] = admin.get('status')
            if not members_map[user_id].get('username') and admin.get('username'):
                members_map[user_id]['username'] = admin['username']
            if not members_map[user_id].get('first_name') and admin.get('first_name'):
                members_map[user_id]['first_name'] = admin['first_name']
        else:
            members_map[user_id] = {
                "user_id": user_id,
                "username": admin.get('username'),
                "first_name": admin.get('first_name'),
                "warns": [],
                "is_muted": False,
                "is_banned": False,
                "message_count": 0,
                "trust_score": 100,  # Admins have high trust
                "is_admin": True,
                "is_owner": admin.get('is_owner', False),
                "status": admin.get('status'),
                "source": "telegram_admin"
            }

    # Convert map to list and sort by last_seen (most recent first)
    from datetime import datetime
    members_list = list(members_map.values())

    def get_sort_key(x):
        last_seen = x.get('last_seen')
        if last_seen is None:
            return datetime(1970, 1, 1)
        if isinstance(last_seen, datetime):
            return last_seen
        if isinstance(last_seen, str):
            try:
                return datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return datetime(1970, 1, 1)
        return datetime(1970, 1, 1)

    members_list.sort(key=get_sort_key, reverse=True)

    return members_list


@router.get("/members/events")
async def get_member_events(
    chat_id: int, request: Request,
    event_type: str = None, limit: int = 50
):
    # db   = request.app.state.db
    async with db.pool.acquire() as conn:
        q    = """
            SELECT * FROM member_events
            WHERE chat_id=$1
            {type_filter}
            ORDER BY created_at DESC
            LIMIT $2
        """
        if event_type:
            rows = await conn.fetch(
                q.format(type_filter="AND event_type=$3"),
                chat_id, limit, event_type
            )
        else:
            rows = await conn.fetch(
                q.format(type_filter=""), chat_id, limit
            )
    return [dict(r) for r in rows]


@router.get("/members/approved")
async def get_approved(chat_id: int):
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT am.*, u.username FROM approved_members am "
            "LEFT JOIN users u ON am.user_id = u.user_id AND am.chat_id = u.chat_id "
            "WHERE am.chat_id=$1 ORDER BY approved_at DESC",
            chat_id
        )
    return [dict(r) for r in rows]


@router.post("/members/{user_id}/approve")
async def approve_member(chat_id: int, user_id: int, request: Request):
    approver = request.state.user_id
    async with db.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO approved_members (chat_id, user_id, approved_by)
               VALUES ($1,$2,$3)
               ON CONFLICT (chat_id, user_id) DO NOTHING""",
            chat_id, user_id, approver
        )
    return {"ok": True}


@router.delete("/members/{user_id}/approve")
async def unapprove_member(chat_id: int, user_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM approved_members WHERE chat_id=$1 AND user_id=$2",
            chat_id, user_id
        )
    return {"ok": True}


@router.post("/members/{user_id}/mute")
async def mute_member(chat_id: int, user_id: int, request: Request):
    """Mute a member (restrict from sending messages)."""
    body = await request.json()
    duration = body.get("duration", 3600)  # Default 1 hour
    
    try:
        # Get bot app for this group
        from bot.registry import get_all
        bots = get_all()
        bot_app = None
        for bid, app in bots.items():
            bot_app = app
            break
        
        if not bot_app:
            raise HTTPException(status_code=503, detail="Bot service unavailable")
        
        from telegram import ChatPermissions
        await bot_app.bot.restrict_chat_member(
            chat_id, user_id, ChatPermissions(can_send_messages=False)
        )
        
        # Update database
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO users (chat_id, user_id, is_muted, updated_at)
                   VALUES ($1, $2, TRUE, NOW())
                   ON CONFLICT (chat_id, user_id) 
                   DO UPDATE SET is_muted = TRUE, updated_at = NOW()""",
                chat_id, user_id
            )
            
            # Log the action
            await conn.execute(
                """INSERT INTO actions_log 
                   (chat_id, action, target_user_id, by_user_id, reason, timestamp)
                   VALUES ($1, 'mute', $2, $3, $4, NOW())""",
                chat_id, user_id, request.state.user_id, f"Muted for {duration}s via Mini App"
            )
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"[Members] Error muting member {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to mute member")


@router.post("/members/{user_id}/kick")
async def kick_member(chat_id: int, user_id: int, request: Request):
    """Kick a member from the group."""
    try:
        # Get bot app for this group
        from bot.registry import get_all
        bots = get_all()
        bot_app = None
        for bid, app in bots.items():
            bot_app = app
            break
        
        if not bot_app:
            raise HTTPException(status_code=503, detail="Bot service unavailable")
        
        await bot_app.bot.ban_chat_member(chat_id, user_id)
        await bot_app.bot.unban_chat_member(chat_id, user_id)
        
        # Log the action
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO actions_log 
                   (chat_id, action, target_user_id, by_user_id, reason, timestamp)
                   VALUES ($1, 'kick', $2, $3, 'Kicked via Mini App', NOW())""",
                chat_id, user_id, request.state.user_id
            )
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"[Members] Error kicking member {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to kick member")


@router.post("/members/{user_id}/ban")
async def ban_member(chat_id: int, user_id: int, request: Request):
    """Ban a member from the group."""
    try:
        # Get bot app for this group
        from bot.registry import get_all
        bots = get_all()
        bot_app = None
        for bid, app in bots.items():
            bot_app = app
            break
        
        if not bot_app:
            raise HTTPException(status_code=503, detail="Bot service unavailable")
        
        await bot_app.bot.ban_chat_member(chat_id, user_id)
        
        # Update database
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO users (chat_id, user_id, is_banned, updated_at)
                   VALUES ($1, $2, TRUE, NOW())
                   ON CONFLICT (chat_id, user_id) 
                   DO UPDATE SET is_banned = TRUE, updated_at = NOW()""",
                chat_id, user_id
            )
            
            # Log the action
            await conn.execute(
                """INSERT INTO actions_log 
                   (chat_id, action, target_user_id, by_user_id, reason, timestamp)
                   VALUES ($1, 'ban', $2, $3, 'Banned via Mini App', NOW())""",
                chat_id, user_id, request.state.user_id
            )
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"[Members] Error banning member {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to ban member")


@router.post("/members/{user_id}/unban")
async def unban_member(chat_id: int, user_id: int, request: Request):
    """Unban a member from the group."""
    try:
        # Get bot app for this group
        from bot.registry import get_all
        bots = get_all()
        bot_app = None
        for bid, app in bots.items():
            bot_app = app
            break
        
        if not bot_app:
            raise HTTPException(status_code=503, detail="Bot service unavailable")
        
        await bot_app.bot.unban_chat_member(chat_id, user_id)
        
        # Update database
        async with db.pool.acquire() as conn:
            await conn.execute(
                """UPDATE users SET is_banned = FALSE, updated_at = NOW()
                   WHERE chat_id = $1 AND user_id = $2""",
                chat_id, user_id
            )
            
            # Log the action
            await conn.execute(
                """INSERT INTO actions_log 
                   (chat_id, action, target_user_id, by_user_id, reason, timestamp)
                   VALUES ($1, 'unban', $2, $3, 'Unbanned via Mini App', NOW())""",
                chat_id, user_id, request.state.user_id
            )
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"[Members] Error unbanning member {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to unban member")


@router.post("/members/{user_id}/unmute")
async def unmute_member(chat_id: int, user_id: int, request: Request):
    """Unmute a member (restore permissions)."""
    try:
        # Get bot app for this group
        from bot.registry import get_all
        bots = get_all()
        bot_app = None
        for bid, app in bots.items():
            bot_app = app
            break
        
        if not bot_app:
            raise HTTPException(status_code=503, detail="Bot service unavailable")
        
        from telegram import ChatPermissions
        await bot_app.bot.restrict_chat_member(
            chat_id, user_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False
            )
        )
        
        # Update database
        async with db.pool.acquire() as conn:
            await conn.execute(
                """UPDATE users SET is_muted = FALSE, updated_at = NOW()
                   WHERE chat_id = $1 AND user_id = $2""",
                chat_id, user_id
            )
            
            # Log the action
            await conn.execute(
                """INSERT INTO actions_log 
                   (chat_id, action, target_user_id, by_user_id, reason, timestamp)
                   VALUES ($1, 'unmute', $2, $3, 'Unmuted via Mini App', NOW())""",
                chat_id, user_id, request.state.user_id
            )
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"[Members] Error unmuting member {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to unmute member")


@router.post("/members/{user_id}/warn")
async def warn_member(chat_id: int, user_id: int, request: Request):
    """Add a warning to a member."""
    body = await request.json()
    reason = body.get("reason", "Warned via Mini App")
    
    try:
        # Get current warns for the user
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT warns FROM users WHERE chat_id = $1 AND user_id = $2",
                chat_id, user_id
            )
            
            warns = []
            if row and row['warns']:
                if isinstance(row['warns'], str):
                    warns = json.loads(row['warns'])
                else:
                    warns = row['warns']
            
            # Add new warning
            warns.append({
                "reason": reason,
                "timestamp": "now()",
                "by": request.state.user_id
            })
            
            # Update user record
            await conn.execute(
                """INSERT INTO users (chat_id, user_id, warns, updated_at)
                   VALUES ($1, $2, $3, NOW())
                   ON CONFLICT (chat_id, user_id) 
                   DO UPDATE SET warns = $3, updated_at = NOW()""",
                chat_id, user_id, json.dumps(warns)
            )
            
            # Log the action
            await conn.execute(
                """INSERT INTO actions_log 
                   (chat_id, action, target_user_id, by_user_id, reason, timestamp)
                   VALUES ($1, 'warn', $2, $3, $4, NOW())""",
                chat_id, user_id, reason, request.state.user_id
            )
        
        return {"ok": True, "warn_count": len(warns)}
    except Exception as e:
        logger.error(f"[Members] Error warning member {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to warn member")


@router.post("/members/bulk")
async def bulk_action(chat_id: int, request: Request):
    body    = await request.json()
    user_ids = body.get("user_ids", [])
    action  = body.get("action")

    if not user_ids or action not in ("ban", "mute", "unmute", "approve", "kick", "unapprove", "warn"):
        raise HTTPException(status_code=400, detail="Invalid request")

    results = {"ok": [], "failed": []}
    
    # Get bot app for this group
    from bot.registry import get_all
    bots = get_all()
    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break

    async with db.pool.acquire() as conn:
        for uid in user_ids[:50]:  # max 50 per bulk action
            try:
                if action == "approve":
                    await conn.execute(
                        """INSERT INTO approved_members
                           (chat_id, user_id, approved_by)
                           VALUES ($1,$2,$3)
                           ON CONFLICT (chat_id, user_id) DO NOTHING""",
                        chat_id, uid, request.state.user_id
                    )
                elif action == "unapprove":
                    await conn.execute(
                        "DELETE FROM approved_members WHERE chat_id=$1 AND user_id=$2",
                        chat_id, uid
                    )
                elif action == "warn":
                    # Get current warns
                    row = await conn.fetchrow(
                        "SELECT warns FROM users WHERE chat_id = $1 AND user_id = $2",
                        chat_id, uid
                    )
                    warns = []
                    if row and row['warns']:
                        if isinstance(row['warns'], str):
                            warns = json.loads(row['warns'])
                        else:
                            warns = row['warns']
                    
                    warns.append({
                        "reason": "Warned via bulk action",
                        "timestamp": "now()",
                        "by": request.state.user_id
                    })
                    
                    await conn.execute(
                        """INSERT INTO users (chat_id, user_id, warns, updated_at)
                           VALUES ($1, $2, $3, NOW())
                           ON CONFLICT (chat_id, user_id) 
                           DO UPDATE SET warns = $3, updated_at = NOW()""",
                        chat_id, uid, json.dumps(warns)
                    )
                    
                    # Log the action
                    await conn.execute(
                        """INSERT INTO actions_log 
                           (chat_id, action, target_user_id, by_user_id, reason, timestamp)
                           VALUES ($1, 'warn', $2, $3, 'Bulk warn action', NOW())""",
                        chat_id, uid, request.state.user_id
                    )
                elif bot_app:
                    if action == "ban":
                        await bot_app.bot.ban_chat_member(chat_id, uid)
                        # Update database
                        await conn.execute(
                            """INSERT INTO users (chat_id, user_id, is_banned, updated_at)
                               VALUES ($1, $2, TRUE, NOW())
                               ON CONFLICT (chat_id, user_id) 
                               DO UPDATE SET is_banned = TRUE, updated_at = NOW()""",
                            chat_id, uid
                        )
                    elif action == "mute":
                        from telegram import ChatPermissions
                        await bot_app.bot.restrict_chat_member(
                            chat_id, uid, ChatPermissions(can_send_messages=False)
                        )
                        # Update database
                        await conn.execute(
                            """INSERT INTO users (chat_id, user_id, is_muted, updated_at)
                               VALUES ($1, $2, TRUE, NOW())
                               ON CONFLICT (chat_id, user_id) 
                               DO UPDATE SET is_muted = TRUE, updated_at = NOW()""",
                            chat_id, uid
                        )
                    elif action == "unmute":
                        from telegram import ChatPermissions
                        await bot_app.bot.restrict_chat_member(
                            chat_id, uid,
                            ChatPermissions(
                                can_send_messages=True,
                                can_send_media_messages=True,
                                can_send_polls=True,
                                can_send_other_messages=True,
                                can_add_web_page_previews=True,
                                can_change_info=False,
                                can_invite_users=True,
                                can_pin_messages=False
                            )
                        )
                        # Update database
                        await conn.execute(
                            """UPDATE users SET is_muted = FALSE, updated_at = NOW()
                               WHERE chat_id = $1 AND user_id = $2""",
                            chat_id, uid
                        )
                    elif action == "kick":
                        await bot_app.bot.ban_chat_member(chat_id, uid)
                        await bot_app.bot.unban_chat_member(chat_id, uid)
                results["ok"].append(uid)
            except Exception:
                results["failed"].append(uid)

    return results


@router.get("/antiraid/status")
async def antiraid_status(chat_id: int):
    async with db.pool.acquire() as conn:
        session = await conn.fetchrow(
            """SELECT * FROM antiraid_sessions
               WHERE chat_id=$1 AND is_active=TRUE
               ORDER BY triggered_at DESC LIMIT 1""",
            chat_id
        )
    return dict(session) if session else {"active": False}


@router.put("/antiraid/settings")
async def update_antiraid_settings(chat_id: int, request: Request):
    body = await request.json()
    from db.ops.automod import update_group_setting

    keys = [
        "antiraid_enabled", "antiraid_mode", "antiraid_threshold",
        "antiraid_duration_mins", "auto_antiraid_enabled",
        "auto_antiraid_threshold", "captcha_enabled", "captcha_mode",
        "captcha_timeout_mins", "captcha_kick_on_timeout"
    ]
    for k in keys:
        if k in body:
            await update_group_setting(db.pool, chat_id, k, body[k])

    return {"ok": True}

@router.post("/antiraid/toggle")
async def toggle_antiraid(chat_id: int, request: Request):
    body = await request.json()
    enable = body.get("enable", False)
    
    # Need to call the bot handler or trigger it.
    # Since we have the bot app and settings, we can call manual_toggle_raid.
    from bot.registry import get_all
    bots = get_all()
    bot_app = None
    for bid, app in bots.items():
        bot_app = app
        break
    
    if not bot_app:
        raise HTTPException(status_code=503, detail="Bot service unavailable")
        
    from db.ops.automod import get_group_settings
    settings = await get_group_settings(db.pool, chat_id)
    from bot.antiraid.engine import manual_toggle_raid
    
    result = await manual_toggle_raid(
        bot_app.bot, chat_id, enable, settings, db.pool, request.state.user_id
    )
    return {"ok": True, "result": result}
