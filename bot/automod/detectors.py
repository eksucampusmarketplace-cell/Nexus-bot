"""
bot/automod/detectors.py

Content type detection + unofficial Telegram detection.
"""

import re
from datetime import time


def detect_content_type(msg) -> str:
    if msg.photo:       return "photo"
    if msg.video:       return "video"
    if msg.sticker:     return "sticker"
    if msg.animation:   return "animation"
    if msg.voice:       return "voice"
    if msg.audio:       return "audio"
    if msg.location:    return "location"
    if msg.contact:     return "contact"
    if msg.game:        return "game"
    if msg.poll:        return "poll"
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
        "api.gram", "tgplus", "mobi.telegram", "telegra.plus",
        "telegram.plus", "telegreat", "nicegram.app",
        "plus.telegram", "bgram", "gram.plus",
    ]
    text = (msg.text or msg.caption or "").lower()
    return any(sig in text for sig in UNOFFICIAL_SIGNATURES)


def is_in_time_window(
    current_time: time,
    start_str: str,
    end_str: str
) -> bool:
    """
    Check if current_time is within [start, end].
    Handles midnight-spanning windows (end < start).

    start_str, end_str: "HH:MM" strings
    """
    try:
        start = _parse_time(start_str)
        end   = _parse_time(end_str)
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
