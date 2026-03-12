"""
bot/factory.py

Creates fully configured PTB Application instances.
Used for BOTH the primary bot and all clones.

CRITICAL:
  - updater=None → webhook mode, never polling
  - Clone bots DO NOT get clone commands (/clone, /myclones, token_input_handler)
  - Only the primary bot gets those handlers
  - is_primary flag controls which handlers are registered
  - DB pool is injected into bot_data after creation
"""

import logging
from telegram.ext import (
    ApplicationBuilder, Application,
    CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler,
    filters
)

logger = logging.getLogger(__name__)


def create_application(token: str, is_primary: bool = False) -> Application:
    """
    Build a PTB Application for the given token.

    is_primary=True  → registers clone management handlers (/clone, /myclones, token input)
    is_primary=False → registers only group management handlers (moderation, automod, etc.)

    DO NOT call app.run_webhook() or app.run_polling().
    Updates arrive via process_update() in the /webhook/{bot_id} FastAPI route.
    """

    from bot.utils.crypto import mask_token
    logger.info(
        f"[FACTORY] Creating application | "
        f"token={mask_token(token)} | "
        f"is_primary={is_primary}"
    )

    app = (
        ApplicationBuilder()
        .token(token)
        .updater(None)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # ── Import all handlers ───────────────────────────────────────────────
    from bot.handlers.commands import (
        warn_handler, unwarn_handler, warns_handler,
        ban_handler, unban_handler,
        mute_handler, unmute_handler,
        kick_handler, purge_handler,
        lock_handler, unlock_handler,
        pin_handler, unpin_handler,
        rules_handler, info_handler, admins_handler,
        stats_handler, id_handler, report_handler,
        start, help_handler, panel
    )
    from bot.handlers.automod import (
        antiflood_handler, antispam_handler, antilink_handler,
        message_handler, member_join_handler
    )
    from bot.handlers.captcha import (
        new_member_handler, captcha_callback_handler
    )
    # OLD MUSIC SYSTEM IMPORTS - REPLACED BY NEW STREAMING SYSTEM
    # from bot.handlers.music import (
    #     play_command, skip_command, queue_command, stop_command,
    #     pause_command, resume_command, nowplaying_command,
    #     music_callback_handler
    # )
    # from bot.handlers.music_advanced import (
    #     play_youtube_command, volume_command, repeat_command,
    #     shuffle_command, playlist_create_command, playlist_list_command,
    #     playlist_play_command, playlist_delete_command, history_command,
    #     search_command, sync_command, music_settings_command,
    #     music_advanced_callback_handler
    # )
    from bot.handlers.errors import error_handler as global_error_handler

    from bot.handlers.prefix_handler import prefix_handler
    from bot.handlers.greetings import (
        welcome_handler, goodbye_handler,
        set_welcome_handler, set_goodbye_handler, set_rules_handler,
        welcome_preview_handler, goodbye_preview_handler,
        reset_welcome_handler, reset_goodbye_handler, reset_rules_handler,
        rules_handler as nexus_rules_handler
    )
    from bot.handlers.channel import (
        channel_post_handler, schedule_post_handler, approve_post_handler,
        cancel_post_handler, edit_post_handler, delete_post_handler
    )
    from bot.handlers.group_lifecycle import group_lifecycle_handler
    from bot.handlers.group_approval import group_approval_handler
    from bot.handlers.help import help_handler as nexus_help_handler, help_callback_handler
    from bot.utils.aliases import register_aliases

    # Import booster handlers
    from bot.handlers.booster import register_handlers as register_booster_handlers

    # Import new start_help and setmessage handlers (for all bots)
    from bot.handlers.start_help import start_handler, help_handler
    from bot.handlers.setmessage import setmessage_conversation

    # Import alerts utility for error handling
    from bot.utils.alerts import alert_error
    from config import settings

    # ── Music setup ────────────────────────────────────────────────────────
    # Initialize music worker for this bot if userbot configured
    from bot.userbot.music_worker import MusicWorker
    from pyrogram import Client
    from bot.utils.crypto import decrypt_token
    import db.ops.music_new as db_music
    from bot.handlers.music_new import music_handlers as new_music_handlers
    from bot.handlers.adduserbot import adduserbot_conversation

    app.bot_data["is_primary"] = is_primary

    # Store DB pool for later use
    # This will be set by main.py before calling setup_music_worker

    # Music commands handler for new streaming system
    for h in new_music_handlers:
        app.add_handler(h)

    # Register /adduserbot on PRIMARY bot only
    if is_primary:
        app.add_handler(adduserbot_conversation)
        logger.info(f"[FACTORY] AddUserbot handler registered (primary bot only)")

    # ── Prefix system (highest priority) ─────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & (filters.Regex(r'^!') | filters.Regex(r'^!!')), prefix_handler), group=0)

    # ── Basic commands (all bots) ─────────────────────────────────────────
    # Use the new start_help handlers for all bots
    app.add_handler(start_handler)  # /start from start_help.py
    app.add_handler(help_handler)   # /help from start_help.py
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(setmessage_conversation)  # /setmessage for customizing messages

    # ── Nexus Greetings & Rules ──────────────────────────────────────────
    app.add_handler(CommandHandler("setwelcome",  set_welcome_handler,  filters=GROUP))
    app.add_handler(CommandHandler("setgoodbye",  set_goodbye_handler,  filters=GROUP))
    app.add_handler(CommandHandler("setrules",    set_rules_handler,    filters=GROUP))
    app.add_handler(CommandHandler("welcome",     welcome_preview_handler, filters=GROUP))
    app.add_handler(CommandHandler("goodbye",     goodbye_preview_handler, filters=GROUP))
    app.add_handler(CommandHandler("rules",       nexus_rules_handler,     filters=GROUP))
    app.add_handler(CommandHandler("resetwelcome", reset_welcome_handler, filters=GROUP))
    app.add_handler(CommandHandler("resetgoodbye", reset_goodbye_handler, filters=GROUP))
    app.add_handler(CommandHandler("resetrules",   reset_rules_handler,   filters=GROUP))

    # ── Nexus Channel Management ─────────────────────────────────────────
    app.add_handler(CommandHandler("channelpost",  channel_post_handler,  filters=GROUP))
    app.add_handler(CommandHandler("schedulepost", schedule_post_handler, filters=GROUP))
    app.add_handler(CommandHandler("approvepost",  approve_post_handler,  filters=GROUP))
    app.add_handler(CommandHandler("cancelpost",   cancel_post_handler,   filters=GROUP))
    app.add_handler(CommandHandler("editpost",     edit_post_handler,     filters=GROUP))
    app.add_handler(CommandHandler("deletepost",   delete_post_handler,   filters=GROUP))

    # ── Moderation commands (groups only) ─────────────────────────────────
    GROUP = filters.ChatType.GROUPS
    PRIVATE = filters.ChatType.PRIVATE

    app.add_handler(CommandHandler("warn",    warn_handler,    filters=GROUP))
    app.add_handler(CommandHandler("unwarn",  unwarn_handler,  filters=GROUP))
    app.add_handler(CommandHandler("warns",   warns_handler,   filters=GROUP))
    app.add_handler(CommandHandler("ban",     ban_handler,     filters=GROUP))
    app.add_handler(CommandHandler("unban",   unban_handler,   filters=GROUP))
    app.add_handler(CommandHandler("mute",    mute_handler,    filters=GROUP))
    app.add_handler(CommandHandler("unmute",  unmute_handler,  filters=GROUP))
    app.add_handler(CommandHandler("kick",    kick_handler,    filters=GROUP))
    app.add_handler(CommandHandler("purge",   purge_handler,   filters=GROUP))
    app.add_handler(CommandHandler("lock",    lock_handler,    filters=GROUP))
    app.add_handler(CommandHandler("unlock",  unlock_handler,  filters=GROUP))
    app.add_handler(CommandHandler("pin",     pin_handler,     filters=GROUP))
    app.add_handler(CommandHandler("unpin",   unpin_handler,   filters=GROUP))

    # ── Utility commands ──────────────────────────────────────────────────
    app.add_handler(CommandHandler("rules",   rules_handler))
    app.add_handler(CommandHandler("info",    info_handler))
    app.add_handler(CommandHandler("admins",  admins_handler))
    app.add_handler(CommandHandler("stats",   stats_handler))
    app.add_handler(CommandHandler("id",      id_handler))
    app.add_handler(CommandHandler("report",  report_handler))

    # ── Music commands (groups only) ───────────────────────────────────────
    # OLD MUSIC SYSTEM - REPLACED BY NEW STREAMING SYSTEM
    # app.add_handler(CommandHandler("play",           play_command,           filters=GROUP))
    # app.add_handler(CommandHandler("skip",           skip_command,           filters=GROUP))
    # app.add_handler(CommandHandler("queue",          queue_command,          filters=GROUP))
    # app.add_handler(CommandHandler("stop",           stop_command,           filters=GROUP))
    # app.add_handler(CommandHandler("pause",          pause_command,          filters=GROUP))
    # app.add_handler(CommandHandler("resume",         resume_command,         filters=GROUP))
    # app.add_handler(CommandHandler("nowplaying",     nowplaying_command,     filters=GROUP))

    # ── Advanced music commands (groups only) ─────────────────────────────
    # OLD MUSIC SYSTEM - REPLACED BY NEW STREAMING SYSTEM
    # app.add_handler(CommandHandler("play_youtube",   play_youtube_command,   filters=GROUP))
    # app.add_handler(CommandHandler("volume",         volume_command,         filters=GROUP))
    # app.add_handler(CommandHandler("repeat",         repeat_command,         filters=GROUP))
    # app.add_handler(CommandHandler("shuffle",        shuffle_command,        filters=GROUP))
    # app.add_handler(CommandHandler("playlist_create", playlist_create_command, filters=GROUP))
    # app.add_handler(CommandHandler("playlist_list",   playlist_list_command,   filters=GROUP))
    # app.add_handler(CommandHandler("playlist_play",   playlist_play_command,   filters=GROUP))
    # app.add_handler(CommandHandler("playlist_delete", playlist_delete_command, filters=GROUP))
    # app.add_handler(CommandHandler("history",        history_command,        filters=GROUP))
    # app.add_handler(CommandHandler("search",         search_command,         filters=GROUP))
    # app.add_handler(CommandHandler("sync",           sync_command,           filters=GROUP))
    # app.add_handler(CommandHandler("music_settings", music_settings_command, filters=GROUP))

    # ── Clone commands — PRIMARY BOT ONLY ─────────────────────────────────
    if is_primary:
        from bot.handlers.clone import (
            clone_command_handler,
            myclones_command_handler,
            cloneset_handler,
            token_input_handler,
            clone_callback_handler
        )
        app.add_handler(CommandHandler("clone",    clone_command_handler,    filters=PRIVATE))
        app.add_handler(CommandHandler("myclones", myclones_command_handler, filters=PRIVATE))
        app.add_handler(CommandHandler("cloneset", cloneset_handler,         filters=PRIVATE))
        app.add_handler(MessageHandler(
            PRIVATE & filters.TEXT & filters.Regex(r"^\d{8,12}:[\w-]{35,50}$"),
            token_input_handler
        ))
        app.add_handler(CallbackQueryHandler(clone_callback_handler, pattern=r"^clone:"))
        logger.info(f"[FACTORY] Clone handlers registered (primary bot only)")
    else:
        logger.info(f"[FACTORY] Clone handlers SKIPPED (clone bot)")

    # ── Help callbacks (all bots) ─────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(help_callback_handler, pattern=r'^help_'))

    # ── Captcha callbacks (all bots) ──────────────────────────────────────
    app.add_handler(CallbackQueryHandler(captcha_callback_handler, pattern=r'^captcha_verify_'))

    # ── Music callbacks (all bots) ─────────────────────────────────────────
    # OLD MUSIC SYSTEM - REPLACED BY NEW STREAMING SYSTEM
    # app.add_handler(CallbackQueryHandler(music_callback_handler, pattern=r'^music:skip|stop|queue|pause'))
    # app.add_handler(CallbackQueryHandler(music_advanced_callback_handler, pattern=r'^music:vol|repeat|shuffle'))
    # New music system uses callbacks with pattern=r'^music:' from music_handlers

    # ── AutoMod message handlers (groups, priority groups 1-3) ───────────
    app.add_handler(MessageHandler(GROUP & filters.ALL,  antiflood_handler), group=1)
    app.add_handler(MessageHandler(GROUP & filters.TEXT, antispam_handler),  group=2)
    app.add_handler(MessageHandler(GROUP & filters.TEXT, antilink_handler),  group=3)

    # ── New member joins/leaves ──────────────────────────────────────────
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_handler))

    # Keep old captcha handler if needed, but in separate groups or combined
    # app.add_handler(ChatMemberHandler(new_member_handler, ChatMemberHandler.CHAT_MEMBER))

    # ── Global error handler with alert ─────────────────────────────────────
    # Group lifecycle - on ALL bots
    app.add_handler(group_lifecycle_handler)

    # Clone approval callbacks (PRIMARY bot only)
    if is_primary:
        app.add_handler(group_approval_handler)

    async def global_error_handler_with_alert(update, context):
        """Enhanced error handler that posts alerts to support group."""
        import traceback
        import logging
        log = logging.getLogger(__name__)
        error_str = "".join(traceback.format_exception(
            type(context.error), context.error, context.error.__traceback__
        ))
        log.error(f"[ERROR] {error_str[:500]}")

        # Try to get bot username for alert
        try:
            me = await context.bot.get_me()
            chat_id = update.effective_chat.id if update and update.effective_chat else 0
            await alert_error(context.bot, me.username, chat_id, str(context.error)[:300])
        except Exception:
            pass

        # Call original error handler
        try:
            await global_error_handler(update, context)
        except Exception:
            pass

        # Try to notify user something went wrong
        try:
            if update and update.effective_message:
                from bot.utils.messages import DEFAULTS
                suffix = DEFAULTS.get("error_suffix", "").format(main_bot=settings.MAIN_BOT_USERNAME)
                await update.effective_message.reply_text(
                    f"❌ Something went wrong. {suffix}"
                )
        except Exception:
            pass

    app.add_error_handler(global_error_handler_with_alert)

    # ── Register all aliases ──────────────────────────────────────────────
    nexus_handlers = {
        "/warn": warn_handler,
        "/unwarn": unwarn_handler,
        "/mute": mute_handler,
        "/unmute": unmute_handler,
        "/ban": ban_handler,
        "/unban": unban_handler,
        "/kick": kick_handler,
        "/purge": purge_handler,
        "/pin": pin_handler,
        "/unpin": unpin_handler,
        "/rules": nexus_rules_handler,
        "/info": info_handler,
        "/stats": stats_handler,
        "/id": id_handler,
        "/report": report_handler,
        "/setwelcome": set_welcome_handler,
        "/setgoodbye": set_goodbye_handler,
        "/setrules": set_rules_handler,
        "/welcome": welcome_preview_handler,
        "/goodbye": goodbye_preview_handler,
        "/resetwelcome": reset_welcome_handler,
        "/resetgoodbye": reset_goodbye_handler,
        "/resetrules": reset_rules_handler,
        "/channelpost": channel_post_handler,
        "/schedulepost": schedule_post_handler,
        "/approvepost": approve_post_handler,
        "/cancelpost": cancel_post_handler,
        "/editpost": edit_post_handler,
        "/deletepost": delete_post_handler,
    }
    register_aliases(app, nexus_handlers)

    # ── Member Booster handlers ──────────────────────────────────────────────
    register_booster_handlers(app)
    logger.info(f"[FACTORY] Booster handlers registered")

    logger.info(f"[FACTORY] Application built successfully | is_primary={is_primary}")
    return app


