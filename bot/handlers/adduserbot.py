"""
bot/handlers/adduserbot.py

/adduserbot — Conversation for clone owners to add their music userbot.
PRIMARY BOT ONLY (clone owners DM the primary bot to set up their clone's userbot).

Conversation flow:
  /adduserbot
  → "Which bot do you want to add a music account for?" (if owner has multiple clones)
  → "Choose login method:" [📱 Phone+OTP] [📷 QR Code] [🔑 Session String]

  Phone flow:
    → "Send your phone number (international format, e.g. +1234567890)"
    → [OTP sent] "Enter the code Telegram sent you"
    → If 2FA: "Enter your 2FA password"
    → Success: show account name, save to DB, reload MusicWorker

  QR flow:
    → Send QR image
    → "Scan this with your Telegram app → Settings → Devices → Scan QR"
    → Poll until scanned

  Session string flow:
    → "Paste your Pyrogram session string"
    → Validate and save

After success:
  - Save encrypted session to music_userbots table
  - Reload clone's MusicWorker with new Pyrogram client
  - Confirm to owner with account name

Logs prefix: [ADDUSERBOT]
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from telegram.constants import ParseMode

from config import settings
from bot.userbot.music_auth import (
    MusicAuthSession, start_phone_auth, complete_phone_auth,
    start_qr_auth, check_qr_auth, session_string_auth
)
import db.ops.music_new as db_music

log = logging.getLogger("adduserbot")

# States
CHOOSING_CLONE, CHOOSING_METHOD, PHONE_NUMBER, OTP_CODE, TWO_FA, QR_WAIT, SESSION_STRING = range(7)


async def cmd_adduserbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = context.bot_data.get("db")

    if update.effective_chat.type != "private":
        await update.message.reply_text("Please do this in our private chat.")
        return ConversationHandler.END

    # Get owner's clones
    clones = await db_music.get_owner_clones(db, user.id) if db else []

    if not clones:
        await update.message.reply_text(
            "❌ You don't have any clone bots yet.\n"
            "Use /clone to create one first.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    if len(clones) == 1:
        context.user_data["target_bot_id"] = clones[0]["bot_id"]
        return await _ask_method(update, context)

    # Multiple clones — ask which one
    rows = [[InlineKeyboardButton(
        f"@{c['username']} — {c['display_name']}",
        callback_data=f"aub_clone:{c['bot_id']}"
    )] for c in clones]
    await update.message.reply_text(
        "🤖 Which bot do you want to add a music account for?",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return CHOOSING_CLONE


async def on_clone_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_id = int(query.data.split(":")[1])
    context.user_data["target_bot_id"] = bot_id
    return await _ask_method(update, context)


async def _ask_method(update, context):
    msg = update.effective_message or update.callback_query.message
    await msg.reply_text(
        "🎵 <b>Add Music Account</b>\n\n"
        "Choose how you want to log in with your Telegram account.\n\n"
        "This account will join voice chats to stream music. "
        "It should be a real account, not a bot.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Phone + OTP", callback_data="aub_method:phone")],
            [InlineKeyboardButton("📷 QR Code", callback_data="aub_method:qr")],
            [InlineKeyboardButton("🔑 Session String (Advanced)", callback_data="aub_method:session")],
            [InlineKeyboardButton("❌ Cancel", callback_data="aub_method:cancel")],
        ])
    )
    return CHOOSING_METHOD


async def on_method_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split(":")[1]
    owner_bot_id = context.user_data.get("target_bot_id", 0)

    if method == "cancel":
        await query.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END

    if method == "phone":
        context.user_data["music_auth"] = MusicAuthSession(owner_bot_id)
        await query.edit_message_text(
            "📱 Send your phone number in international format.\n"
            "Example: <code>+1234567890</code>",
            parse_mode=ParseMode.HTML
        )
        return PHONE_NUMBER

    if method == "qr":
        auth = MusicAuthSession(owner_bot_id)
        context.user_data["music_auth"] = auth
        result = await start_qr_auth(auth)
        if not result.ok:
            await query.edit_message_text(f"❌ {result.error}")
            return ConversationHandler.END
        # Send QR image
        img_bytes = bytes.fromhex(result.session_string)
        await query.message.reply_photo(
            photo=img_bytes,
            caption=(
                "📷 <b>Scan this QR code</b>\n\n"
                "Open Telegram → Settings → Devices → Scan QR Code\n\n"
                "Waiting for scan... (30 seconds)",
            ),
            parse_mode=ParseMode.HTML
        )
        return QR_WAIT

    if method == "session":
        await query.edit_message_text(
            "🔑 Paste your Pyrogram session string below.\n\n"
            "To get one: run <code>python3 -c \"from pyrogram import Client; "
            "Client(':memory:').run(lambda c: print(c.export_session_string()))\"</code>",
            parse_mode=ParseMode.HTML
        )
        return SESSION_STRING


async def on_phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    auth = context.user_data.get("music_auth")
    result = await start_phone_auth(auth, phone)
    if not result.ok:
        await update.message.reply_text(f"❌ {result.error}\nTry again or /cancel")
        return PHONE_NUMBER
    await update.message.reply_text(
        "✅ Code sent! Enter the OTP Telegram sent to your account."
    )
    return OTP_CODE


async def on_otp_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    auth = context.user_data.get("music_auth")
    result = await complete_phone_auth(auth, code)
    if result.error == "2FA_REQUIRED":
        await update.message.reply_text("🔐 Enter your 2FA password:")
        context.user_data["pending_code"] = code
        return TWO_FA
    return await _finish_auth(update, context, result)


async def on_2fa_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    auth = context.user_data.get("music_auth")
    code = context.user_data.get("pending_code", "")
    result = await complete_phone_auth(auth, code, password)
    return await _finish_auth(update, context, result)


async def on_qr_wait(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sends anything while waiting for QR — check if scanned."""
    auth = context.user_data.get("music_auth")
    result = await check_qr_auth(auth, timeout=30)
    return await _finish_auth(update, context, result)


