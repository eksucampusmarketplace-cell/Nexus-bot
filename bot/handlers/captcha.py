from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db.ops.captcha import add_captcha_pending, get_captcha_pending, remove_captcha_pending
from datetime import datetime, timedelta

async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE, member):
    chat_id = update.effective_chat.id
    user_id = member.id
    
    keyboard = [[InlineKeyboardButton("✅ I'm human", callback_data=f"captcha_verify_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"Welcome {member.first_name}! Please click the button below to verify you're human."
    msg = await update.message.reply_text(text, reply_markup=reply_markup)
    
    expires_at = datetime.now() + timedelta(seconds=120)
    await add_captcha_pending(user_id, chat_id, msg.message_id, expires_at)
    
    # Schedule kick if not verified
    context.job_queue.run_once(captcha_timeout, 120, data={"chat_id": chat_id, "user_id": user_id})

async def captcha_timeout(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    pending = await get_captcha_pending(data['user_id'], data['chat_id'])
    if pending:
        try:
            await context.bot.unban_chat_member(data['chat_id'], data['user_id'])
            await context.bot.delete_message(data['chat_id'], pending['message_id'])
        except:
            pass
        await remove_captcha_pending(data['user_id'], data['chat_id'])

async def captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if not data.startswith("captcha_verify_"):
        return
    
    user_id = int(data.split("_")[-1])
    if query.from_user.id != user_id:
        await query.answer("This button is not for you!", show_alert=True)
        return
    
    chat_id = update.effective_chat.id
    pending = await get_captcha_pending(user_id, chat_id)
    if pending:
        await query.answer("Verified! Welcome.")
        try:
            await context.bot.delete_message(chat_id, pending['message_id'])
        except:
            pass
        await remove_captcha_pending(user_id, chat_id)
    else:
        await query.answer("Session expired or already verified.")