async def setup_music_worker(app, bot_id: int, is_primary: bool, db):
    """
    Load music userbot from DB and attach MusicWorker to app.bot_data.
    For primary bot: load all accounts in pool (MUSIC_WORKER_COUNT).
    For clone bots: load their single account if configured.
    If no account found: set music_worker = None (commands show setup instructions).
    """
    from bot.userbot.music_worker import MusicWorker
    from bot.utils.crypto import decrypt_token
    from pyrogram import Client
    from config import settings
    import logging
    logger = logging.getLogger(__name__)

    if not db:
        app.bot_data["music_worker"] = None
        return

    owner_id = 0 if is_primary else bot_id
    rows = await db.fetch(
        "SELECT * FROM music_userbots WHERE owner_bot_id=$1 AND is_active=TRUE LIMIT 1",
        owner_id
    )

    if not rows:
        app.bot_data["music_worker"] = None
        logger.info(f"[MUSIC] No userbot configured | bot={bot_id}")
        return

    row = rows[0]
    try:
        # Check if Pyrogram credentials are configured
        if not settings.PYROGRAM_API_ID or not settings.PYROGRAM_API_HASH:
            logger.warning(f"[MUSIC] Pyrogram credentials not configured | bot={bot_id}")
            app.bot_data["music_worker"] = None
            return

        raw_session = decrypt_token(row["session_string"])
        pyro_client = Client(
            name=f"music_{bot_id}",
            api_id=settings.PYROGRAM_API_ID,
            api_hash=settings.PYROGRAM_API_HASH,
            session_string=raw_session,
            in_memory=True
        )
        await pyro_client.start()
        worker = MusicWorker(pyro_client, bot_id, db)
        await worker.start()
        app.bot_data["music_worker"] = worker
        logger.info(f"[MUSIC] Worker ready | bot={bot_id} account={row['tg_name']}")
    except Exception as e:
        logger.error(f"[MUSIC] Worker startup failed | bot={bot_id} error={e}")
        app.bot_data["music_worker"] = None


# Keep backward compatibility
def create_bot_app(token: str) -> Application:
    """Legacy function - use create_application instead."""
    return create_application(token, is_primary=False)
