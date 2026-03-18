"""
bot/utils/messages.py

All user-facing message templates used by every bot (primary + all clones).
RULES:
  - {bot_name}   = settings.BOT_DISPLAY_NAME  (e.g. "Nexus")
  - {clone_name} = the individual bot's Telegram display name
  - {main_bot}   = settings.MAIN_BOT_USERNAME (e.g. "NexusBot")
  - The "Powered by {bot_name}" line CANNOT be removed or edited.
    It is appended programmatically in get_message(), not stored in DB.
  - All other message content CAN be customized by clone owners
    via /setmessage command or Mini App Settings → Messages tab.
  - Beginners-friendly: default messages use simple language,
    no jargon, clear call to action.
  - Customizable fields use {variable} placeholders documented below.
"""

import time

from config import settings

# ── POWERED BY FOOTER ──────────────────────────────────────────────────────
# This is ALWAYS appended to every user-facing message.
# It cannot be removed or edited. Ever. By anyone.
POWERED_BY_FOOTER = "\n\n⚡ Powered by {bot_name}"


def _append_footer(text: str) -> str:
    return text + POWERED_BY_FOOTER.format(bot_name=settings.BOT_DISPLAY_NAME)


# ── DEFAULT MESSAGES ───────────────────────────────────────────────────────
# These are the out-of-the-box messages every new clone starts with.
# Clone owners can replace the body but footer is always re-appended.

DEFAULTS = {
    # /start in PRIVATE chat
    # Variables: {first_name}, {clone_name}, {main_bot}
    "start_private": (
        "👋 Hi {first_name}!\n\n"
        "I'm <b>{clone_name}</b>, a smart group management bot.\n\n"
        "🔧 <b>Need help or support?</b>\n"
        "All support is handled through our main channels below.\n\n"
        "📱 <b>Managing a group?</b>\n"
        "Add me to your group and open the Mini App to configure everything."
    ),
    # /start in GROUP chat (sent as DM to the admin who added the bot)
    # Variables: {first_name}, {clone_name}, {group_name}
    "start_group_dm": (
        "👋 Hey {first_name}!\n\n"
        "I've been added to <b>{group_name}</b>. Let's get set up!\n\n"
        "Open the Mini App below to configure commands, auto-moderation, "
        "welcome messages, and more.\n\n"
        "Tip: Start with the <b>Commands</b> tab to enable the features you need."
    ),
    # /help
    # Variables: {clone_name}, {main_bot}, {miniapp_url}
    "help": (
        "⚡ <b>{clone_name} Commands</b>\n\n"
        "<b>📱 Open the Mini App for full command documentation</b>\n"
        "All commands are listed with detailed descriptions and usage examples.\n"
        "Configure all features deeply through the visual interface.\n\n"
        '<a href="{miniapp_url}">🚀 Open Commands Panel</a>\n\n'
        "<b>🛡️ Quick Reference:</b>\n\n"
        "<b>Moderation:</b> /warn, /ban, /mute, /kick, /purge, /pin\n"
        "<b>Security:</b> !antispam, !antiflood, !antilink, !captcha\n"
        "<b>Notes:</b> /note, /notes, /savenote, /delnote\n"
        "<b>Anti-Raid:</b> /antiraid, !captcha, !antiflood\n\n"
        "<b>💡 Tip:</b> Use /panel to open the full management interface."
    ),
    # Shown when a member is muted
    # Variables: {first_name}, {group_name}, {reason}, {duration}
    "member_muted": (
        "🔇 <b>You've been muted</b>\n\n"
        "You were muted in <b>{group_name}</b>.\n"
        "Reason: {reason}\n"
        "Duration: {duration}\n\n"
        "If you think this was a mistake, contact the group admins."
    ),
    # Shown when a member is banned
    # Variables: {first_name}, {group_name}, {reason}
    "member_banned": (
        "🚫 <b>You've been removed</b>\n\n"
        "You were banned from <b>{group_name}</b>.\n"
        "Reason: {reason}\n\n"
        "If you think this was a mistake, contact the group admins."
    ),
    # Appended to every error message sent to users
    # Variables: {main_bot}
    "error_suffix": ("If this keeps happening, please report it to @{main_bot}."),
    # Warn notification DM
    # Variables: {first_name}, {group_name}, {reason}, {warn_count}, {warn_limit}
    "warn_dm": (
        "⚠️ <b>Warning received</b>\n\n"
        "You received a warning in <b>{group_name}</b>.\n"
        "Reason: {reason}\n"
        "Warnings: {warn_count}/{warn_limit}\n\n"
        "Please follow the group rules to avoid further action."
    ),
    # Force channel gate message
    # Variables: {first_name}, {channel_name}, {channel_link}
    "channel_gate": (
        "👋 Hi {first_name}!\n\n"
        "To participate in this group, you need to join our channel first.\n\n"
        "1. Join <b>{channel_name}</b>\n"
        "2. Come back here — you'll be automatically verified."
    ),
    # Force boost gate message
    # Variables: {first_name}, {required}, {current}, {remaining}, {link}, {bar}
    "boost_gate": (
        "👋 Hi {first_name}!\n\n"
        "To unlock full access, invite <b>{remaining}</b> more "
        "member(s) to this group.\n\n"
        "Your progress: {bar} ({current}/{required})\n\n"
        "Your personal invite link:\n{link}"
    ),
    # Boost unlocked notification
    # Variables: {first_name}, {group_name}
    "boost_unlocked": (
        "🎉 <b>Access unlocked!</b>\n\n"
        "You've hit your invite goal in <b>{group_name}</b>.\n"
        "You now have full access. Welcome!"
    ),
}


