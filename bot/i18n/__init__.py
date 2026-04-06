"""
bot/i18n/__init__.py

Internationalization (i18n) system for Nexus bot.
Uses strings from bot.utils.localization.
"""

from bot.utils.localization import STRINGS, DEFAULT_LANG, SUPPORTED_LANGUAGES

def t(key: str, lang: str = "en", **kwargs) -> str:
    """
    Translate a key to the specified language with format kwargs.
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANG

    # Get translations for the key
    translations = STRINGS.get(key)
    if not translations:
        # Fallback to key if not found
        return key

    # Get template for requested lang, fallback to English
    template = translations.get(lang, translations.get("en", key))

    # Format and return
    try:
        if kwargs:
            return template.format(**kwargs)
        return template
    except Exception:
        # If formatting fails, return template as-is
        return template

def get_available_languages() -> list:
    """Get list of available language codes."""
    return list(SUPPORTED_LANGUAGES.keys())

def add_translation(lang: str, key: str, value: str):
    """Add or update a translation at runtime."""
    if key not in STRINGS:
        STRINGS[key] = {}
    STRINGS[key][lang] = value
