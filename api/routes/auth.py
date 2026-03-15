"""
api/routes/auth.py

POST /api/auth/validate-session
  Receives browser-generated session data.
  Converts to Pyrogram StringSession format.
  Validates by calling get_me() — rejects bots, banned accounts.
  Encrypts and stores in music_userbots table.
  Reloads MusicWorker for the clone bot.

The browser session format (base64 JSON) differs from Pyrogram StringSession.
This endpoint handles the conversion using Pyrogram's storage internals.

Logs prefix: [AUTH]
"""

import base64
import json
import logging

from fastapi import APIRouter, HTTPException, Request

try:
    from pyrogram import Client
    from pyrogram.storage import MemoryStorage

    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False
    Client = None
    MemoryStorage = None

from bot.utils.crypto import encrypt_token
from config import settings

try:
    from db.ops.music_new import save_music_userbot

    MUSIC_NEW_AVAILABLE = True
except ImportError:
    MUSIC_NEW_AVAILABLE = False
    save_music_userbot = None

from bot.registry import get

try:
    from bot.userbot.music_worker import MusicWorker

    MUSIC_WORKER_AVAILABLE = True
except ImportError:
    MUSIC_WORKER_AVAILABLE = False
    MusicWorker = None

log = logging.getLogger("auth_api")
router = APIRouter()


@router.post("/api/auth/validate-session")
async def validate_session(request: Request):
    """
    Validate a browser-generated MTProto session and store it.

    Accepts two formats:
      1. Browser session JSON (from MtprotoAuth._exportSession)
         { session_string: "<base64 JSON with dc_id, auth_key, user_id>" }

      2. Raw Pyrogram StringSession string
         { session_string: "<standard Pyrogram session string>" }

    Steps:
      1. Detect format
      2. Convert to Pyrogram StringSession if needed
      3. Start Pyrogram client, call get_me()
      4. Verify: not a bot, not banned
      5. Encrypt session string
      6. Save to music_userbots
      7. Reload MusicWorker for the clone
    """
    if not PYROGRAM_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Pyrogram is not installed. Session validation is unavailable.",
        )

    if not MUSIC_NEW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Music module is not available.",
        )

    owner_id = request.state.user_id
    db = request.app.state.db
    body = await request.json()
    raw = body.get("session_string", "").strip()
    bot_id = body.get("bot_id", 0)

    if not raw:
        raise HTTPException(status_code=400, detail="session_string required")

    log.info(f"[AUTH] Validating session | owner={owner_id} bot={bot_id}")

    # Detect and convert format
    pyrogram_session = await _to_pyrogram_session(raw)
    if not pyrogram_session:
        raise HTTPException(status_code=400, detail="Invalid session format")

    # Validate via Pyrogram
    try:
        client = Client(
            name=f"validate_{owner_id}",
            api_id=settings.PYROGRAM_API_ID,
            api_hash=settings.PYROGRAM_API_HASH,
            session_string=pyrogram_session,
            in_memory=True,
        )
        await client.connect()
        me = await client.get_me()
        await client.disconnect()
    except Exception as e:
        log.warning(f"[AUTH] Validation failed | owner={owner_id} error={e}")
        raise HTTPException(status_code=400, detail=f"Session invalid: {str(e)[:100]}")

    if me.is_bot:
        raise HTTPException(status_code=400, detail="Bot accounts cannot be used as userbots.")

    # Encrypt and save
    encrypted = encrypt_token(pyrogram_session)
    await save_music_userbot(
        db,
        owner_bot_id=bot_id,
        tg_user_id=me.id,
        tg_name=f"{me.first_name} {me.last_name or ''}".strip(),
        tg_username=me.username or "",
        encrypted_session=encrypted,
    )

    # Reload MusicWorker for this clone
    await _reload_music_worker(bot_id, pyrogram_session, db)

    log.info(f"[AUTH] Session saved | owner={owner_id} bot={bot_id} user={me.id}")
    return {
        "ok": True,
        "user": {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name or "",
            "username": me.username or "",
        },
    }


async def _to_pyrogram_session(raw: str) -> str | None:
    """
    Convert browser session format to Pyrogram StringSession.
    Returns None if format unrecognized.
    """
    # Try: browser JSON format (base64 encoded JSON)
    try:
        decoded = base64.b64decode(raw + "==").decode("utf-8")
        data = json.loads(decoded)

        if all(k in data for k in ("dc_id", "auth_key", "user_id")):
            # Build Pyrogram StringSession from browser session data
            # Pyrogram StringSession format:
            # base64( version(1 byte) + dc_id(1 byte) +
            #         auth_key_id(8 bytes) + ... )
            # Simplest approach: create MemoryStorage and populate it
            storage = MemoryStorage(":memory:")
            await storage.open()
            await storage.dc_id(data["dc_id"])
            await storage.auth_key(bytes(data["auth_key"]))
            await storage.user_id(data["user_id"])
            await storage.is_bot(False)
            session_str = await storage.export_session_string()
            await storage.close()
            return session_str
    except Exception:
        pass

    # Try: raw Pyrogram StringSession (already correct format)
    if len(raw) > 50 and raw.replace("+", "").replace("/", "").replace("=", "").isalnum():
        return raw

    return None


async def _reload_music_worker(bot_id: int, session_string: str, db):
    """Reload the MusicWorker for a clone bot after new session added."""
    if not PYROGRAM_AVAILABLE or not MUSIC_WORKER_AVAILABLE:
        log.warning(f"[AUTH] Cannot reload MusicWorker - dependencies not available")
        return

    try:
        clone_app = get(bot_id)
        if not clone_app:
            return

        pyro = Client(
            name=f"music_{bot_id}",
            api_id=settings.PYROGRAM_API_ID,
            api_hash=settings.PYROGRAM_API_HASH,
            session_string=session_string,
            in_memory=True,
        )
        await pyro.start()
        worker = MusicWorker(pyro, bot_id, db)
        await worker.start()
        clone_app.bot_data["music_worker"] = worker
        log.info(f"[AUTH] MusicWorker reloaded | bot={bot_id}")
    except Exception as e:
        log.warning(f"[AUTH] MusicWorker reload failed | bot={bot_id} error={e}")