# ── MESSAGE GETTER ─────────────────────────────────────────────────────────


async def get_message(
    key: str, group_id: int | None, variables: dict, db=None, bot_id: int | None = None
) -> str:
    """
    Returns the final message string for a given key.

    Steps:
    1. If group_id and db provided: check DB for group-specific override
    2. If bot_id and db provided: check DB for bot-wide override
    3. Fall back to DEFAULTS[key] if no custom message
    4. Format with provided variables
    5. ALWAYS append POWERED_BY_FOOTER (cannot be bypassed)

    Args:
        key:       Message key (e.g. "start_private", "help")
        group_id:  The group this message is for (None = global/no group)
        variables: Dict of {placeholder: value} for formatting
        db:        AsyncPG connection/pool (optional, skips DB lookup if None)
        bot_id:    The bot ID for bot-wide customization

    Logs: [MESSAGES] key={key} group={group_id} bot={bot_id} custom={bool}
    """
    import logging

    log = logging.getLogger("messages")

    custom_body = None

    if db and (group_id or bot_id):
        cache_key = (group_id, bot_id, key)
        cached = get_message._cache.get(cache_key)
        if cached and (time.monotonic() - cached["ts"]) < 300:
            custom_body = cached["body"]
        else:
            # 1. Try group-specific override
            if group_id:
                try:
                    row = await db.fetchrow(
                        "SELECT body FROM group_custom_messages"
                        " WHERE group_id=$1 AND message_key=$2",
                        group_id,
                        key,
                    )
                    if row:
                        custom_body = row["body"]
                except Exception as e:
                    log.warning(f"[MESSAGES] Group DB lookup failed | key={key} error={e}")

            # 2. Try bot-wide override if no group override found
            if not custom_body and bot_id:
                try:
                    row = await db.fetchrow(
                        "SELECT body FROM bot_custom_messages"
                        " WHERE bot_id=$1 AND message_key=$2",
                        bot_id,
                        key,
                    )
                    if row:
                        custom_body = row["body"]
                except Exception as e:
                    log.warning(f"[MESSAGES] Bot DB lookup failed | key={key} error={e}")

            get_message._cache[cache_key] = {"body": custom_body, "ts": time.monotonic()}

    body = custom_body if custom_body else DEFAULTS.get(key, "")
    is_custom = bool(custom_body)

    log.debug(f"[MESSAGES] key={key} group={group_id} bot={bot_id} custom={is_custom}")

    # Inject standard variables always available
    variables.setdefault("main_bot", settings.MAIN_BOT_USERNAME)
    variables.setdefault("bot_name", settings.BOT_DISPLAY_NAME)

    # Format body safely (missing keys show as {key} not crash)
    try:
        body = body.format_map(variables)
    except Exception as e:
        log.warning(f"[MESSAGES] Format failed | key={key} error={e}")

    return _append_footer(body)


get_message._cache = {}
