from telegram import User


def escape_markdown_v2(text: str) -> str:
    """Escapes strings for Telegram's MarkdownV2 parse mode."""
    if not text:
        return ""
    # Standard MarkdownV2 special characters that must be escaped outside code blocks
    # Backslash must be escaped first, so it's at the beginning of the string.
    special_chars = r"\_*[]()~`>#+-=|{}.!"
    res = str(text)
    for char in special_chars:
        res = res.replace(char, f"\\{char}")
    return res


def get_main_bot_ref() -> str:
    """Returns a safe reference to the main bot (never empty string).

    Falls back through several options so messages always have
    a valid reference even when MAIN_BOT_USERNAME is not configured.
    """
    from config import settings

    if settings.MAIN_BOT_USERNAME:
        return f"@{settings.MAIN_BOT_USERNAME}"
    if settings.SUPPORT_GROUP_URL:
        return settings.SUPPORT_GROUP_URL
    if settings.BOT_DISPLAY_NAME:
        return settings.BOT_DISPLAY_NAME
    return "the main bot"


def format_user(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"


def format_stats(stats: dict) -> str:
    return (
        f"📊 <b>Group Statistics</b>\n\n"
        f"👥 Members: {stats.get('member_count', 'N/A')}\n"
        f"💬 Total Messages: {stats.get('total_messages', 0)}\n"
        f"⚠️ Total Warnings: {stats.get('total_warns', 0)}\n"
    )
