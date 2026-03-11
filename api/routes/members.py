from fastapi import APIRouter, Depends
from api.auth import get_current_user
from db.client import db
import json

router = APIRouter(prefix="/api/groups/{chat_id}/members")

@router.get("")
async def list_members(chat_id: int, user: dict = Depends(get_current_user)):
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users WHERE chat_id = $1 ORDER BY last_seen DESC LIMIT 100", chat_id)
        res = []
        for r in rows:
            d = dict(r)
            if isinstance(d['warns'], str):
                d['warns'] = json.loads(d['warns'])
            res.append(d)
        return res
