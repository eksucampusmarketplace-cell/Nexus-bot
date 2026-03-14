"""
crypto.py

Token security layer. All token storage and retrieval flows through here.

SECRET_KEY must be a valid Fernet key.
Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

NEVER log, print, or expose raw tokens anywhere in the codebase.
Use mask_token() whenever a token must appear in a log line.
"""

import os
import hashlib
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    key = os.getenv("SECRET_KEY")
    if not key:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode())
    except Exception as e:
        raise RuntimeError(f"SECRET_KEY is malformed: {e}")


def encrypt_token(token: str) -> str:
    """
    Encrypt a raw bot token for database storage.
    Returns a Fernet-encrypted string safe for storage.
    Never store the return value in a log.
    """
    encrypted = _get_fernet().encrypt(token.encode()).decode()
    logger.debug(f"Token encrypted successfully (hash={hash_token(token)[:8]}...)")
    return encrypted


def decrypt_token(encrypted: str) -> str:
    """
    Decrypt a stored token back to raw form.
    Raises ValueError if SECRET_KEY is wrong or data is corrupt.
    The decrypted value must NEVER be logged — use mask_token() instead.
    """
    try:
        raw = _get_fernet().decrypt(encrypted.encode()).decode()
        logger.debug("Token decrypted successfully")
        return raw
    except InvalidToken:
        raise ValueError(
            "Token decryption failed. "
            "This usually means SECRET_KEY was rotated or the stored value is corrupt."
        )


def hash_token(token: str) -> str:
    """
    SHA-256 hash of a raw token.
    Used for deduplication lookups in the DB.
    Safe to log and store — it is one-way and reveals nothing about the token.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def mask_token(token: str) -> str:
    """
    Safe representation for log lines.
    Shows first 8 characters and last 4, hides the middle.
    Example: "71234567...xYzW"
    """
    if len(token) < 16:
        return "***"
    return f"{token[:8]}...{token[-4:]}"


def validate_token_format(token: str) -> bool:
    """
    Quick regex-free format check before hitting Telegram API.
    Telegram bot tokens are: {bot_id}:{secret}
    - bot_id: numeric string (currently 8-12 digits)
    - secret: alphanumeric/hyphen/underscore (usually 35-50 chars)
    """
    import re

    # More permissive regex to handle newer/longer Telegram bot tokens
    return bool(re.match(r"^\d{8,12}:[\w-]{35,50}$", token))