async def on_session_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_str = update.message.text.strip()
    owner_bot_id = context.user_data.get("target_bot_id", 0)
    result = await session_string_auth(owner_bot_id, session_str)
    return await _finish_auth(update, context, result)


async def _finish_auth(update, context, result):
    db = context.bot_data.get("db")
    owner_bot_id = context.user_data.get("target_bot_id", 0)

    if not result.ok:
        await update.effective_message.reply_text(
            f"❌ {result.error}\n\nTry /adduserbot again."
        )
        return ConversationHandler.END

    # Save to DB
    if db:
        await db_music.save_music_userbot(
            db,
            owner_bot_id=owner_bot_id,
            tg_user_id=result.tg_user_id,
            tg_name=result.tg_name,
            tg_username=result.tg_username,
            encrypted_session=result.session_string
        )

    # Reload MusicWorker for this clone
    # (registry.py exposes get_app_by_bot_id — use it to get the clone app and reload its worker)
    from bot.registry import get
    from bot.userbot.music_worker import MusicWorker
    from pyrogram import Client
    from bot.utils.crypto import decrypt_token

    clone_app = get(owner_bot_id)
    if clone_app:
        raw_session = decrypt_token(result.session_string)
        pyro_client = Client(
            name=f"music_{owner_bot_id}",
            api_id=settings.PYROGRAM_API_ID,
            api_hash=settings.PYROGRAM_API_HASH,
            session_string=raw_session,
            in_memory=True
        )
        await pyro_client.start()
        worker = MusicWorker(pyro_client, owner_bot_id, db)
        await worker.start()
        clone_app.bot_data["music_worker"] = worker
        log.info(f"[ADDUSERBOT] MusicWorker reloaded | bot={owner_bot_id}")

    await update.effective_message.reply_text(
        f"✅ <b>Music account added!</b>\n\n"
        f"Account: <b>{result.tg_name}</b>"
        + (f" (@{result.tg_username})" if result.tg_username else "") +
        f"\n\nYour bot can now stream music in voice chats. "
        f"Use /play in any group.\n\n"
        f"⚡ Powered by {settings.BOT_DISPLAY_NAME}",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


adduserbot_conversation = ConversationHandler(
    entry_points=[CommandHandler("adduserbot", cmd_adduserbot)],
    states={
        CHOOSING_CLONE: [CallbackQueryHandler(on_clone_chosen, pattern=r"^aub_clone:")],
        CHOOSING_METHOD: [CallbackQueryHandler(on_method_chosen, pattern=r"^aub_method:")],
        PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_phone_received)],
        OTP_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_otp_received)],
        TWO_FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_2fa_received)],
        QR_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_qr_wait)],
        SESSION_STRING: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_session_string)],
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    per_chat=True,
)
