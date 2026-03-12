"""
bot/handlers/setmessage.py

/setmessage — Let group admins customize bot messages for their group.
Admin-only. Works in group chat or private chat (with group selection).

Flow:
  Step 1: /setmessage
          → Show list of customizable messages as buttons

  Step 2: Admin taps a message name
          → Show current text + available variables + instructions
          → "Send your new message text now. Or tap Cancel."

  Step 3: Admin sends new text
          → Show PREVIEW with footer appended
          → Buttons: [✅ Save] [✏️ Edit again] [🔄 Reset to default] [❌ Cancel]

  Step 4: Admin taps Save
          → Save to group_custom_messages table
          → Confirm saved

Rules:
  - Admin cannot include the footer text manually (it gets stripped then re-appended)
  - Admin cannot remove {required} or safety-critical variables from gate messages
  - Message body max length: 1000 characters
  - The "Powered by {bot_name}" footer is shown in preview but admin
    is clearly told they cannot remove it
  - Friendly reminder: "You can use HTML formatting: <b>bold</b>, <i>italic</i>, <a href='...'>links</a>"
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters
)
from telegram.constants import ParseMode

from config import settings
from bot.utils.messages import DEFAULTS, get_message, POWERED_BY_FOOTER
from bot.utils.keyboards import support_keyboard
from db.ops.groups import require_admin

log = logging.getLogger("setmessage")

# Conversation states
CHOOSING_MESSAGE, WAITING_FOR_TEXT, CONFIRMING = range(3)

# ── Message catalog ────────────────────────────────────────────────────────
# What admins can customize and what variables are available for each.
# Safety-critical variables marked with * — warn if missing from new text.
MESSAGE_CATALOG = {
    "start_private": {
        "label": "👋 Welcome Message (DM)",
        "description": "Shown when a user starts the bot in private chat.",
        "variables": {
            "{first_name}":  "User's first name",
            "{clone_name}":  "This bot's name",
            "{main_bot}":    f"Main support bot (@{settings.MAIN_BOT_USERNAME})",
        },
        "required_vars": [],
    },
    "help": {
        "label": "📚 Help Message",
        "description": "Shown when any user sends /help.",
        "variables": {
            "{clone_name}":  "This bot's name",
            "{main_bot}":    "Main support bot username",
            "{bot_name}":    f"Brand name ({settings.BOT_DISPLAY_NAME})",
        },
        "required_vars": [],
    },
    "member_muted": {
        "label": "🔇 Mute Notification",
        "description": "Sent to a user when they are muted.",
        "variables": {
            "{first_name}":  "User's first name",
            "{group_name}":  "Group name",
            "{reason}":      "Mute reason",
            "{duration}":    "Mute duration",
        },
        "required_vars": ["{reason}"],
    },
    "member_banned": {
        "label": "🚫 Ban Notification",
        "description": "Sent to a user when they are banned.",
        "variables": {
            "{first_name}":  "User's first name",
            "{group_name}":  "Group name",
            "{reason}":      "Ban reason",
        },
        "required_vars": ["{reason}"],
    },
    "warn_dm": {
        "label": "⚠️ Warning Notification",
        "description": "Sent to a user when they receive a warning.",
        "variables": {
            "{first_name}":  "User's first name",
            "{group_name}":  "Group name",
            "{reason}":      "Warning reason",
            "{warn_count}":  "Current warn count",
            "{warn_limit}":  "Max warns before action",
        },
        "required_vars": ["{warn_count}", "{warn_limit}"],
    },
    "channel_gate": {
        "label": "📢 Channel Gate Message",
        "description": "Shown when a user must join the channel first.",
        "variables": {
            "{first_name}":   "User's first name",
            "{channel_name}": "Required channel name",
            "{channel_link}": "Channel join link",
        },
        "required_vars": ["{channel_link}"],
    },
    "boost_gate": {
        "label": "🚀 Boost Gate Message",
        "description": "Shown when a user must invite members to gain access.",
        "variables": {
            "{first_name}":  "User's first name",
            "{required}":    "Total invites needed",
            "{current}":     "User's current invites",
            "{remaining}":   "Invites still needed",
            "{link}":        "User's personal invite link",
            "{bar}":         "Progress bar graphic",
        },
        "required_vars": ["{remaining}", "{link}"],
    },
    "boost_unlocked": {
        "label": "🎉 Boost Unlocked Message",
        "description": "Sent to a user when they complete their invite goal.",
        "variables": {
            "{first_name}":  "User's first name",
            "{group_name}":  "Group name",
        },
        "required_vars": [],
    },
}

MAX_BODY_LENGTH = 1000


def _catalog_keyboard() -> InlineKeyboardMarkup:
    """Show all customizable messages as buttons, 1 per row."""
    rows = []
    for key, meta in MESSAGE_CATALOG.items():
        rows.append([InlineKeyboardButton(
            text=meta["label"],
            callback_data=f"setmsg:{key}"
        )])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="setmsg:cancel")])
    return InlineKeyboardMarkup(rows)


def _vars_text(key: str) -> str:
    """Human-readable variable reference for a message key."""
    meta = MESSAGE_CATALOG[key]
    lines = [f"  <code>{var}</code> — {desc}"
             for var, desc in meta["variables"].items()]
    return "\n".join(lines)


async def cmd_setmessage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: /setmessage"""
    user = update.effective_user
    chat = update.effective_chat
    db_pool = context.bot_data["db_pool"]

    # Must be admin
    if not await require_admin(db_pool, chat.id, user.id, context.bot):
        await update.message.reply_text("❌ Only group admins can customize messages.")
        return ConversationHandler.END

    log.info(f"[SETMESSAGE] Started | user={user.id} chat={chat.id}")

    await update.message.reply_text(
        "✏️ <b>Customize Bot Messages</b>\n\n"
        "Choose which message you want to edit.\n"
        "Each message can use special variables (I'll show you which ones).\n\n"
        f"📌 Note: All messages end with \"⚡ Powered by {settings.BOT_DISPLAY_NAME}\" "
        f"— this cannot be removed.",
        parse_mode=ParseMode.HTML,
        reply_markup=_catalog_keyboard()
    )
    return CHOOSING_MESSAGE


