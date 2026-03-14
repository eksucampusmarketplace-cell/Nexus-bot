"""
bot/userbot/music_auth.py

Handles adding a Pyrogram userbot account for music streaming.
Three methods: phone+OTP, QR code, session string.
Used by both the /adduserbot command and the Mini App API.

Flow (phone+OTP):
  1. User provides phone number
  2. Pyrogram sends OTP to that Telegram account
  3. User provides OTP code
  4. Optional: 2FA password if account has it
  5. Session string extracted, encrypted, saved to music_userbots table
  6. MusicWorker reloaded with new client

Flow (QR code):
  1. Generate QR login token via Pyrogram
  2. Render as PNG using qrcode library
  3. Send image to user
  4. Poll until scanned (30s timeout, refresh every 8s)
  5. Session string extracted, saved

Flow (session string):
  1. User pastes existing Pyrogram session string
  2. Validate by calling get_me()
  3. Save to DB if valid

All methods:
  - Encrypt session string with Fernet before saving (same as clone token encryption)
  - Validate account is not a bot account
  - Validate account is not already added
  - Return UserbotAuthResult(ok, error, tg_user_id, tg_name, session_string)

Logs prefix: [MUSIC_AUTH]
"""

import logging
import io
import asyncio
from dataclasses import dataclass
from typing import Optional

from pyrogram import Client
from pyrogram.errors import (
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait,
)
import qrcode

from config import settings
from bot.utils.crypto import encrypt_token, decrypt_token

log = logging.getLogger("music_auth")


@dataclass
class UserbotAuthResult:
    ok: bool
    error: str = ""
    tg_user_id: int = 0
    tg_name: str = ""
    tg_username: str = ""
    session_string: str = ""  # encrypted


class MusicAuthSession:
    """
    Holds in-progress auth state for one user.
    Stored in context.user_data["music_auth"] during conversation.
    """

    def __init__(self, owner_bot_id: int):
        self.owner_bot_id = owner_bot_id
        self.client: Optional[Client] = None
        self.phone: str = ""
        self.phone_hash: str = ""
        self.method: str = ""  # phone|qr|session


async def start_phone_auth(session: MusicAuthSession, phone: str) -> UserbotAuthResult:
    """Step 1 of phone auth: send OTP."""
    phone = phone.strip().replace(" ", "")
    session.phone = phone
    session.method = "phone"

    client = Client(
        name=f"music_auth_{phone}",
        api_id=settings.PYROGRAM_API_ID,
        api_hash=settings.PYROGRAM_API_HASH,
        in_memory=True,
    )

    try:
        await client.connect()
        sent = await client.send_code(phone)
        session.phone_hash = sent.phone_code_hash
        session.client = client
        log.info(f"[MUSIC_AUTH] OTP sent | phone={phone[:6]}***")
        return UserbotAuthResult(ok=True)
    except PhoneNumberInvalid:
        await client.disconnect()
        return UserbotAuthResult(ok=False, error="Invalid phone number.")
    except FloodWait as e:
        await client.disconnect()
        return UserbotAuthResult(ok=False, error=f"Too many attempts. Wait {e.value}s.")
    except Exception as e:
        await client.disconnect()
        return UserbotAuthResult(ok=False, error=str(e))


async def complete_phone_auth(
    session: MusicAuthSession, code: str, password: str = ""
) -> UserbotAuthResult:
    """Step 2 of phone auth: verify OTP (and optional 2FA password)."""
    client = session.client
    if not client:
        return UserbotAuthResult(ok=False, error="Auth session expired. Start over.")

    try:
        await client.sign_in(session.phone, session.phone_hash, code.strip())
    except SessionPasswordNeeded:
        if not password:
            return UserbotAuthResult(ok=False, error="2FA_REQUIRED")
        try:
            await client.check_password(password)
        except PasswordHashInvalid:
            return UserbotAuthResult(ok=False, error="Wrong 2FA password.")
    except PhoneCodeInvalid:
        return UserbotAuthResult(ok=False, error="Wrong code. Try again.")
    except Exception as e:
        return UserbotAuthResult(ok=False, error=str(e))

    return await _finalize(client, session.owner_bot_id)


async def start_qr_auth(session: MusicAuthSession) -> UserbotAuthResult:
    """
    Generate a QR code login.
    Returns UserbotAuthResult with data containing PNG bytes in error field
    (caller sends image to user) — if ok=True, QR is ready, poll with check_qr_auth().
    This is a simplified flow: returns the QR image bytes for the caller to send.
    """
    session.method = "qr"
    client = Client(
        name=f"music_qr_{id(session)}",
        api_id=settings.PYROGRAM_API_ID,
        api_hash=settings.PYROGRAM_API_HASH,
        in_memory=True,
    )

    try:
        await client.connect()
        qr_login = await client.qr_login()
        session.client = client
        session._qr_login = qr_login

        # Generate QR image
        img = qrcode.make(qr_login.url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        log.info(f"[MUSIC_AUTH] QR generated")
        return UserbotAuthResult(ok=True, error="QR_IMAGE", session_string=buf.getvalue().hex())
        # Caller uses session_string field to get image bytes: bytes.fromhex(result.session_string)

    except Exception as e:
        await client.disconnect()
        return UserbotAuthResult(ok=False, error=str(e))


async def check_qr_auth(session: MusicAuthSession, timeout: int = 30) -> UserbotAuthResult:
    """Poll until QR is scanned or timeout."""
    client = session.client
    qr_login = getattr(session, "_qr_login", None)
    if not client or not qr_login:
        return UserbotAuthResult(ok=False, error="No QR session active.")

    try:
        await asyncio.wait_for(qr_login.wait(), timeout=timeout)
        return await _finalize(client, session.owner_bot_id)
    except asyncio.TimeoutError:
        return UserbotAuthResult(ok=False, error="QR expired. Try again.")
    except Exception as e:
        return UserbotAuthResult(ok=False, error=str(e))


async def session_string_auth(owner_bot_id: int, session_str: str) -> UserbotAuthResult:
    """Validate and save a pasted Pyrogram session string."""
    client = Client(
        name="music_session_validate",
        api_id=settings.PYROGRAM_API_ID,
        api_hash=settings.PYROGRAM_API_HASH,
        session_string=session_str.strip(),
        in_memory=True,
    )
    try:
        await client.connect()
        return await _finalize(client, owner_bot_id)
    except Exception as e:
        return UserbotAuthResult(ok=False, error=f"Invalid session: {e}")


async def _finalize(client: Client, owner_bot_id: int) -> UserbotAuthResult:
    """Extract session string, validate not a bot, encrypt, return result."""
    try:
        me = await client.get_me()

        if me.is_bot:
            await client.disconnect()
            return UserbotAuthResult(
                ok=False, error="This is a bot account. Use a real user account."
            )

        raw_session = await client.export_session_string()
        await client.disconnect()

        encrypted = encrypt_token(raw_session)  # reuse existing Fernet encrypt

        log.info(f"[MUSIC_AUTH] Finalized | user={me.id} name={me.first_name}")
        return UserbotAuthResult(
            ok=True,
            tg_user_id=me.id,
            tg_name=f"{me.first_name} {me.last_name or ''}".strip(),
            tg_username=me.username or "",
            session_string=encrypted,
        )
    except Exception as e:
        return UserbotAuthResult(ok=False, error=str(e))
