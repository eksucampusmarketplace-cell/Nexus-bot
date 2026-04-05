"""
api/routes/federation.py

Federation and Personality REST API endpoints.
Provides both legacy /api/federation/* endpoints and newer /federations/* endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user, require_auth
from db.client import db

logger = logging.getLogger(__name__)

# Main router without prefix - registered at /api/federation in main.py
router = APIRouter()

# Legacy router with prefix for backward compatibility
legacy_router = APIRouter(prefix="/api/federation")


# === Legacy routes (/api/federation/*) - used by v21 miniapp ===


@legacy_router.get("/my")
async def list_federations_legacy(user: dict = Depends(get_current_user)):
    """List all federations owned by the user (legacy endpoint)."""
    user_id = user.get("id")

    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT f.id, f.name, f.invite_code, f.created_at,
                          (SELECT COUNT(*) FROM federation_members WHERE federation_id = f.id) as member_count,
                          (SELECT COUNT(*) FROM federation_bans WHERE federation_id = f.id) as ban_count
                   FROM federations f
                   WHERE f.owner_id = $1
                   ORDER BY f.created_at DESC""",
                user_id,
            )

        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to list federations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch federations")


@legacy_router.post("/create")
async def create_federation_legacy(body: dict, user: dict = Depends(get_current_user)):
    """Create a new federation (legacy endpoint)."""
    user_id = user.get("id")
    name = body.get("name", "").strip()
    chat_id = body.get("chat_id")

    if not name:
        raise HTTPException(status_code=400, detail="Federation name is required")

    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id is required")

    import secrets
    import string

    invite_code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    invite_code = f"FED-{invite_code}"

    try:
        async with db.pool.acquire() as conn:
            # Create federation
            fed_id = await conn.fetchval(
                """INSERT INTO federations (owner_id, name, invite_code)
                   VALUES ($1, $2, $3)
                   RETURNING id""",
                user_id,
                name,
                invite_code,
            )

            # Add the group as the first member
            await conn.execute(
                """INSERT INTO federation_members (federation_id, chat_id, joined_at, joined_by)
                   VALUES ($1, $2, NOW(), $3)""",
                fed_id,
                chat_id,
                user_id,
            )

        logger.info(f"[FEDERATION] Created federation {fed_id} '{name}' for user {user_id}")
        return {"id": fed_id, "name": name, "invite_code": invite_code, "owner_id": user_id}
    except Exception as e:
        logger.error(f"Failed to create federation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create federation")


@legacy_router.get("/federations")
async def list_federations_v2(user: dict = Depends(get_current_user)):
    """List all federations owned by the user."""
    return await list_federations_legacy(user)


