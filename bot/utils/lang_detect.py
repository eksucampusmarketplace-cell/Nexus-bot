"""
bot/utils/lang_detect.py

Language auto-detection engine for Nexus Bot v21.
Supports detection from:
1. Telegram language_code (highest priority for auto-detect)
2. Name character script (Arabic, Cyrillic, Devanagari, Turkish, German)
3. Message text script (passive detection)

Priority order:
1. Manual preference via /lang (stored with auto_detected=FALSE, NEVER overridden)
2. Telegram language_code (most reliable signal)
3. Name character script (runs on join)
4. Message text script (passive, runs on every message)
5. Group default language (fallback)
6. English (final fallback)

Zero API calls - all detection uses Unicode block analysis.
"""

import logging
import re
from typing import Optional, Tuple

from bot.utils.localization import SUPPORTED_LANGUAGES, DEFAULT_LANG

log = logging.getLogger("lang_detect")

# Telegram language code to supported language mapping
TELEGRAM_LANG_MAP = {
    # Arabic
    "ar": "ar",
    "ar-SA": "ar", "ar-AE": "ar", "ar-EG": "ar", "ar-SA": "ar",
    # Spanish
    "es": "es", "es-ES": "es", "es-MX": "es", "es-419": "es",
    # French
    "fr": "fr", "fr-FR": "fr", "fr-CA": "fr",
    # Hindi
    "hi": "hi", "hi-IN": "hi",
    # Portuguese
    "pt": "pt", "pt-BR": "pt", "pt-PT": "pt",
    # Russian
    "ru": "ru", "ru-RU": "ru", "ru-UA": "ru",
    # Turkish
    "tr": "tr", "tr-TR": "tr",
    # Indonesian
    "id": "id", "id-ID": "id",
    # German
    "de": "de", "de-DE": "de", "de-AT": "de", "de-CH": "de",
    # English
    "en": "en", "en-US": "en", "en-GB": "en", "en-AU": "en", "en-CA": "en",
    # Thai
    "th": "th", "th-TH": "th",
}

# Unicode block ranges for script detection
SCRIPTS = {
    "ar": {
        "name": "Arabic",
        "ranges": [
            (0x0600, 0x06FF),    # Arabic
            (0x0750, 0x077F),    # Arabic Supplement
            (0xFB50, 0xFDFF),    # Arabic Presentation Forms-A
            (0xFE70, 0xFEFF),    # Arabic Presentation Forms-B
        ],
    },
    "ru": {
        "name": "Cyrillic",
        "ranges": [
            (0x0400, 0x04FF),    # Cyrillic
            (0x0500, 0x052F),    # Cyrillic Supplement
            (0x2DE0, 0x2DFF),    # Cyrillic Extended-A
            (0xA640, 0xA69F),    # Cyrillic Extended-B
        ],
    },
    "hi": {
        "name": "Devanagari",
        "ranges": [
            (0x0900, 0x097F),    # Devanagari
            (0xA8E0, 0xA8FF),    # Devanagari Extended
        ],
    },
    "th": {
        "name": "Thai",
        "ranges": [
            (0x0E00, 0x0E7F),    # Thai
        ],
    },
}

# Turkish-specific characters (Latin-based but unique to Turkish)
TURKISH_CHARS = set("ğşıöüÇĞŞİÖÜ")

# German-specific: ß (unique to German among supported languages)
GERMAN_CHARS = set("ß")


def detect_from_telegram_code(lang_code: Optional[str]) -> Optional[str]:
    """
    Detect language from Telegram's language_code.
    Telegram sends this with every message and on user join.
    Maps BCP-47 codes (ar, ar-SA, en-US, fr, etc.) to supported languages.
    
    Args:
        lang_code: Telegram language code (e.g., 'en-US', 'ar', 'fr')
    
    Returns:
        Supported language code or None
    """
    if not lang_code:
        return None
    
    lang_code = lang_code.lower().strip()
    
    # Direct match
    if lang_code in TELEGRAM_LANG_MAP:
        detected = TELEGRAM_LANG_MAP[lang_code]
        log.debug(f"[LANG_DETECT] Telegram code '{lang_code}' -> {detected}")
        return detected
    
    # Try prefix match (e.g., 'en-GB' -> 'en')
    prefix = lang_code.split("-")[0]
    if prefix in TELEGRAM_LANG_MAP:
        detected = TELEGRAM_LANG_MAP[prefix]
        log.debug(f"[LANG_DETECT] Telegram code '{lang_code}' (prefix '{prefix}') -> {detected}")
        return detected
    
    log.debug(f"[LANG_DETECT] Unknown Telegram code: {lang_code}")
    return None


def _has_char_in_range(char: str, start: int, end: int) -> bool:
    """Check if a character's code point is in a range."""
    try:
        code = ord(char)
        return start <= code <= end
    except (ValueError, TypeError):
        return False


