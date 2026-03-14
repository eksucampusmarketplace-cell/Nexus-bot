from telegram import Update
from telegram.ext import ContextTypes
from config import settings


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user.id == settings.OWNER_ID:
        return True

    if update.effective_chat.type == "private":
        return True

    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ["creator", "administrator"]


async def command_enabled(chat_id: int, command_name: str) -> bool:
    from db.ops.groups import get_group

    group = await get_group(chat_id)
    if not group:
        return True
    return group.get("settings", {}).get("commands", {}).get(command_name, True)
