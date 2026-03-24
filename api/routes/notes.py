"""
api/routes/notes.py

REST API for the notes system.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from api.routes.groups import _verify_group_access
from db.client import db
import db.ops.notes as notes_db

router = APIRouter(prefix="/api/groups/{chat_id}/notes", tags=["notes"])
logger = logging.getLogger(__name__)


class NoteRequest(BaseModel):
    name: str
    content: Optional[str] = None
    file_id: Optional[str] = None
    media_type: Optional[str] = None
    buttons: Optional[list] = None


@router.get("")
async def list_notes(chat_id: int, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    try:
        notes = await notes_db.get_notes(db.pool, chat_id)
        return {"ok": True, "data": notes}
    except Exception as e:
        logger.error(f"[Notes API] list_notes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}")
async def get_note(chat_id: int, name: str, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    try:
        note = await notes_db.get_note(db.pool, chat_id, name)
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"ok": True, "data": note}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Notes API] get_note error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_note(chat_id: int, req: NoteRequest, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    try:
        note = await notes_db.save_note(
            db.pool,
            chat_id,
            req.name.strip(),
            req.content,
            req.file_id,
            req.media_type,
            req.buttons or [],
            user.get("id", 0),
        )
        return {"ok": True, "data": note}
    except Exception as e:
        logger.error(f"[Notes API] create_note error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{name}")
async def delete_note(chat_id: int, name: str, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    try:
        deleted = await notes_db.delete_note(db.pool, chat_id, name)
        if not deleted:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Notes API] delete_note error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