def _detect_script(text: str) -> Optional[str]:
    """
    Detect script from text using Unicode blocks.
    
    Args:
        text: String to analyze (name or message text)
    
    Returns:
        Language code based on dominant script or None
    """
    if not text or not isinstance(text, str):
        return None
    
    # Clean the text - take first 100 chars for performance
    text = text.strip()[:100]
    if not text:
        return None
    
    # Count script occurrences
    script_counts = {"ar": 0, "ru": 0, "hi": 0, "tr": 0, "de": 0}
    total_chars = 0
    
    for char in text:
        # Skip non-printable and whitespace
        if char.isspace() or not char.isprintable():
            continue
        
        total_chars += 1
        
        # Check Arabic
        for start, end in SCRIPTS["ar"]["ranges"]:
            if _has_char_in_range(char, start, end):
                script_counts["ar"] += 1
                break
        else:
            # Check Cyrillic
            for start, end in SCRIPTS["ru"]["ranges"]:
                if _has_char_in_range(char, start, end):
                    script_counts["ru"] += 1
                    break
            else:
                # Check Devanagari
                for start, end in SCRIPTS["hi"]["ranges"]:
                    if _has_char_in_range(char, start, end):
                        script_counts["hi"] += 1
                        break
                else:
                    # Check Turkish-specific Latin chars
                    if char in TURKISH_CHARS:
                        script_counts["tr"] += 1
                    # Check German ß
                    elif char in GERMAN_CHARS:
                        script_counts["de"] += 1
    
    # Need at least 30% of characters to be in a script for detection
    if total_chars < 3:
        return None
    
    threshold = max(1, total_chars * 0.3)
    
    for script, count in script_counts.items():
        if count >= threshold:
            log.debug(f"[LANG_DETECT] Script '{script}' detected: {count}/{total_chars} chars")
            return script
    
    return None


def detect_from_name(first_name: Optional[str] = None, last_name: Optional[str] = None) -> Optional[str]:
    """
    Detect language from user's name using Unicode script analysis.
    
    Arabic script in first_name/last_name -> ar
    Cyrillic -> ru  
    Devanagari -> hi
    Turkish special chars (ğ,ş,ı,ö,ü,ç) -> tr
    German ß -> de
    
    Args:
        first_name: User's first name
        last_name: User's last name (optional)
    
    Returns:
        Detected language code or None
    """
    name_parts = [first_name, last_name]
    full_name = " ".join(part for part in name_parts if part)
    
    if not full_name:
        return None
    
    detected = _detect_script(full_name)
    if detected:
        log.debug(f"[LANG_DETECT] Name script detection: '{full_name[:30]}' -> {detected}")
    
    return detected


def detect_from_text(text: Optional[str] = None) -> Optional[str]:
    """
    Detect language from message text using Unicode script analysis.
    Used for passive detection on every message.
    
    Catches users whose name is Latin but who type in Arabic/Russian.
    
    Args:
        text: Message text or caption
    
    Returns:
        Detected language code or None
    """
    if not text:
        return None
    
    detected = _detect_script(text)
    if detected:
        log.debug(f"[LANG_DETECT] Message text detection -> {detected}")
    
    return detected


def detect_from_bio(bio: Optional[str] = None) -> Optional[str]:
    """
    Detect language from user's bio using Unicode script analysis.
    
    Args:
        bio: User's bio text
    
    Returns:
        Detected language code or None
    """
    if not bio:
        return None
    
    detected = _detect_script(bio)
    if detected:
        log.debug(f"[LANG_DETECT] Bio script detection: '{bio[:50]}...' -> {detected}")
    
    return detected


def detect_from_group_description(description: Optional[str] = None) -> Optional[str]:
    """
    Detect language from group description using Unicode script analysis.
    
    Args:
        description: Group description text
    
    Returns:
        Detected language code or None
    """
    if not description:
        return None
    
    detected = _detect_script(description)
    if detected:
        log.debug(f"[LANG_DETECT] Group description script detection -> {detected}")
    
    return detected


