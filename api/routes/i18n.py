"""
api/routes/i18n.py

i18n API endpoint for the miniapp.
Returns all translated strings for a given language.
"""

from fastapi import APIRouter, HTTPException

from bot.utils.localization import STRINGS, SUPPORTED_LANGUAGES

router = APIRouter(prefix="/api/i18n")


@router.get("")
async def get_i18n_strings(lang: str = "en"):
    """
    Get all translated strings for a language.
    
    Returns:
        {
            "bot": {...},      # Bot message strings
            "ui": {...},       # UI strings
            "is_rtl": bool,    # True for Arabic
            "available_languages": {...}  # All supported languages
        }
    """
    # Normalize language code
    lang = lang.lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    # Build response
    bot_strings = {}
    for key, translations in STRINGS.items():
        bot_strings[key] = translations.get(lang, translations.get("en", key))

    # Extract UI strings (navigation, buttons, status, etc.)
    ui_keys = [
        # Navigation labels
        "nav_dashboard", "nav_bots", "nav_moderation", "nav_automod", 
        "nav_members", "nav_analytics", "nav_broadcast", "nav_reports",
        "nav_greetings", "nav_antiraid", "nav_settings", "nav_logs",
        "nav_roles", "nav_notes", "nav_xp", "nav_owner",
        # v21 navigation
        "nav_trustnet", "nav_captcha", "nav_community_vote", 
        "nav_night_mode", "nav_history", "nav_language", "nav_persona",
        # Buttons
        "save_btn", "cancel_btn", "enable_label", "disable_label",
        "delete", "edit", "confirm", "close", "refresh", "search",
        "copy", "copied", "reset", "add_bot", "add_clone",
        # Status
        "status_active", "status_inactive", "status_pending",
        "status_online", "status_offline", "status_live",
        # Moderation
        "action_ban", "action_kick", "action_mute", "action_warn", "action_delete",
        # AutoMod
        "antiflood", "antilink", "antispam", "blacklist_lbl", "locks_lbl",
        # Sections
        "section_general", "section_warnings", "section_captcha", "section_antiraid",
        # Time
        "minutes", "seconds", "hours", "days", "threshold_lbl", "timeout_lbl",
        # Page-specific
        "vote_threshold", "vote_action", "auto_detect_scams",
        "night_schedule", "night_start_lbl", "night_end_lbl", "timezone_lbl",
        "night_message_lbl", "morning_msg_lbl",
        "fed_name_lbl", "invite_code_lbl", "ban_propagation", "share_reputation",
        "my_lang_lbl", "group_lang_lbl", "auto_detected", "manual_override",
        # Toast messages
        "toast_save_success", "toast_delete_success", "toast_copy", "toast_no_group",
        "loading", "saved", "error", "select_group",
    ]
    
    ui_strings = {}
    for key in ui_keys:
        if key in STRINGS:
            ui_strings[key] = STRINGS[key].get(lang, STRINGS[key].get("en", key))

    return {
        "bot": bot_strings,
        "ui": ui_strings,
        "is_rtl": lang == "ar",
        "available_languages": SUPPORTED_LANGUAGES,
    }