@legacy_router.post("/join")
async def join_federation_legacy(body: dict, user: dict = Depends(require_auth)):
    """Join a federation using an invite code."""
    user_id = user.get("id")
    invite_code = body.get("invite_code", "").strip().upper()
    chat_id = body.get("chat_id")

    if not invite_code:
        raise HTTPException(status_code=400, detail="Invite code is required")

    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id is required")

    # Verify user is admin of the group they want to add
    from bot.registry import get_all

    bots = get_all()
    is_admin = False

    for bot_app in bots.values():
        try:
            member = await bot_app.bot.get_chat_member(chat_id, user_id)
            if member.status in ["creator", "administrator"]:
                is_admin = True
                break
        except Exception:
            continue

    if not is_admin:
        raise HTTPException(status_code=403, detail="Not an admin of this group")

    try:
        async with db.pool.acquire() as conn:
            # Find federation by invite code
            fed = await conn.fetchrow(
                "SELECT id, owner_id FROM federations WHERE invite_code = $1",
                invite_code,
            )

            if not fed:
                raise HTTPException(status_code=404, detail="Invalid invite code")

            # Check if group is already in this federation
            existing = await conn.fetchval(
                "SELECT 1 FROM federation_members WHERE federation_id = $1 AND chat_id = $2",
                fed["id"],
                chat_id,
            )

            if existing:
                raise HTTPException(status_code=409, detail="Group is already in this federation")

            # Add group to federation
            await conn.execute(
                """INSERT INTO federation_members (federation_id, chat_id, joined_at, joined_by)
                   VALUES ($1, $2, NOW(), $3)""",
                fed["id"],
                chat_id,
                user_id,
            )

        logger.info(f"[FEDERATION] User {user_id} added chat {chat_id} to federation {fed['id']}")
        return {"ok": True, "federation_id": fed["id"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to join federation: {e}")
        raise HTTPException(status_code=500, detail="Failed to join federation")


@legacy_router.get("/federations/{fed_id}")
async def get_federation_legacy(fed_id: str, user: dict = Depends(get_current_user)):
    """Get federation details."""
    return await get_federation(fed_id, user)


@legacy_router.post("/federations/{fed_id}/regenerate-code")
async def regenerate_invite_code_legacy(fed_id: str, user: dict = Depends(get_current_user)):
    """Regenerate federation invite code."""
    return await regenerate_invite_code(fed_id, user)


@legacy_router.get("/groups/{chat_id}/federations")
async def get_group_federations_legacy(chat_id: int, user: dict = Depends(require_auth)):
    """Get federations for a specific group."""
    return await get_group_federations(chat_id, user)


# === Personality API (also via legacy router for miniapp) ===


@legacy_router.get("/personality/preview")
async def get_personality_preview(tone: str = "neutral", language: str = "en", emoji: bool = True):
    """Get preview messages for a personality configuration."""
    try:
        from bot.personality.engine import PersonalityEngine

        engine = PersonalityEngine(tone=tone, language=language, emoji=emoji)
        preview = engine.get_preview()

        return {
            "tone": preview["tone"],
            "description": preview["description"],
            "examples": {
                "warn": preview["warn"],
                "ban": preview["ban"],
                "kick": preview["kick"],
                "mute": preview["mute"],
            },
        }
    except Exception as e:
        logger.error(f"Failed to get personality preview: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate preview")


@legacy_router.get("/personality/tones")
async def get_available_tones():
    """Get list of available personality tones."""
    try:
        from bot.personality.engine import TONES

        return {
            "tones": [
                {"id": tone, "description": data["description"]} for tone, data in TONES.items()
            ]
        }
    except ImportError:
        return {"tones": []}


@legacy_router.get("/languages")
async def get_languages():
    """Get list of supported languages."""
    try:
        from bot.utils.localization import SUPPORTED_LANGUAGES

        return {
            "languages": [
                {"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()
            ]
        }
    except ImportError:
        return {"languages": []}


@legacy_router.get("/groups/{chat_id}/personality")
async def get_group_personality(chat_id: int, user: dict = Depends(require_auth)):
    """Get personality settings for a group."""
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT persona_name, persona_tone, persona_language, persona_emoji
                   FROM groups WHERE chat_id = $1""",
                chat_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Group not found")

        return {
            "name": row["persona_name"],
            "tone": row["persona_tone"] or "neutral",
            "language": row["persona_language"] or "en",
            "emoji": row["persona_emoji"] if row["persona_emoji"] is not None else True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get group personality: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch personality")


@legacy_router.put("/groups/{chat_id}/personality")
async def update_group_personality(
    chat_id: int,
    tone: Optional[str] = None,
    language: Optional[str] = None,
    emoji: Optional[bool] = None,
    name: Optional[str] = None,
    user: dict = Depends(require_auth),
):
    """Update personality settings for a group."""
    try:
        updates: list[str] = []
        values: list = []

        if tone is not None:
            updates.append("persona_tone = $" + str(len(values) + 1))
            values.append(tone)
        if language is not None:
            updates.append("persona_language = $" + str(len(values) + 1))
            values.append(language)
        if emoji is not None:
            updates.append("persona_emoji = $" + str(len(values) + 1))
            values.append(emoji)
        if name is not None:
            updates.append("persona_name = $" + str(len(values) + 1))
            values.append(name)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(chat_id)

        async with db.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE groups SET {', '.join(updates)} WHERE chat_id = ${len(values)}", *values
            )

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update personality: {e}")
        raise HTTPException(status_code=500, detail="Failed to update personality")


# === Main router functions (used by legacy router above) ===


async def get_federation(fed_id: str, user: dict = Depends(get_current_user)):
    """Get federation details."""
    user_id = user.get("id")

    try:
        async with db.pool.acquire() as conn:
            # Check ownership
            fed = await conn.fetchrow("SELECT * FROM federations WHERE id = $1", fed_id)

            if not fed:
                raise HTTPException(status_code=404, detail="Federation not found")

            if fed["owner_id"] != user_id:
                # Check if admin
                is_admin = await conn.fetchval(
                    "SELECT 1 FROM federation_admins WHERE federation_id = $1 AND user_id = $2",
                    fed_id,
                    user_id,
                )
                if not is_admin:
                    raise HTTPException(status_code=403, detail="Not authorized")

            # Get members
            members = await conn.fetch(
                """SELECT fm.chat_id, fm.joined_at, fm.joined_by, g.title
                   FROM federation_members fm
                   LEFT JOIN groups g ON g.chat_id = fm.chat_id
                   WHERE fm.federation_id = $1""",
                fed_id,
            )

            # Get bans
            bans = await conn.fetch(
                """SELECT fb.* FROM federation_bans fb
                   WHERE fb.federation_id = $1
                   ORDER BY fb.banned_at DESC
                   LIMIT 100""",
                fed_id,
            )

            # Get admins
            admins = await conn.fetch(
                """SELECT fa.user_id, fa.promoted_at, fa.promoted_by
                   FROM federation_admins fa
                   WHERE fa.federation_id = $1""",
                fed_id,
            )

        return {
            "federation": dict(fed),
            "members": [dict(m) for m in members],
            "bans": [dict(b) for b in bans],
            "admins": [dict(a) for a in admins],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get federation: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch federation")


async def regenerate_invite_code(fed_id: str, user: dict = Depends(get_current_user)):
    """Regenerate federation invite code."""
    user_id = user.get("id")

    import secrets
    import string

    new_code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    new_code = f"FED-{new_code}"

    try:
        async with db.pool.acquire() as conn:
            # Check ownership
            result = await conn.execute(
                "UPDATE federations SET invite_code = $1 WHERE id = $2 AND owner_id = $3",
                new_code,
                fed_id,
                user_id,
            )

            if result == "UPDATE 0":
                raise HTTPException(
                    status_code=403, detail="Not authorized or federation not found"
                )

        return {"invite_code": new_code}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate code: {e}")
        raise HTTPException(status_code=500, detail="Failed to regenerate code")


async def get_group_federations(chat_id: int, user: dict = Depends(require_auth)):
    """Get federations for a specific group."""
    # Verify user is admin of this group
    from bot.registry import get_all

    bots = get_all()
    is_admin = False

    for bot_app in bots.values():
        try:
            member = await bot_app.bot.get_chat_member(chat_id, user["id"])
            if member.status in ["creator", "administrator"]:
                is_admin = True
                break
        except Exception:
            continue

    if not is_admin:
        raise HTTPException(status_code=403, detail="Not an admin of this group")

    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT f.id, f.name, f.owner_id, fm.joined_at,
                          (SELECT COUNT(*) FROM federation_members WHERE federation_id = f.id) as group_count
                   FROM federation_members fm
                   JOIN federations f ON f.id = fm.federation_id
                   WHERE fm.chat_id = $1""",
                chat_id,
            )

        return {"federations": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Failed to get group federations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch federations")


# === Federation Name History ===

@legacy_router.get("/federations/{fed_id}/name-history")
async def get_federation_name_history(fed_id: str, limit: int = 50, user: dict = Depends(get_current_user)):
    """Get name history across all groups in a federation."""
    user_id = user.get("id")
    
    try:
        async with db.pool.acquire() as conn:
            # Check if user owns or is admin of this federation
            is_authorized = await conn.fetchval(
                """SELECT 1 FROM federations f
                   LEFT JOIN federation_admins fa ON fa.federation_id = f.id AND fa.user_id = $2
                   WHERE f.id = $1 AND (f.owner_id = $2 OR fa.user_id IS NOT NULL)""",
                fed_id, user_id
            )
            
            if not is_authorized:
                raise HTTPException(status_code=403, detail="Not authorized for this federation")
            
            # Get all groups in federation
            group_ids = await conn.fetch(
                "SELECT chat_id FROM federation_members WHERE federation_id = $1",
                fed_id
            )
            chat_ids = [g["chat_id"] for g in group_ids]
            
            if not chat_ids:
                return {"history": [], "groups": []}
            
            # Get name history from all groups in federation
            rows = await conn.fetch(
                """SELECT 
                    uhh.user_id,
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
                    uhh.source_chat_id,
                    g.title as group_name,
                    uhh.is_federated
                 FROM user_name_history uhh
                 LEFT JOIN groups g ON g.chat_id = uhh.source_chat_id
                 WHERE uhh.source_chat_id = ANY($1)
                 ORDER BY uhh.changed_at DESC
                 LIMIT $2""",
                chat_ids, limit
            )
            
            # Get group info
            groups = await conn.fetch(
                "SELECT chat_id, title FROM groups WHERE chat_id = ANY($1)",
                chat_ids
            )
        
        return {
            "history": [
                {
                    "user_id": r["user_id"],
                    "user_name": r["user_name"] or r["username"] or "Unknown",
                    "old_name": r["old_name"] or r["old_username"] or "",
                    "changed_at": r["changed_at"].isoformat() if r["changed_at"] else None,
                    "chat_id": r["source_chat_id"],
                    "group_name": r["group_name"] or f"Group {r['source_chat_id']}",
                    "is_federated": r["is_federated"] or False,
                }
                for r in rows
            ],
            "groups": [{"chat_id": g["chat_id"], "title": g["title"]} for g in groups]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get federation name history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch federation name history")


@legacy_router.get("/federations/{fed_id}/name-history/stats")
async def get_federation_name_stats(fed_id: str, user: dict = Depends(get_current_user)):
    """Get name change statistics across a federation."""
    user_id = user.get("id")
    
    try:
        async with db.pool.acquire() as conn:
            # Check authorization
            is_authorized = await conn.fetchval(
                """SELECT 1 FROM federations f
                   LEFT JOIN federation_admins fa ON fa.federation_id = f.id AND fa.user_id = $2
                   WHERE f.id = $1 AND (f.owner_id = $2 OR fa.user_id IS NOT NULL)""",
                fed_id, user_id
            )
            
            if not is_authorized:
                raise HTTPException(status_code=403, detail="Not authorized")
            
            # Get stats across federation
            rows = await conn.fetch(
                """SELECT 
                    uhh.user_id,
                    COUNT(*) as change_count,
                    MAX(uhh.changed_at) as last_changed,
                    (SELECT CASE
                        WHEN last_name IS NOT NULL AND last_name != '' 
                        THEN COALESCE(NULLIF(first_name,''), username, 'Unknown') || ' ' || last_name
                        ELSE COALESCE(NULLIF(first_name,''), username, 'Unknown')
                     END 
                     FROM user_name_history u2 
                     WHERE u2.user_id = uhh.user_id 
                       AND u2.source_chat_id IN (SELECT chat_id FROM federation_members WHERE federation_id = $1)
                     ORDER BY changed_at DESC LIMIT 1) as user_name,
                     array_agg(DISTINCT uhh.source_chat_id) as chat_ids
                 FROM user_name_history uhh
                 WHERE uhh.source_chat_id IN (SELECT chat_id FROM federation_members WHERE federation_id = $1)
                 GROUP BY uhh.user_id
                 ORDER BY change_count DESC
                 LIMIT 20""",
                fed_id
            )
        
        return [
            {
                "user_id": r["user_id"],
                "user_name": r["user_name"] or "Unknown",
                "change_count": r["change_count"],
                "last_changed": r["last_changed"].isoformat() if r["last_changed"] else None,
                "groups_affected": len(r["chat_ids"]) if r["chat_ids"] else 0,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get federation name stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch federation stats")
