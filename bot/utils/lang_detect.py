"""
bot/utils/lang_detect.py

Language auto-detection engine for Nexus Bot v21.
Detects user language from:
1. Telegram language_code (highest priority if manually set)
2. Name character script (Arabic, Cyrillic, Devanagari, etc.)
3. Message text script
4. Group default language
5. English fallback

Zero API calls - all detection is local.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = {"en", "ar", "es", "fr", "hi", "pt", "ru", "tr", "id", "de"}

# Unicode block ranges for script detection
UNICODE_RANGES = {
    "arabic": [
        (0x0600, 0x06FF),   # Arabic
        (0x0750, 0x077F),   # Arabic Supplement
        (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
    ],
    "cyrillic": [
        (0x0400, 0x04FF),   # Cyrillic
        (0x0500, 0x052F),   # Cyrillic Supplement
    ],
    "devanagari": [
        (0x0900, 0x097F),   # Devanagari
    ],
}


def detect_from_telegram_code(language_code: Optional[str]) -> Optional[str]:
    """
    Detect language from Telegram's language_code (BCP-47 format).
    Maps codes like 'ar', 'ar-SA', 'en-US' to our supported languages.
    """
    if not language_code:
        return None

    # Extract primary language code (before any hyphen)
    primary_code = language_code.split("-")[0].lower()

    if primary_code in SUPPORTED_LANGUAGES:
        logger.debug(f"[LANG_DETECT] Telegram code '{language_code}' → '{primary_code}'")
        return primary_code

    return None


def _check_unicode_ranges(text: str, unicode_ranges: list) -> bool:
    """Check if text contains characters from any of the given Unicode ranges."""
    for char in text:
        code_point = ord(char)
        for start, end in unicode_ranges:
            if start <= code_point <= end:
                return True
    return False


def detect_from_text(text: str) -> Optional[str]:
    """
    Detect language from text character script.
    Uses Unicode block detection - zero API calls.
    """
    if not text:
        return None

    text = text.strip()
    if len(text) < 2:
        return None

    # Arabic script
    if _check_unicode_ranges(text, UNICODE_RANGES["arabic"]):
        logger.debug(f"[LANG_DETECT] Text script → 'ar'")
        return "ar"

    # Cyrillic script (Russian)
    if _check_unicode_ranges(text, UNICODE_RANGES["cyrillic"]):
        logger.debug(f"[LANG_DETECT] Text script → 'ru'")
        return "ru"

    # Devanagari script (Hindi)
    if _check_unicode_ranges(text, UNICODE_RANGES["devanagari"]):
        logger.debug(f"[LANG_DETECT] Text script → 'hi'")
        return "hi"

    # Turkish-specific characters
    turkish_chars = set("ğşıöçĞŞİÖÜ")
    if any(char in turkish_chars for char in text):
        logger.debug(f"[LANG_DETECT] Turkish chars detected → 'tr'")
        return "tr"

    # German ß (sharp s) - unique to German in our supported set
    if "ß" in text:
        logger.debug(f"[LANG_DETECT] German ß detected → 'de'")
        return "de"

    return None


def detect_from_name(first_name: Optional[str], last_name: Optional[str] = None) -> Optional[str]:
    """
    Detect language from user's name character script.
    Runs on user join instantly.
    """
    name_parts = []
    if first_name:
        name_parts.append(first_name)
    if last_name:
        name_parts.append(last_name)

    if not name_parts:
        return None

    full_name = " ".join(name_parts)
    return detect_from_text(full_name)


async def auto_detect_and_store(
    pool,
    user_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    language_code: Optional[str] = None,
    text: Optional[str] = None,
    chat_id: Optional[int] = None
) -> Optional[str]:
    """
    Auto-detect and store user's language preference.
    Only stores if no manual preference exists (auto_detected=FALSE).

    Detection priority:
    1. Telegram language_code
    2. Name script
    3. Message text script (if provided)
    4. Group default language
    5. English fallback

    Returns the detected language or None if manual preference exists.
    """
    try:
        # Check if user has a manual preference
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT language_code, auto_detected FROM user_lang_prefs WHERE user_id = $1",
                user_id
            )

            # If manual preference exists, don't override
            if row and not row.get("auto_detected", True):
                logger.debug(f"[LANG_DETECT] User {user_id} has manual pref '{row['language_code']}' - skipping")
                return row["language_code"]

        # Detect language
        detected_lang = None

        # 1. Telegram language_code
        if language_code:
            detected_lang = detect_from_telegram_code(language_code)

        # 2. Name script
        if not detected_lang and (first_name or last_name):
            detected_lang = detect_from_name(first_name, last_name)

        # 3. Message text script (if provided)
        if not detected_lang and text:
            detected_lang = detect_from_text(text)

        # 4. Group default language
        if not detected_lang and chat_id:
            try:
                async with pool.acquire() as conn:
                    group_row = await conn.fetchrow(
                        "SELECT settings->>'group_lang' as lang FROM groups WHERE chat_id = $1",
                        chat_id
                    )
                    if group_row and group_row["lang"] in SUPPORTED_LANGUAGES:
                        detected_lang = group_row["lang"]
                        logger.debug(f"[LANG_DETECT] Using group language '{detected_lang}'")
            except Exception as e:
                logger.debug(f"[LANG_DETECT] Failed to get group language: {e}")

        # 5. English fallback
        if not detected_lang:
            detected_lang = "en"
            logger.debug(f"[LANG_DETECT] No detection match - using English fallback")

        # Store with auto_detected=TRUE
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_lang_prefs (user_id, language_code, auto_detected)
                   VALUES ($1, $2, TRUE)
                   ON CONFLICT (user_id) DO UPDATE
                   SET language_code = EXCLUDED.language_code,
                       auto_detected = TRUE,
                       updated_at = NOW()
                   WHERE user_lang_prefs.auto_detected = TRUE""",
                user_id, detected_lang
            )

        logger.info(f"[LANG_DETECT] User {user_id} → '{detected_lang}' (auto)")
        return detected_lang

    except Exception as e:
        logger.error(f"[LANG_DETECT] Failed for user {user_id}: {e}")
        return None


