"""
bot/i18n/__init__.py

Internationalization (i18n) system for Nexus bot.
Uses JSON locale files. Detects language from Telegram user.language_code.
"""

import json
import os
from pathlib import Path

_LOCALES: dict = {}
_LOCALE_DIR = Path(__file__).parent


def _load_locales():
    """Load all locale files from the i18n directory."""
    global _LOCALES
    for f in _LOCALE_DIR.glob("*.json"):
        lang = f.stem
        try:
            with open(f, encoding="utf-8") as fp:
                _LOCALES[lang] = json.load(fp)
        except Exception as e:
            print(f"[i18n] Error loading {f}: {e}")


# Load locales on module import
_load_locales()


def t(key: str, lang: str = "en", **kwargs) -> str:
    """
    Translate a key to the specified language with format kwargs.

    Args:
        key: Translation key (e.g., 'warn_issued')
        lang: Language code (e.g., 'en', 'es', 'fr')
        **kwargs: Format arguments for the translation string

    Returns:
        Translated string, or key itself if not found

    Usage:
        lang = getattr(update.effective_user, 'language_code', 'en')[:2]
        await message.reply_text(t('warn_issued', lang,
            user=user.first_name, count=warn_count, max=3, reason=reason))
    """
    # Use English as fallback
    base = _LOCALES.get("en", {})

    # Get locale (fallback to English)
    locale = _LOCALES.get(lang, base)

    # Get template (fallback to base, then to key)
    template = locale.get(key)
    if template is None:
        template = base.get(key, key)

    # Format and return
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # If formatting fails, return template as-is
        return template


def get_available_languages() -> list:
    """Get list of available language codes."""
    return list(_LOCALES.keys())


def add_translation(lang: str, key: str, value: str):
    """Add or update a translation at runtime."""
    if lang not in _LOCALES:
        _LOCALES[lang] = {}
    _LOCALES[lang][key] = value
