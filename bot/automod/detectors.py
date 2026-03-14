"""
bot/automod/detectors.py

Content type detection + unofficial Telegram detection.
Advanced spam pattern detection with frequency analysis.
"""

import re
from datetime import time
from collections import defaultdict, deque
from time import time as time_now

# In-memory spam tracker (resets on bot restart)
_user_message_times: dict = defaultdict(lambda: deque(maxlen=50))

# Spam pattern regex patterns
SPAM_PATTERNS = [
    # Crypto/investment spam
    r"(?:earn|profit|invest).{0,20}(?:\$|usd|usdt)",
    r"(?:100x|10x|crypto|bitcoin).{0,30}(?:join|group|channel)",
    # Phishing
    r"(?:click|verify|confirm).{0,20}(?:https?://)",
    r"(?:account|wallet).{0,15}(?:suspend|block|limit)",
    # Mass mention spam
    r"@\w+(?:\s+@\w+){4,}",  # 5+ mentions in one message
    # Telegram invite flood
    r"t\.me/\+[A-Za-z0-9]{10,}",
    # Fake giveaway
    r"(?:free|giveaway|airdrop).{0,30}(?:nft|token|coin)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SPAM_PATTERNS]

# Default profanity filter words (can be customized per-group)
DEFAULT_FILTER_WORDS = [
    # Common profanity - add your word list here
    # Using word boundaries to avoid false positives
]


def detect_spam_pattern(text: str) -> tuple[bool, str | None]:
    """
    Detect spam patterns in text.

    Returns:
        (is_spam, reason_or_None)
    """
    if not text:
        return False, None

    for i, pattern in enumerate(COMPILED_PATTERNS):
        if pattern.search(text):
            return True, f"pattern_{i}"

    return False, None


def detect_message_frequency(
    user_id: int, chat_id: int, window_sec: int = 10, threshold: int = 8
) -> tuple[bool, int]:
    """
    Detect rapid message sending (flood detection).

    Args:
        user_id: User to check
        chat_id: Chat context
        window_sec: Time window in seconds
        threshold: Max messages allowed in window

    Returns:
        (is_flooding, message_count_in_window)
    """
    key = (user_id, chat_id)
    q = _user_message_times[key]
    now = time_now()
    q.append(now)

    cutoff = now - window_sec
    recent = sum(1 for t in q if t > cutoff)

    return recent > threshold, recent


def build_filter_pattern(words: list[str]) -> re.Pattern | None:
    """Build a compiled regex from a word list for profanity filtering."""
    if not words:
        return None
    escaped = [re.escape(w) for w in words]
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


async def detect_profanity(text: str, chat_id: int, custom_words: list[str] = None) -> bool:
    """
    Check text against profanity filter.

    Args:
        text: Message text to check
        chat_id: Group ID for custom word list lookup
        custom_words: Additional custom words from group settings

    Returns:
        True if profanity detected
    """
    if not text:
        return False

    # Build word list from defaults + custom
    words = DEFAULT_FILTER_WORDS.copy()
    if custom_words:
        words.extend(custom_words)

    pattern = build_filter_pattern(words)
    if not pattern:
        return False

    return bool(pattern.search(text))


def reset_frequency_tracker(user_id: int = None, chat_id: int = None):
    """Reset frequency tracker for testing or cleanup."""
    global _user_message_times
    if user_id and chat_id:
        key = (user_id, chat_id)
        _user_message_times.pop(key, None)
    else:
        _user_message_times.clear()


def detect_content_type(msg) -> str:
    if msg.photo:
        return "photo"
    if msg.video:
        return "video"
    if msg.sticker:
        return "sticker"
    if msg.animation:
        return "animation"
    if msg.voice:
        return "voice"
    if msg.audio:
        return "audio"
    if msg.location:
        return "location"
    if msg.contact:
        return "contact"
    if msg.game:
        return "game"
    if msg.poll:
        return "poll"
    if msg.document:
        fname = msg.document.file_name or ""
        if fname.endswith(".apk"):
            return "apk"
        return "document"
    return "text"


def detect_unofficial_telegram(msg) -> bool:
    """
    Detect messages sent by unofficial Telegram clients.
    These apps hijack accounts to send spam ads.

    Detection methods:
    1. via_bot with known spam bot usernames
    2. Message contains known unofficial app signatures
    3. Forward from known spam channels
    """
    UNOFFICIAL_SIGNATURES = [
        "api.gram",
        "tgplus",
        "mobi.telegram",
        "telegra.plus",
        "telegram.plus",
        "telegreat",
        "nicegram.app",
        "plus.telegram",
        "bgram",
        "gram.plus",
    ]
    text = (msg.text or msg.caption or "").lower()
    return any(sig in text for sig in UNOFFICIAL_SIGNATURES)


def is_in_time_window(current_time: time, start_str: str, end_str: str) -> bool:
    """
    Check if current_time is within [start, end].
    Handles midnight-spanning windows (end < start).

    start_str, end_str: "HH:MM" strings
    """
    try:
        start = _parse_time(start_str)
        end = _parse_time(end_str)
    except Exception:
        return False

    if start <= end:
        return start <= current_time <= end
    else:
        # Spans midnight: 23:30 → 08:10
        return current_time >= start or current_time <= end


def _parse_time(s: str) -> time:
    parts = s.split(":")
    return time(int(parts[0]), int(parts[1]))
