"""
api/routes/users.py

User-related API endpoints for v21 features.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user, require_auth
from db.client import db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{user_id}/history")
async def get_user_history(user_id: int, user: dict = Depends(require_auth)):
    """Get name history for a user."""
    try:
        async with db.pool.acquire() as conn:
            # Check if user opted out
            optout = await conn.fetchval(
                "SELECT 1 FROM user_history_optout WHERE user_id = $1",
                user_id
            )
            
            if optout:
                return {
                    "user_id": user_id,
                    "opted_out": True,
                    "history": []
                }
            
            # Get history
            history = await conn.fetch(
                """SELECT first_name, last_name, username, old_first_name, old_last_name, old_username,
                          changed_at, source_chat_id
                   FROM user_name_history
                   WHERE user_id = $1
                   ORDER BY changed_at DESC
                   LIMIT 50""",
                user_id
            )
            
            # Get current snapshot
            current = await conn.fetchrow(
                """SELECT first_name, last_name, username, captured_at
                   FROM user_snapshots
                   WHERE user_id = $1
                   ORDER BY captured_at DESC
                   LIMIT 1""",
                user_id
            )
        
        return {
            "user_id": user_id,
            "opted_out": False,
            "current": dict(current) if current else None,
            "history": [dict(h) for h in history],
            "change_count": len(history)
        }
    except Exception as e:
        logger.error(f"Failed to get user history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


@router.get("/me/language")
async def get_my_language(user: dict = Depends(get_current_user)):
    """Get current user's language preference."""
    user_id = user.get("id")
    
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT language_code FROM user_lang_prefs WHERE user_id = $1",
                user_id
            )
        
        from bot.utils.localization import SUPPORTED_LANGUAGES, DEFAULT_LANG
        
        lang_code = row["language_code"] if row else DEFAULT_LANG
        
        return {
            "language_code": lang_code,
            "language_name": SUPPORTED_LANGUAGES.get(lang_code, lang_code)
        }
    except Exception as e:
        logger.error(f"Failed to get user language: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch language")


@router.put("/me/language")
async def set_my_language(language_code: str, user: dict = Depends(get_current_user)):
    """Set current user's language preference."""
    user_id = user.get("id")
    
    from bot.utils.localization import SUPPORTED_LANGUAGES, set_user_language
    
    if language_code not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported language code")
    
    try:
        success = await set_user_language(db.pool, user_id, language_code)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to set language")
        
        return {
            "success": True,
            "language_code": language_code,
            "language_name": SUPPORTED_LANGUAGES[language_code]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set user language: {e}")
        raise HTTPException(status_code=500, detail="Failed to set language")


@router.get("/{user_id}/trust")
async def get_user_trust(user_id: int, user: dict = Depends(require_auth)):
    """Get trust score for a user."""
    try:
        async with db.pool.acquire() as conn:
            # Get reputation scores
            reps = await conn.fetch(
                """SELECT fr.score, f.name as federation_name, f.id as federation_id
                   FROM federation_reputation fr
                   JOIN federations f ON f.id = fr.federation_id
                   WHERE fr.user_id = $1""",
                user_id
            )
            
            # Get ban status
            bans = await conn.fetch(
                """SELECT fb.federation_id, fb.reason, fb.banned_at, fb.silent, f.name as federation_name
                   FROM federation_bans fb
                   JOIN federations f ON f.id = fb.federation_id
                   WHERE fb.user_id = $1""",
                user_id
            )
            
            # Calculate average score
            if reps:
                avg_score = sum(r["score"] for r in reps) / len(reps)
            else:
                avg_score = 50  # Default neutral
            
            # Determine level
            if avg_score >= 80:
                level = "trusted"
                level_emoji = "🟢"
            elif avg_score >= 60:
                level = "reliable"
                level_emoji = "🟡"
            elif avg_score >= 40:
                level = "neutral"
                level_emoji = "⚪"
            elif avg_score >= 20:
                level = "suspicious"
                level_emoji = "🟠"
            else:
                level = "untrusted"
                level_emoji = "🔴"
        
        return {
            "user_id": user_id,
            "trust_score": round(avg_score),
            "level": level,
            "level_emoji": level_emoji,
            "federation_scores": [
                {
                    "federation_id": str(r["federation_id"]),
                    "federation_name": r["federation_name"],
                    "score": r["score"]
                }
                for r in reps
            ],
            "federation_bans": [
                {
                    "federation_id": str(b["federation_id"]),
                    "federation_name": b["federation_name"],
                    "reason": b["reason"],
                    "banned_at": b["banned_at"].isoformat() if b["banned_at"] else None,
                    "silent": b["silent"]
                }
                for b in bans
            ],
            "ban_count": len(bans)
        }
    except Exception as e:
        logger.error(f"Failed to get trust score: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trust score")


@router.delete("/me/history")
async def delete_my_history(confirm: bool = False, user: dict = Depends(get_current_user)):
    """Delete current user's name history (GDPR compliance)."""
    user_id = user.get("id")
    
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Must pass confirm=true to delete history"
        )
    
    try:
        async with db.pool.acquire() as conn:
            # Delete history
            await conn.execute(
                "DELETE FROM user_name_history WHERE user_id = $1",
                user_id
            )
            
            # Delete snapshots
            await conn.execute(
                "DELETE FROM user_snapshots WHERE user_id = $1",
                user_id
            )
            
            # Auto opt-out
            await conn.execute(
                """INSERT INTO user_history_optout (user_id, reason)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO NOTHING""",
                user_id, "User deleted their data via API"
            )
        
        return {
            "success": True,
            "message": "Your name history has been permanently deleted",
            "opted_out": True
        }
    except Exception as e:
        logger.error(f"Failed to delete user history: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete history")


@router.get("/me/optout-status")
async def get_optout_status(user: dict = Depends(get_current_user)):
    """Get current user's opt-out status."""
    user_id = user.get("id")
    
    try:
        async with db.pool.acquire() as conn:
            optout = await conn.fetchrow(
                "SELECT opted_out_at, reason FROM user_history_optout WHERE user_id = $1",
                user_id
            )
        
        if optout:
            return {
                "opted_out": True,
                "opted_out_at": optout["opted_out_at"].isoformat() if optout["opted_out_at"] else None,
                "reason": optout["reason"]
            }
        else:
            return {
                "opted_out": False,
                "opted_out_at": None,
                "reason": None
            }
    except Exception as e:
        logger.error(f"Failed to get optout status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch optout status")


@router.post("/me/optout")
async def opt_out(user: dict = Depends(get_current_user)):
    """Opt out of name history tracking."""
    user_id = user.get("id")
    
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_history_optout (user_id, reason)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO NOTHING""",
                user_id, "User requested opt-out via API"
            )
        
        return {
            "success": True,
            "opted_out": True
        }
    except Exception as e:
        logger.error(f"Failed to opt out: {e}")
        raise HTTPException(status_code=500, detail="Failed to opt out")


@router.post("/me/optin")
async def opt_in(user: dict = Depends(get_current_user)):
    """Opt back into name history tracking."""
    user_id = user.get("id")
    
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM user_history_optout WHERE user_id = $1",
                user_id
            )
        
        return {
            "success": True,
            "opted_out": False
        }
    except Exception as e:
        logger.error(f"Failed to opt in: {e}")
        raise HTTPException(status_code=500, detail="Failed to opt in")