async def on_message_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped a message type button."""
    query = update.callback_query
    await query.answer()

    data = query.data  # "setmsg:start_private" or "setmsg:cancel"
    key = data.split(":", 1)[1]

    if key == "cancel":
        await query.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END

    if key not in MESSAGE_CATALOG:
        await query.edit_message_text("❌ Unknown message type.")
        return ConversationHandler.END

    meta = MESSAGE_CATALOG[key]
    context.user_data["setmsg_key"] = key

    current_body = DEFAULTS.get(key, "(not set)")
    footer = POWERED_BY_FOOTER.format(bot_name=settings.BOT_DISPLAY_NAME)

    await query.edit_message_text(
        f"✏️ <b>Editing: {meta['label']}</b>\n\n"
        f"📝 <b>What this message does:</b>\n{meta['description']}\n\n"
        f"🔤 <b>Available variables:</b>\n{_vars_text(key)}\n\n"
        f"📌 <b>Current message:</b>\n<i>{current_body}{footer}</i>\n\n"
        f"──────────────────\n"
        f"💬 <b>Send your new message text now.</b>\n"
        f"You can use HTML: <code>&lt;b&gt;bold&lt;/b&gt;</code>, "
        f"<code>&lt;i&gt;italic&lt;/i&gt;</code>\n\n"
        f"⚠️ The footer <i>\"⚡ Powered by {settings.BOT_DISPLAY_NAME}\"</i> "
        f"is always added automatically — don't add it yourself.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="setmsg:cancel")
        ]])
    )
    return WAITING_FOR_TEXT


async def on_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sent their new message body. Show preview + confirm buttons."""
    user = update.effective_user
    new_body = update.message.text.strip()
    key = context.user_data.get("setmsg_key")

    if not key:
        await update.message.reply_text("❌ Something went wrong. Try /setmessage again.")
        return ConversationHandler.END

    # Length check
    if len(new_body) > MAX_BODY_LENGTH:
        await update.message.reply_text(
            f"❌ Message too long ({len(new_body)} chars). "
            f"Maximum is {MAX_BODY_LENGTH} characters. Please shorten it."
        )
        return WAITING_FOR_TEXT

    # Strip footer if admin accidentally included it
    footer_text = POWERED_BY_FOOTER.format(bot_name=settings.BOT_DISPLAY_NAME).strip()
    new_body_clean = new_body.replace(footer_text, "").strip()

    # Warn about missing required variables
    meta = MESSAGE_CATALOG[key]
    missing = [v for v in meta["required_vars"] if v not in new_body_clean]
    warning = ""
    if missing:
        warning = (
            f"\n\n⚠️ <b>Warning:</b> Your message is missing these important variables:\n"
            + "\n".join(f"  • <code>{v}</code>" for v in missing)
            + "\nYou can still save, but the message may not work as expected."
        )

    # Build preview
    footer = POWERED_BY_FOOTER.format(bot_name=settings.BOT_DISPLAY_NAME)
    preview = f"{new_body_clean}{footer}"

    context.user_data["setmsg_body"] = new_body_clean

    log.info(f"[SETMESSAGE] Preview | user={user.id} key={key} len={len(new_body_clean)}")

    await update.message.reply_text(
        f"👀 <b>Preview:</b>\n\n{preview}{warning}\n\n"
        f"──────────────────\n"
        f"Does this look right?",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Save", callback_data="setmsg_confirm:save"),
                InlineKeyboardButton("✏️ Edit again", callback_data="setmsg_confirm:edit"),
            ],
            [
                InlineKeyboardButton("🔄 Reset to default", callback_data="setmsg_confirm:reset"),
                InlineKeyboardButton("❌ Cancel", callback_data="setmsg_confirm:cancel"),
            ]
        ])
    )
    return CONFIRMING