async def get_user_lang(pool, user_id: int, chat_id: Optional[int] = None) -> str:
    """
    Get user's preferred language.
    Returns stored preference or auto-detects if not set.
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT language_code FROM user_lang_prefs WHERE user_id = $1",
                user_id
            )
            if row:
                return row["language_code"]
    except Exception as e:
        logger.debug(f"Failed to get user language: {e}")

    # Fallback to group language or English
    if chat_id:
        try:
            async with pool.acquire() as conn:
                group_row = await conn.fetchrow(
                    "SELECT settings->>'group_lang' as lang FROM groups WHERE chat_id = $1",
                    chat_id
                )
                if group_row and group_row["lang"] in SUPPORTED_LANGUAGES:
                    return group_row["lang"]
        except Exception:
            pass

    return "en"


async def set_lang_manual(pool, user_id: int, language_code: str) -> bool:
    """
    Set user's language manually (via /lang command).
    Sets auto_detected=FALSE to prevent auto-detection override.
    """
    if language_code not in SUPPORTED_LANGUAGES:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_lang_prefs (user_id, language_code, auto_detected)
                   VALUES ($1, $2, FALSE)
                   ON CONFLICT (user_id) DO UPDATE
                   SET language_code = EXCLUDED.language_code,
                       auto_detected = FALSE,
                       updated_at = NOW()""",
                user_id, language_code
            )
        logger.info(f"[LANG_DETECT] User {user_id} set manual pref '{language_code}'")
        return True
    except Exception as e:
        logger.error(f"[LANG_DETECT] Failed to set manual lang: {e}")
        return False


# Export
__all__ = [
    "detect_from_telegram_code",
    "detect_from_text",
    "detect_from_name",
    "auto_detect_and_store",
    "get_user_lang",
    "set_lang_manual",
    "SUPPORTED_LANGUAGES",
]
