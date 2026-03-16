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


@legacy_router.get("/federations")
async def list_federations_v2(user: dict = Depends(get_current_user)):
    """List all federations owned by the user."""
    return await list_federations_legacy(user)


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
        updates = []
        values = []

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
