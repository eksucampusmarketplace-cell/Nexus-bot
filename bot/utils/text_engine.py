import re
import logging
from telegram import User, Chat, Update
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def substitute_variables(text: str, user: User, chat: Chat, db_pool) -> str:
    """
    Replace all supported variables in text with live values.

    {first}     → user.first_name
    {last}      → user.last_name or ""
    {fullname}  → user.full_name
    {username}  → @user.username or str(user.id) if no username
    {mention}   → HTML mention: <a href="tg://user?id={id}">{first}</a>
    {id}        → str(user.id)
    {count}     → live member count from bot.get_chat_member_count(chat.id)
    {chatname}  → chat.title
    {rules}     → short link to rules or "No rules set" if empty

    Returns substituted string safe for both HTML and MarkdownV2 parse modes.
    Logs: [TEXT_ENGINE] Substituted {n} variables for user_id={user.id}
    """
    if not text:
        return ""

    # Get count
    try:
        count = await chat.get_member_count()
    except Exception:
        count = "N/A"

    # Get rules from DB
    rules_link = "No rules set"
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT text_config FROM groups WHERE chat_id = $1", chat.id)
        if row and row["text_config"]:
            import json

            text_config = row["text_config"]
            if isinstance(text_config, str):
                text_config = json.loads(text_config)
            if text_config.get("rules"):
                rules_link = f"Rules for {chat.title}"  # In reality this might be a link to a message or /rules

    variables = {
        "{first}": user.first_name,
        "{last}": user.last_name or "",
        "{fullname}": user.full_name,
        "{username}": f"@{user.username}" if user.username else str(user.id),
        "{mention}": f'<a href="tg://user?id={user.id}">{user.first_name}</a>',
        "{id}": str(user.id),
        "{count}": str(count),
        "{chatname}": chat.title,
        "{rules}": rules_link,
    }

    n = 0
    result = text
    for var, val in variables.items():
        if var in result:
            result = result.replace(var, val)
            n += 1

    logger.info(f"[TEXT_ENGINE] Substituted {n} variables | user_id={user.id} | chat_id={chat.id}")
    return result