async def auto_detect_and_store(db, user_id: int, chat_id: Optional[int] = None,
                                telegram_code: Optional[str] = None,
                                first_name: Optional[str] = None,
                                last_name: Optional[str] = None,
                                bio: Optional[str] = None,
                                message_text: Optional[str] = None,
                                group_description: Optional[str] = None) -> Optional[str]:
    """
    Main auto-detection function.
    
    Priority order:
    1. Manual preference (auto_detected=FALSE) - NEVER overridden
    2. Telegram language_code (most reliable)
    3. Name script detection
    4. Bio script detection
    5. Message text script (passive detection)
    6. Group description script detection (for new groups)
    7. Group default language (fallback)
    8. English (final fallback)
    
    Args:
        db: Database connection pool
        user_id: User ID
        chat_id: Group ID (for group fallback)
        telegram_code: Telegram's language_code from the message/join event
        first_name: User's first name
        last_name: User's last name
        bio: User's bio/about text
        message_text: Message text (for passive detection)
        group_description: Group description (for initial group language detection)
    
    Returns:
        The detected/stored language code
    """
    if not db:
        log.warning("[LANG_DETECT] No DB pool, returning default")
        return DEFAULT_LANG
    
    try:
        async with db.acquire() as conn:
            # STEP 1: Check for existing manual preference
            # Manual preferences (auto_detected=FALSE) are NEVER overridden
            existing = await conn.fetchrow(
                "SELECT language_code, auto_detected FROM user_lang_prefs WHERE user_id = $1",
                user_id
            )
            
            if existing and existing["auto_detected"] is False:
                log.debug(f"[LANG_DETECT] User {user_id} has manual preference: {existing['language_code']}")
                return existing["language_code"]
            
            # STEP 2: Try Telegram language_code (most reliable)
            detected_lang = detect_from_telegram_code(telegram_code)
            
            # STEP 3: Try name script detection
            if not detected_lang:
                detected_lang = detect_from_name(first_name, last_name)
            
            # STEP 4: Try bio script detection
            if not detected_lang and bio:
                detected_lang = detect_from_bio(bio)
            
            # STEP 5: Try message text script (passive)
            if not detected_lang and message_text:
                detected_lang = detect_from_text(message_text)
            
            # STEP 6: Try group description script detection
            if not detected_lang and group_description:
                detected_lang = detect_from_group_description(group_description)
            
            # STEP 7: Fall back to group default language
            if not detected_lang and chat_id:
                try:
                    row = await conn.fetchrow(
                        "SELECT settings->>'default_language' as lang FROM groups WHERE chat_id = $1",
                        chat_id
                    )
                    if row and row["lang"]:
                        detected_lang = row["lang"]
                        log.debug(f"[LANG_DETECT] Using group language: {detected_lang}")
                except Exception as e:
                    log.debug(f"[LANG_DETECT] Failed to get group language: {e}")
            
            # STEP 8: Final fallback to English
            if not detected_lang or detected_lang not in SUPPORTED_LANGUAGES:
                detected_lang = DEFAULT_LANG
            
            # Store/update the language preference
            if existing:
                # Update existing row (was auto-detected or new)
                await conn.execute(
                    """UPDATE user_lang_prefs 
                       SET language_code = $1, auto_detected = TRUE, updated_at = NOW()
                       WHERE user_id = $2 AND auto_detected IS NOT FALSE""",
                    detected_lang, user_id
                )
            else:
                # Insert new row
                await conn.execute(
                    """INSERT INTO user_lang_prefs (user_id, language_code, auto_detected)
                       VALUES ($1, $2, TRUE)
                       ON CONFLICT (user_id) DO NOTHING""",
                    user_id, detected_lang
                )
            
            log.info(f"[LANG_DETECT] User {user_id} language detected: {detected_lang} (auto_detected=TRUE)")
            return detected_lang
            
    except Exception as e:
        log.error(f"[LANG_DETECT] Detection failed for user {user_id}: {e}")
        return DEFAULT_LANG


async def set_user_lang_manual(db, user_id: int, language_code: str) -> bool:
    """
    Set user's language preference manually (via /lang command).
    This sets auto_detected=FALSE, which means auto-detection will NEVER override it.
    
    Args:
        db: Database connection pool
        user_id: User ID
        language_code: Language code to set
    
    Returns:
        True if successful
    """
    if language_code not in SUPPORTED_LANGUAGES:
        log.warning(f"[LANG_DETECT] Invalid language code: {language_code}")
        return False
    
    if not db:
        log.warning("[LANG_DETECT] No DB pool, cannot set manual preference")
        return False
    
    try:
        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_lang_prefs (user_id, language_code, auto_detected)
                   VALUES ($1, $2, FALSE)
                   ON CONFLICT (user_id) DO UPDATE 
                   SET language_code = EXCLUDED.language_code, 
                       auto_detected = FALSE, 
                       updated_at = NOW()""",
                user_id, language_code
            )
        
        log.info(f"[LANG_DETECT] User {user_id} set manual language: {language_code} (auto_detected=FALSE)")
        return True
        
    except Exception as e:
        log.error(f"[LANG_DETECT] Failed to set manual language for {user_id}: {e}")
        return False


# Export
__all__ = [
    "detect_from_telegram_code",
    "detect_from_name",
    "detect_from_text",
    "detect_from_bio",
    "detect_from_group_description",
    "auto_detect_and_store",
    "set_user_lang_manual",
]
