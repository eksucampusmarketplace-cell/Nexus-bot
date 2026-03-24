import asyncio
import json
import logging

from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.utils.text_engine import substitute_variables

logger = logging.getLogger(__name__)

# Store references to background tasks to prevent garbage collection
_bg_tasks = set()


async def _delete_after(message, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass


async def send_welcome_in_group(
    update, context, user, chat, processed_welcome, media=None, reply_markup=None, delete_after=0
):
    sent_message = None
    try:
        if media:
            file_id = media["file_id"]
            media_type = media["type"]
            if media_type == "photo":
                sent_message = await context.bot.send_photo(
                    chat_id=chat.id,
                    photo=file_id,
                    caption=processed_welcome,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            elif media_type == "video":
                sent_message = await context.bot.send_video(
                    chat_id=chat.id,
                    video=file_id,
                    caption=processed_welcome,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
            elif media_type == "animation":
                sent_message = await context.bot.send_animation(
                    chat_id=chat.id,
                    animation=file_id,
                    caption=processed_welcome,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
        else:
            sent_message = await context.bot.send_message(
                chat_id=chat.id,
                text=processed_welcome,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )

        logger.info(
            f"[WELCOME] Sent | chat_id={chat.id} | user_id={user.id} | mode=group | media={'photo' if media else 'none'}"
        )

        if delete_after and delete_after > 0 and sent_message:
            t = asyncio.create_task(_delete_after(sent_message, delete_after))
            _bg_tasks.add(t)
            t.add_done_callback(_bg_tasks.discard)

    except Exception as e:
        logger.error(f"[WELCOME] Failed to send in group: {e}")


async def welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db_pool = context.bot_data["db_pool"]

    # Check if welcome module is enabled
    # First try using get_group which now includes modules
    from db.ops.groups import get_group

    group = await get_group(chat.id)
    if not group:
        return

    modules = group.get("modules", {})
    if not modules.get("welcome_message", False):
        return

    text_config = group.get("text_config") or {}
    if isinstance(text_config, str):
        try:
            text_config = json.loads(text_config)
        except:
            text_config = {}

    for user in update.message.new_chat_members:
        if user.is_bot:
            continue

        welcome_text = text_config.get("welcome", "Welcome {mention} to {chatname}!")
        processed_welcome = await substitute_variables(welcome_text, user, chat, db_pool)

        media = text_config.get("welcome_media")  # {file_id: x, type: photo}
        send_as_dm = text_config.get("welcome_dm", False)
        delete_after = text_config.get("welcome_delete_after", 0) or 0

        buttons_config = text_config.get("welcome_buttons", [])
        reply_markup = None
        if buttons_config:
            keyboard = [
                [
                    InlineKeyboardButton(b["text"], url=b["url"])
                    for b in buttons_config
                    if b.get("text") and b.get("url")
                ]
            ]
            if keyboard and keyboard[0]:
                reply_markup = InlineKeyboardMarkup(keyboard)

        if send_as_dm:
            try:
                await context.bot.send_message(
                    chat_id=user.id, text=processed_welcome, parse_mode=ParseMode.HTML
                )
                notice = await update.message.reply_text(
                    f"👋 Welcome {user.mention_html()}! Check your DMs.", parse_mode=ParseMode.HTML
                )
                t = asyncio.create_task(_delete_after(notice, 10))
                _bg_tasks.add(t)
                t.add_done_callback(_bg_tasks.discard)
                logger.info(f"[WELCOME] Sent | chat_id={chat.id} | user_id={user.id} | mode=dm")
            except Exception as e:
                logger.info(f"[WELCOME] DM blocked fallback | user_id={user.id}")
                await send_welcome_in_group(
                    update,
                    context,
                    user,
                    chat,
                    processed_welcome,
                    media,
                    reply_markup,
                    delete_after,
                )
        else:
            await send_welcome_in_group(
                update, context, user, chat, processed_welcome, media, reply_markup, delete_after
            )


async def goodbye_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db_pool = context.bot_data["db_pool"]
    user = update.message.left_chat_member
    if not user or user.is_bot:
        return

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT modules, text_config FROM groups WHERE chat_id = $1", chat.id
        )
        if not row:
            return
        modules = row["modules"] or {}
        if isinstance(modules, str):
            modules = json.loads(modules)
        if not modules.get("goodbye_message", False):
            return

        text_config = row["text_config"] or {}
        if isinstance(text_config, str):
            text_config = json.loads(text_config)

    goodbye_text = text_config.get("goodbye", "Goodbye {fullname}!")
    processed_goodbye = await substitute_variables(goodbye_text, user, chat, db_pool)

    await context.bot.send_message(
        chat_id=chat.id, text=processed_goodbye, parse_mode=ParseMode.HTML
    )
    logger.info(f"[GOODBYE] Sent | chat_id={chat.id} | user_id={user.id}")


async def set_welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Command /setwelcome <text>
    if not await _is_admin(update, context):
        return

    text = " ".join(context.args)
    media = None
    if update.message.reply_to_message:
        reply = update.message.reply_to_message
        if reply.photo:
            media = {"file_id": reply.photo[-1].file_id, "type": "photo"}
        elif reply.video:
            media = {"file_id": reply.video.file_id, "type": "video"}
        elif reply.animation:
            media = {"file_id": reply.animation.file_id, "type": "animation"}

    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT text_config FROM groups WHERE chat_id = $1", update.effective_chat.id
        )
        config = row["text_config"] or {}
        if isinstance(config, str):
            config = json.loads(config)
        config["welcome"] = text
        if media:
            config["welcome_media"] = media
        await conn.execute(
            "UPDATE groups SET text_config = $1 WHERE chat_id = $2",
            json.dumps(config),
            update.effective_chat.id,
        )

    await update.message.reply_text("✅ Welcome message updated.")


async def set_goodbye_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        return
    text = " ".join(context.args)
    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT text_config FROM groups WHERE chat_id = $1", update.effective_chat.id
        )
        config = row["text_config"] or {}
        if isinstance(config, str):
            config = json.loads(config)
        config["goodbye"] = text
        await conn.execute(
            "UPDATE groups SET text_config = $1 WHERE chat_id = $2",
            json.dumps(config),
            update.effective_chat.id,
        )
    await update.message.reply_text("✅ Goodbye message updated.")


async def set_rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        return
    text = " ".join(context.args)
    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT text_config FROM groups WHERE chat_id = $1", update.effective_chat.id
        )
        config = row["text_config"] or {}
        if isinstance(config, str):
            config = json.loads(config)
        config["rules"] = text
        await conn.execute(
            "UPDATE groups SET text_config = $1 WHERE chat_id = $2",
            json.dumps(config),
            update.effective_chat.id,
        )
    await update.message.reply_text("✅ Rules updated.")


