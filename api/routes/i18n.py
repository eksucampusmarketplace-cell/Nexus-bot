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

    # UI strings (for now, return basic set - expand as needed)
    ui_strings = {
        # Navigation
        "nav_trustnet": "TrustNet" if lang == "en" else "TrustNet",
        "nav_captcha": "Captcha" if lang == "en" else "Captcha",
        "nav_community_vote": "Community Vote" if lang == "en" else "Community Vote",
        "nav_night_mode": "Night Mode" if lang == "en" else "Night Mode",
        "nav_history": "Name History" if lang == "en" else "Name History",
        "nav_language": "Language" if lang == "en" else "Language",
        "nav_persona": "Bot Persona" if lang == "en" else "Bot Persona",
        
        # Buttons
        "save_btn": "Save" if lang == "en" else "Save",
        "cancel_btn": "Cancel" if lang == "en" else "Cancel",
        "enable_label": "Enable" if lang == "en" else "Enable",
        "disable_label": "Disable" if lang == "en" else "Disable",
        "delete": "Delete" if lang == "en" else "Delete",
        "edit": "Edit" if lang == "en" else "Edit",
        "confirm": "Confirm" if lang == "en" else "Confirm",
        "close": "Close" if lang == "en" else "Close",
        "refresh": "Refresh" if lang == "en" else "Refresh",
        "search": "Search" if lang == "en" else "Search",
        "copy": "Copy" if lang == "en" else "Copy",
        "copied": "Copied!" if lang == "en" else "Copied!",
        "reset": "Reset" if lang == "en" else "Reset",
        "add_bot": "Add Bot" if lang == "en" else "Add Bot",
        "add_clone": "Add Clone" if lang == "en" else "Add Clone",
        
        # Status
        "status_active": "Active" if lang == "en" else "Active",
        "status_inactive": "Inactive" if lang == "en" else "Inactive",
        "status_pending": "Pending" if lang == "en" else "Pending",
        "status_online": "Online" if lang == "en" else "Online",
        "status_offline": "Offline" if lang == "en" else "Offline",
        "status_live": "Live" if lang == "en" else "Live",
        
        # Common
        "loading": "Loading..." if lang == "en" else "Loading...",
        "saved": "Saved!" if lang == "en" else "Saved!",
        "error": "Error" if lang == "en" else "Error",
        "select_group": "Select a group" if lang == "en" else "Select a group",
        
        # Toast messages
        "toast_save_success": "Saved successfully!" if lang == "en" else "Saved successfully!",
        "toast_delete_success": "Deleted successfully!" if lang == "en" else "Deleted successfully!",
        "toast_copy": "Copied to clipboard!" if lang == "en" else "Copied to clipboard!",
        "toast_no_group": "No group selected" if lang == "en" else "No group selected",
        
        # Moderation labels
        "action_ban": "Ban" if lang == "en" else "Ban",
        "action_kick": "Kick" if lang == "en" else "Kick",
        "action_mute": "Mute" if lang == "en" else "Mute",
        "action_warn": "Warn" if lang == "en" else "Warn",
        "action_delete": "Delete" if lang == "en" else "Delete",
        
        # AutoMod labels
        "antiflood": "Anti-Flood" if lang == "en" else "Anti-Flood",
        "antilink": "Anti-Link" if lang == "en" else "Anti-Link",
        "antispam": "Anti-Spam" if lang == "en" else "Anti-Spam",
        "blacklist_lbl": "Blacklist" if lang == "en" else "Blacklist",
        "locks_lbl": "Locks" if lang == "en" else "Locks",
        
        # Section headers
        "section_general": "General" if lang == "en" else "General",
        "section_warnings": "Warnings" if lang == "en" else "Warnings",
        "section_captcha": "Captcha" if lang == "en" else "Captcha",
        "section_antiraid": "Anti-Raid" if lang == "en" else "Anti-Raid",
        
        # Time labels
        "minutes": "minutes" if lang == "en" else "minutes",
        "seconds": "seconds" if lang == "en" else "seconds",
        "hours": "hours" if lang == "en" else "hours",
        "days": "days" if lang == "en" else "days",
        "threshold_lbl": "Threshold" if lang == "en" else "Threshold",
        "timeout_lbl": "Timeout" if lang == "en" else "Timeout",
        
        # Page-specific
        "vote_threshold": "Vote Threshold" if lang == "en" else "Vote Threshold",
        "vote_action": "Vote Action" if lang == "en" else "Vote Action",
        "auto_detect_scams": "Auto-Detect Scams" if lang == "en" else "Auto-Detect Scams",
        "night_schedule": "Night Schedule" if lang == "en" else "Night Schedule",
        "night_start_lbl": "Start Time" if lang == "en" else "Start Time",
        "night_end_lbl": "End Time" if lang == "en" else "End Time",
        "timezone_lbl": "Timezone" if lang == "en" else "Timezone",
        "night_message_lbl": "Night Message" if lang == "en" else "Night Message",
        "morning_msg_lbl": "Morning Message" if lang == "en" else "Morning Message",
        "fed_name_lbl": "Federation Name" if lang == "en" else "Federation Name",
        "invite_code_lbl": "Invite Code" if lang == "en" else "Invite Code",
        "ban_propagation": "Ban Propagation" if lang == "en" else "Ban Propagation",
        "share_reputation": "Share Reputation" if lang == "en" else "Share Reputation",
        "my_lang_lbl": "My Language" if lang == "en" else "My Language",
        "group_lang_lbl": "Group Language" if lang == "en" else "Group Language",
        "auto_detected": "Auto-detected" if lang == "en" else "Auto-detected",
        "manual_override": "Manual Override" if lang == "en" else "Manual Override",
    }
    
    # Add language-specific UI strings
    if lang == "ar":
        ui_strings.update({
            "nav_trustnet": "شبكة الثقة",
            "nav_captcha": "الكابتشا",
            "nav_community_vote": "تصويت المجتمع",
            "nav_night_mode": "الوضع الليلي",
            "nav_history": "سجل الأسماء",
            "nav_language": "اللغة",
            "nav_persona": "شخصية البوت",
            "save_btn": "حفظ",
            "cancel_btn": "إلغاء",
            "enable_label": "تفعيل",
            "disable_label": "تعطيل",
            "delete": "حذف",
            "edit": "تعديل",
            "confirm": "تأكيد",
            "close": "إغلاق",
            "refresh": "تحديث",
            "search": "بحث",
            "copy": "نسخ",
            "copied": "تم النسخ!",
            "reset": "إعادة تعيين",
            "loading": "جارٍ التحميل...",
            "saved": "تم الحفظ!",
            "error": "خطأ",
            "select_group": "اختر مجموعة",
            "toast_save_success": "تم الحفظ بنجاح!",
            "toast_delete_success": "تم الحذف بنجاح!",
            "toast_copy": "تم النسخ للحافظة!",
            "toast_no_group": "لم يتم تحديد مجموعة",
        })
    
    return {
        "bot": bot_strings,
        "ui": ui_strings,
        "is_rtl": lang == "ar",
        "available_languages": SUPPORTED_LANGUAGES,
    }