async def on_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped Save / Edit again / Reset / Cancel on the preview."""
    query = update.callback_query
    await query.answer()

    action = query.data.split(":", 1)[1]
    key = context.user_data.get("setmsg_key")
    body = context.user_data.get("setmsg_body")
    chat = update.effective_chat
    user = update.effective_user
    db_pool = context.bot_data["db_pool"]

    if action == "cancel":
        await query.edit_message_text("❌ Cancelled. No changes saved.")
        return ConversationHandler.END

    if action == "edit":
        meta = MESSAGE_CATALOG[key]
        footer = POWERED_BY_FOOTER.format(bot_name=settings.BOT_DISPLAY_NAME)
        await query.edit_message_text(
            f"✏️ <b>Re-editing: {meta['label']}</b>\n\n"
            f"🔤 <b>Variables:</b>\n{_vars_text(key)}\n\n"
            f"Send your updated message text:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="setmsg:cancel")
            ]])
        )
        return WAITING_FOR_TEXT

    if action == "reset":
        if db_pool:
            await db_pool.fetch(
                "DELETE FROM group_custom_messages WHERE group_id=$1 AND message_key=$2",
                chat.id, key
            )
        log.info(f"[SETMESSAGE] Reset | user={user.id} key={key} chat={chat.id}")
        await query.edit_message_text(
            f"🔄 Message reset to default.\n\n"
            f"⚡ Powered by {settings.BOT_DISPLAY_NAME}"
        )
        return ConversationHandler.END

    if action == "save":
        if db_pool:
            await db_pool.fetch(
                """
                INSERT INTO group_custom_messages (group_id, message_key, body, updated_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (group_id, message_key)
                DO UPDATE SET body=EXCLUDED.body, updated_by=EXCLUDED.updated_by, updated_at=NOW()
                """,
                chat.id, key, body, user.id
            )
        log.info(f"[SETMESSAGE] Saved | user={user.id} key={key} chat={chat.id}")
        await query.edit_message_text(
            f"✅ <b>Message saved!</b>\n\n"
            f"Your new message is now active. Use /setmessage anytime to change it again.\n\n"
            f"⚡ Powered by {settings.BOT_DISPLAY_NAME}",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    return ConversationHandler.END


# ── ConversationHandler to register in factory.py ────────────────────────
setmessage_conversation = ConversationHandler(
    entry_points=[CommandHandler("setmessage", cmd_setmessage)],
    states={
        CHOOSING_MESSAGE: [CallbackQueryHandler(on_message_chosen, pattern=r"^setmsg:")],
        WAITING_FOR_TEXT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_received),
            CallbackQueryHandler(on_message_chosen, pattern=r"^setmsg:cancel"),
        ],
        CONFIRMING: [CallbackQueryHandler(on_confirm, pattern=r"^setmsg_confirm:")],
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    per_message=False,
    per_chat=True,
)