async def welcome_preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data["db_pool"]
    chat = update.effective_chat
    user = update.effective_user
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT text_config FROM groups WHERE chat_id = $1", chat.id)
        if not row:
            return
        config = row["text_config"] or {}
        if isinstance(config, str):
            config = json.loads(config)
        welcome_text = config.get("welcome", "Welcome {mention} to {chatname}!")
        processed = await substitute_variables(welcome_text, user, chat, db_pool)
        media = config.get("welcome_media")
        await send_welcome_in_group(update, context, user, chat, processed, media)


async def goodbye_preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_pool = context.bot_data["db_pool"]
    chat = update.effective_chat
    user = update.effective_user
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT text_config FROM groups WHERE chat_id = $1", chat.id)
        if not row:
            return
        config = row["text_config"] or {}
        if isinstance(config, str):
            config = json.loads(config)
        goodbye_text = config.get("goodbye", "Goodbye {fullname}!")
        processed = await substitute_variables(goodbye_text, user, chat, db_pool)
        await context.bot.send_message(chat_id=chat.id, text=processed, parse_mode=ParseMode.HTML)


async def reset_welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        return
    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT text_config FROM groups WHERE chat_id = $1", update.effective_chat.id
        )
        config = row["text_config"] or {}
        if isinstance(config, str):
            config = json.loads(config)
        config.pop("welcome", None)
        config.pop("welcome_media", None)
        await conn.execute(
            "UPDATE groups SET text_config = $1 WHERE chat_id = $2",
            json.dumps(config),
            update.effective_chat.id,
        )
    await update.message.reply_text("✅ Welcome message reset.")


async def reset_goodbye_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        return
    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT text_config FROM groups WHERE chat_id = $1", update.effective_chat.id
        )
        config = row["text_config"] or {}
        if isinstance(config, str):
            config = json.loads(config)
        config.pop("goodbye", None)
        await conn.execute(
            "UPDATE groups SET text_config = $1 WHERE chat_id = $2",
            json.dumps(config),
            update.effective_chat.id,
        )
    await update.message.reply_text("✅ Goodbye message reset.")


async def reset_rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context):
        return
    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT text_config FROM groups WHERE chat_id = $1", update.effective_chat.id
        )
        config = row["text_config"] or {}
        if isinstance(config, str):
            config = json.loads(config)
        config.pop("rules", None)
        await conn.execute(
            "UPDATE groups SET text_config = $1 WHERE chat_id = $2",
            json.dumps(config),
            update.effective_chat.id,
        )
    await update.message.reply_text("✅ Rules reset.")


async def rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT text_config FROM groups WHERE chat_id = $1", chat.id)
        if not row or not row["text_config"]:
            await update.message.reply_text("No rules set for this group.")
            return
        config = row["text_config"]
        if isinstance(config, str):
            config = json.loads(config)
        rules = config.get("rules", "No rules set.")
        await update.message.reply_text(rules, parse_mode=ParseMode.MARKDOWN)


async def _is_admin(update, context):
    member = await update.effective_chat.get_member(update.effective_user.id)
    return member.status in ["creator", "administrator"]
