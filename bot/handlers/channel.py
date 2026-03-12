import logging
import json
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

async def _is_admin(update, context):
    member = await update.effective_chat.get_member(update.effective_user.id)
    return member.status in ['creator', 'administrator']

async def send_to_channel(
    bot,
    channel_id: int,
    text: str = None,
    media_file_id: str = None,
    media_type: str = None,    # photo | video | animation | document
    parse_mode: str = "HTML",
    disable_notification: bool = False
) -> Message:
    """
    Core channel posting function.
    Handles text-only, media+caption, and media-only posts.
    Returns the sent Message object (save message_id to DB for edit/delete later).
    
    Logs: [CHANNEL] Posted | channel_id={id} | type={text/photo/video} | msg_id={id}
    """

    if media_file_id:
        send_func = {
            "photo":     bot.send_photo,
            "video":     bot.send_video,
            "animation": bot.send_animation,
            "document":  bot.send_document,
        }.get(media_type, bot.send_photo)

        msg = await send_func(
            chat_id=channel_id,
            **{media_type: media_file_id},
            caption=text,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
    else:
        msg = await bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
    
    logger.info(f"[CHANNEL] Posted | channel_id={channel_id} | type={media_type or 'text'} | msg_id={msg.message_id}")
    return msg

async def copy_message_to_channel(bot, channel_id: int, from_chat_id: int, message_id: int):
    """
    Copies a message to the channel without the 'Forwarded from' header.
    Used by /approvepost.
    """
    return await bot.copy_message(
        chat_id=channel_id,
        from_chat_id=from_chat_id,
        message_id=message_id
    )

async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context): return
    db_pool = context.bot_data["db_pool"]
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT channel_id FROM linked_channels WHERE group_chat_id = $1", update.effective_chat.id)
        if not row:
            await update.message.reply_text("❌ No channel linked. Use the Mini App to link a channel.")
            return
        channel_id = row['channel_id']

    text = " ".join(context.args)
    media_file_id = None
    media_type = None

    if update.message.reply_to_message:
        reply = update.message.reply_to_message
        if reply.photo:
            media_file_id = reply.photo[-1].file_id
            media_type = "photo"
        elif reply.video:
            media_file_id = reply.video.file_id
            media_type = "video"
        elif reply.animation:
            media_file_id = reply.animation.file_id
            media_type = "animation"
        elif reply.document:
            media_file_id = reply.document.file_id
            media_type = "document"

    await send_to_channel(context.bot, channel_id, text, media_file_id, media_type)
    await update.message.reply_text(f"✅ Posted to channel.")

async def schedule_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context): return
    # /schedulepost 2025-03-15 14:30 Big announcement
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /schedulepost YYYY-MM-DD HH:MM <text>")
        return
    
    try:
        dt_str = f"{context.args[0]} {context.args[1]}"
        from datetime import datetime
        scheduled_at = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except Exception:
        await update.message.reply_text("Invalid date format. Use YYYY-MM-DD HH:MM")
        return

    text = " ".join(context.args[2:])
    db_pool = context.bot_data["db_pool"]

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT channel_id FROM linked_channels WHERE group_chat_id = $1", update.effective_chat.id)
        if not row:
            await update.message.reply_text("❌ No channel linked.")
            return
        channel_id = row['channel_id']

        post_id = await conn.fetchval("""
            INSERT INTO channel_posts (bot_id, channel_id, group_chat_id, text, scheduled_at, created_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, context.bot.id, channel_id, update.effective_chat.id, text, scheduled_at, update.effective_user.id)

    await update.message.reply_text(f"✅ Post scheduled for {dt_str} (UTC). ID: {post_id}")

async def approve_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context): return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a message to approve it for the channel.")
        return

    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT channel_id FROM linked_channels WHERE group_chat_id = $1", update.effective_chat.id)
        if not row:
            await update.message.reply_text("❌ No channel linked.")
            return
        channel_id = row['channel_id']

    await copy_message_to_channel(context.bot, channel_id, update.effective_chat.id, update.message.reply_to_message.message_id)
    await update.message.reply_text("✅ Post approved and copied to channel.")

async def cancel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context): return
    if not context.args:
        await update.message.reply_text("Usage: /cancelpost <post_id>")
        return
    
    post_id = int(context.args[0])
    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE channel_posts SET status = 'cancelled' WHERE id = $1 AND group_chat_id = $2", post_id, update.effective_chat.id)
    
    await update.message.reply_text(f"✅ Post {post_id} cancelled.")

async def edit_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context): return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /editpost <post_id> <new_text>")
        return
    
    post_id = int(context.args[0])
    new_text = " ".join(context.args[1:])
    db_pool = context.bot_data["db_pool"]
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT channel_id, sent_message_id FROM channel_posts WHERE id = $1 AND group_chat_id = $2", post_id, update.effective_chat.id)
        if not row:
            await update.message.reply_text("Post not found.")
            return
        
        if row['sent_message_id']:
            await context.bot.edit_message_text(chat_id=row['channel_id'], message_id=row['sent_message_id'], text=new_text, parse_mode=ParseMode.HTML)
            await conn.execute("UPDATE channel_posts SET text = $1 WHERE id = $2", new_text, post_id)
            await update.message.reply_text("✅ Sent post edited.")
        else:
            await conn.execute("UPDATE channel_posts SET text = $1 WHERE id = $2", new_text, post_id)
            await update.message.reply_text("✅ Scheduled post text updated.")

async def delete_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _is_admin(update, context): return
    if not context.args:
        await update.message.reply_text("Usage: /deletepost <post_id>")
        return
    
    post_id = int(context.args[0])
    db_pool = context.bot_data["db_pool"]
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT channel_id, sent_message_id FROM channel_posts WHERE id = $1 AND group_chat_id = $2", post_id, update.effective_chat.id)
        if not row:
            await update.message.reply_text("Post not found.")
            return
        
        if row['sent_message_id']:
            await context.bot.delete_message(chat_id=row['channel_id'], message_id=row['sent_message_id'])
            await conn.execute("UPDATE channel_posts SET status = 'deleted' WHERE id = $1", post_id)
            await update.message.reply_text("✅ Post deleted from channel.")
        else:
            await conn.execute("UPDATE channel_posts SET status = 'cancelled' WHERE id = $1", post_id)
            await update.message.reply_text("✅ Scheduled post cancelled.")
