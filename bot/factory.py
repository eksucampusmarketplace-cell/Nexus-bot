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
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    MessageHandler,
    filters,
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
    from pyrogram import Client

    import db.ops.music_new as db_music
    from bot.handlers.adduserbot import adduserbot_conversation
    from bot.handlers.admin_request import (
        admin_request_callback,
        admin_request_command_handlers,
        handle_admin_mention,
    )
    from bot.handlers.admin_tools import admin_tool_handlers
    from bot.handlers.advanced_automod import handle_automod_command
    from bot.handlers.approval import (
        cmd_antiraid,
        cmd_approve,
        cmd_approved,
        cmd_autoantiraid,
        cmd_captcha,
        cmd_captchamode,
        cmd_unapprove,
    )
    from bot.handlers.automod import (
        antiflood_handler,
        antilink_handler,
        antispam_handler,
        member_join_handler,
        message_handler,
    )

    # Import booster handlers
    from bot.handlers.booster import register_handlers as register_booster_handlers

    # Import alerts utility for error handling
    from bot.handlers.broadcast_track import track_pm_handler
    from bot.handlers.captcha import captcha_callback_handler, new_member_handler
    from bot.handlers.captcha_callback import handle_captcha_callback
    from bot.handlers.captcha_message import handle_captcha_message
    from bot.handlers.channel import (
        approve_post_handler,
        cancel_post_handler,
        channel_post_handler,
        delete_post_handler,
        edit_post_handler,
        schedule_post_handler,
    )
    from bot.handlers.commands import (
        admins_handler,
        ban_handler,
        help_handler,
        id_handler,
        info_handler,
        kick_handler,
        lock_handler,
        mute_handler,
        panel,
        pin_handler,
        purge_handler,
        report_handler,
        rules_handler,
        start,
        stats_handler,
        unban_handler,
        unlock_handler,
        unmute_handler,
        unpin_handler,
        unwarn_handler,
        warn_handler,
        warns_handler,
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
    from bot.handlers.fun import fun_handlers
    from bot.handlers.greetings import (
        goodbye_handler,
        goodbye_preview_handler,
        reset_goodbye_handler,
        reset_rules_handler,
        reset_welcome_handler,
    )
    from bot.handlers.greetings import rules_handler as nexus_rules_handler
    from bot.handlers.greetings import (
        set_goodbye_handler,
        set_rules_handler,
        set_welcome_handler,
        welcome_handler,
        welcome_preview_handler,
    )
    from bot.handlers.group_approval import group_approval_handler
    from bot.handlers.group_lifecycle import group_lifecycle_handler
    from bot.handlers.help import help_callback_handler
    from bot.handlers.help import help_handler as nexus_help_handler
    from bot.handlers.music_new import music_handlers as new_music_handlers
    from bot.handlers.new_member import handle_chat_member_update
    from bot.handlers.prefix_handler import prefix_handler
    from bot.handlers.privacy import privacy_handler
    from bot.handlers.report import report_handlers as full_report_handlers
    from bot.handlers.setmessage import setmessage_conversation

    # Import new start_help and setmessage handlers (for all bots)
    from bot.handlers.start_help import help_handler, start_callback_handler, start_handler

    # ── Music setup ────────────────────────────────────────────────────────
    # Initialize music worker for this bot if userbot configured
    from bot.userbot.music_worker import MusicWorker
    from bot.utils.alerts import alert_error
    from bot.utils.aliases import register_aliases
    from bot.utils.crypto import decrypt_token
    from config import settings

    app.bot_data["is_primary"] = is_primary

    # Store DB pool for later use
    # This will be set by main.py before calling setup_music_worker

    # ── PM Tracking ────────────────────────────────────────────────────────
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, track_pm_handler), group=-1)

    # Music commands handler for new streaming system
    for h in new_music_handlers:
        app.add_handler(h)

    # Register /adduserbot on PRIMARY bot only
    if is_primary:
        app.add_handler(adduserbot_conversation)
        logger.info(f"[FACTORY] AddUserbot handler registered (primary bot only)")

    # ── Prefix system (highest priority) ─────────────────────────────────
    app.add_handler(
        MessageHandler(
            filters.TEXT & (filters.Regex(r"^!") | filters.Regex(r"^!!")), prefix_handler
        ),
        group=0,
    )

    # Define filter constants (needed for handlers below)
    GROUP = filters.ChatType.GROUPS
    PRIVATE = filters.ChatType.PRIVATE

    # ── Approval & Anti-raid & CAPTCHA (all bots) ─────────────────────────
    app.add_handler(CommandHandler("approve", cmd_approve, filters=GROUP))
    app.add_handler(CommandHandler("unapprove", cmd_unapprove, filters=GROUP))
    app.add_handler(CommandHandler("approved", cmd_approved, filters=GROUP))
    app.add_handler(CommandHandler("antiraid", cmd_antiraid, filters=GROUP))
    app.add_handler(CommandHandler("autoantiraid", cmd_autoantiraid, filters=GROUP))
    app.add_handler(CommandHandler("captcha", cmd_captcha, filters=GROUP))
    app.add_handler(CommandHandler("captchamode", cmd_captchamode, filters=GROUP))

    # ── Basic commands (all bots) ─────────────────────────────────────────
    # Use the new start_help handlers for all bots
    app.add_handler(start_handler)  # /start from start_help.py
    app.add_handler(help_handler)  # /help from start_help.py
    app.add_handler(privacy_handler)  # /privacy from privacy.py
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(setmessage_conversation)  # /setmessage for customizing messages

    # ── Nexus Greetings & Rules ──────────────────────────────────────────
    app.add_handler(CommandHandler("setwelcome", set_welcome_handler, filters=GROUP))
    app.add_handler(CommandHandler("setgoodbye", set_goodbye_handler, filters=GROUP))
    app.add_handler(CommandHandler("setrules", set_rules_handler, filters=GROUP))
    app.add_handler(CommandHandler("welcome", welcome_preview_handler, filters=GROUP))
    app.add_handler(CommandHandler("goodbye", goodbye_preview_handler, filters=GROUP))
    app.add_handler(CommandHandler("rules", nexus_rules_handler, filters=GROUP))
    app.add_handler(CommandHandler("resetwelcome", reset_welcome_handler, filters=GROUP))
    app.add_handler(CommandHandler("resetgoodbye", reset_goodbye_handler, filters=GROUP))
    app.add_handler(CommandHandler("resetrules", reset_rules_handler, filters=GROUP))

    # ── Nexus Channel Management ─────────────────────────────────────────
    app.add_handler(CommandHandler("channelpost", channel_post_handler, filters=GROUP))
    app.add_handler(CommandHandler("schedulepost", schedule_post_handler, filters=GROUP))
    app.add_handler(CommandHandler("approvepost", approve_post_handler, filters=GROUP))
    app.add_handler(CommandHandler("cancelpost", cancel_post_handler, filters=GROUP))
    app.add_handler(CommandHandler("editpost", edit_post_handler, filters=GROUP))
    app.add_handler(CommandHandler("deletepost", delete_post_handler, filters=GROUP))

    # ── New Moderation Handlers ───────────────────────────────────────────
    from bot.handlers.moderation import admins_command as nexus_admins_command
    from bot.handlers.moderation import (
        ban_command,
        blacklist_command,
        blacklistmode_command,
        clearrules_command,
        del_command,
        demote_command,
        filter_command,
        filters_list_command,
    )
    from bot.handlers.moderation import id_command as nexus_id_command
    from bot.handlers.moderation import info_command as nexus_info_command
    from bot.handlers.moderation import (
        kick_command,
        lock_command,
        locks_list_command,
        mute_command,
        promote_command,
        purge_command,
        resetwarns_command,
        restrict_command,
        sban_command,
        setrules_command,
        skick_command,
        smute_command,
        stop_filter_command,
        tban_command,
        title_command,
        tmute_command,
        unban_command,
        unblacklist_command,
        unlock_command,
        unmute_command,
        unrestrict_command,
        unwarn_command,
        warn_command,
        warnlimit_command,
        warnmode_command,
        warns_command,
    )
    from bot.handlers.moderation import rules_command as nexus_rules_command
    from bot.handlers.moderation.message_guard import message_guard

    # ── Moderation commands (groups only) ─────────────────────────────────
    from bot.moderation_scheduler import setup_moderation_scheduler

    setup_moderation_scheduler(app)

    app.add_handler(CommandHandler("ban", ban_command, filters=GROUP))
    app.add_handler(CommandHandler("unban", unban_command, filters=GROUP))
    app.add_handler(CommandHandler("tban", tban_command, filters=GROUP))
    app.add_handler(CommandHandler("sban", sban_command, filters=GROUP))
    app.add_handler(CommandHandler("mute", mute_command, filters=GROUP))
    app.add_handler(CommandHandler("unmute", unmute_command, filters=GROUP))
    app.add_handler(CommandHandler("tmute", tmute_command, filters=GROUP))
    app.add_handler(CommandHandler("warn", warn_command, filters=GROUP))
    app.add_handler(CommandHandler("unwarn", unwarn_command, filters=GROUP))
    app.add_handler(CommandHandler("warns", warns_command, filters=GROUP))
    app.add_handler(CommandHandler("kick", kick_command, filters=GROUP))
    app.add_handler(CommandHandler("purge", purge_command, filters=GROUP))
    app.add_handler(CommandHandler("del", del_command, filters=GROUP))
    app.add_handler(CommandHandler("promote", promote_command, filters=GROUP))
    app.add_handler(CommandHandler("demote", demote_command, filters=GROUP))
    app.add_handler(CommandHandler("admins", nexus_admins_command, filters=GROUP))
    app.add_handler(CommandHandler("lock", lock_command, filters=GROUP))
    app.add_handler(CommandHandler("unlock", unlock_command, filters=GROUP))
    app.add_handler(CommandHandler("locks", locks_list_command, filters=GROUP))
    app.add_handler(CommandHandler("rules", nexus_rules_command, filters=GROUP))
    app.add_handler(CommandHandler("setrules", setrules_command, filters=GROUP))
    app.add_handler(CommandHandler("clearrules", clearrules_command, filters=GROUP))
    app.add_handler(CommandHandler("info", nexus_info_command, filters=GROUP))
    app.add_handler(CommandHandler("id", nexus_id_command, filters=GROUP))
    from bot.handlers.commands import stats_handler

    app.add_handler(CommandHandler("stats", stats_handler, filters=GROUP))
    app.add_handler(CommandHandler("resetwarns", resetwarns_command, filters=GROUP))
    app.add_handler(CommandHandler("warnmode", warnmode_command, filters=GROUP))
    app.add_handler(CommandHandler("warnlimit", warnlimit_command, filters=GROUP))
    app.add_handler(CommandHandler("skick", skick_command, filters=GROUP))
    app.add_handler(CommandHandler("smute", smute_command, filters=GROUP))
    app.add_handler(CommandHandler("restrict", restrict_command, filters=GROUP))
    app.add_handler(CommandHandler("unrestrict", unrestrict_command, filters=GROUP))
    app.add_handler(CommandHandler("title", title_command, filters=GROUP))
    app.add_handler(CommandHandler("filter", filter_command, filters=GROUP))
    app.add_handler(CommandHandler("filters", filters_list_command, filters=GROUP))
    app.add_handler(CommandHandler("stop", stop_filter_command, filters=GROUP))
    app.add_handler(CommandHandler("blacklist", blacklist_command, filters=GROUP))
    app.add_handler(CommandHandler("unblacklist", unblacklist_command, filters=GROUP))
    app.add_handler(CommandHandler("blacklistmode", blacklistmode_command, filters=GROUP))

    # Message handler for message_guard (checks locks, filters, etc.)
    app.add_handler(MessageHandler(GROUP & filters.ALL, message_guard), group=0)

    # ── Full report system (replaces stub report_handler for new commands) ──
    for h in full_report_handlers:
        app.add_handler(h)

    # ── Admin request system (@admins mentions) ──────────────────────────
    for h in admin_request_command_handlers:
        app.add_handler(h)
    # Message handler for @admins mentions (run before automod)
    app.add_handler(MessageHandler(GROUP & filters.TEXT, handle_admin_mention), group=-1)

    # ── Advanced automod commands ───────────────────────────────────────
    # These are also handled by prefix_handler (!, !!) in group 0
    # But we also register specific commands here as fallback
    app.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_automod_command), group=2
    )

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
            clone_conversation,
            clone_management_callback,
            cloneset_handler,
            myclones_command_handler,
        )

        # ConversationHandler for /clone flow (must be added before other clone handlers)
        app.add_handler(clone_conversation)
        # Non-conversation commands
        app.add_handler(CommandHandler("myclones", myclones_command_handler, filters=PRIVATE))
        app.add_handler(CommandHandler("cloneset", cloneset_handler, filters=PRIVATE))
        # Management callbacks outside of conversation (remove, confirm_remove, keep)
        app.add_handler(
            CallbackQueryHandler(
                clone_management_callback, pattern=r"^clone:(remove|confirm_remove|keep)$"
            )
        )
        logger.info(f"[FACTORY] Clone handlers registered (primary bot only)")
    else:
        logger.info(f"[FACTORY] Clone handlers SKIPPED (clone bot)")

    # ── Help callbacks (all bots) ─────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(help_callback_handler, pattern=r"^help_"))
    app.add_handler(start_callback_handler)  # For start_clone and help_main buttons

    # ── Admin request callbacks (all bots) ────────────────────────────────
    app.add_handler(
        CallbackQueryHandler(admin_request_callback, pattern=r"^admin_req:(responding|close):\d+$")
    )
    app.add_handler(
        MessageHandler(GROUP & filters.TEXT & ~filters.COMMAND, handle_captcha_message), group=0
    )

    # ── Music callbacks (all bots) ─────────────────────────────────────────
    # OLD MUSIC SYSTEM - REPLACED BY NEW STREAMING SYSTEM
    # app.add_handler(CallbackQueryHandler(music_callback_handler, pattern=r'^music:skip|stop|queue|pause'))
    # app.add_handler(CallbackQueryHandler(music_advanced_callback_handler, pattern=r'^music:vol|repeat|shuffle'))
    # New music system uses callbacks with pattern=r'^music:' from music_handlers

    # ── AutoMod message handlers (groups, priority groups 1-3) ───────────
    app.add_handler(MessageHandler(GROUP & filters.ALL, antiflood_handler), group=1)
    app.add_handler(MessageHandler(GROUP & filters.TEXT, antispam_handler), group=2)
    app.add_handler(MessageHandler(GROUP & filters.TEXT, antilink_handler), group=3)
    app.add_handler(MessageHandler(GROUP & ~filters.COMMAND, message_handler), group=4)

    # ── New member joins/leaves ──────────────────────────────────────────
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_handler))

    # Advanced member join/leave handler
    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # ── Global error handler with alert ─────────────────────────────────────
    # Group lifecycle - on ALL bots
    app.add_handler(group_lifecycle_handler)

    # Clone approval callbacks (PRIMARY bot only)
    if is_primary:
        app.add_handler(group_approval_handler)

    async def global_error_handler_with_alert(update, context):
        """Enhanced error handler that posts alerts to support group."""
        import logging
        import traceback

        log = logging.getLogger(__name__)
        error_str = "".join(
            traceback.format_exception(
                type(context.error), context.error, context.error.__traceback__
            )
        )
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

                suffix = DEFAULTS.get("error_suffix", "").format(
                    main_bot=settings.MAIN_BOT_USERNAME
                )
                await update.effective_message.reply_text(f"❌ Something went wrong. {suffix}")
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

    # ── Fun and utility handlers ──────────────────────────────────────────────
    for h in fun_handlers:
        app.add_handler(h)
    logger.info(f"[FACTORY] Fun handlers registered")

    # ── Admin tools handlers ──────────────────────────────────────────────
    for h in admin_tool_handlers:
        app.add_handler(h)
    logger.info(f"[FACTORY] Admin tools handlers registered")

    # ── Pin management handlers ───────────────────────────────────────────
    from bot.handlers.pins import (
        cmd_delpin,
        cmd_editpin,
        cmd_pin,
        cmd_repin,
        cmd_unpin,
        cmd_unpinall,
    )

    app.add_handler(CommandHandler("pinmsg", cmd_pin, filters=GROUP))
    app.add_handler(CommandHandler("unpinmsg", cmd_unpin, filters=GROUP))
    app.add_handler(CommandHandler("unpinall", cmd_unpinall, filters=GROUP))
    app.add_handler(CommandHandler("repin", cmd_repin, filters=GROUP))
    app.add_handler(CommandHandler("editpin", cmd_editpin, filters=GROUP))
    app.add_handler(CommandHandler("delpin", cmd_delpin, filters=GROUP))
    logger.info(f"[FACTORY] Pin handlers registered")

    # ── Password management handlers ──────────────────────────────────────
    from bot.handlers.password import cmd_clearpassword, cmd_setpassword, handle_password_dm

    app.add_handler(CommandHandler("setpassword", cmd_setpassword, filters=GROUP))
    app.add_handler(CommandHandler("clearpassword", cmd_clearpassword, filters=GROUP))
    app.add_handler(MessageHandler(PRIVATE & filters.TEXT & ~filters.COMMAND, handle_password_dm))
    logger.info(f"[FACTORY] Password handlers registered")

    # ── Copy settings handler ─────────────────────────────────────────────
    from bot.handlers.copy_settings import cmd_copy_settings

    app.add_handler(CommandHandler("copysettings", cmd_copy_settings, filters=GROUP))
    logger.info(f"[FACTORY] Copy settings handler registered")

    # ── Log channel handlers ──────────────────────────────────────────────
    from bot.handlers.log_channel import cmd_logchannel, cmd_setlog, cmd_unsetlog

    app.add_handler(CommandHandler("setlog", cmd_setlog, filters=GROUP))
    app.add_handler(CommandHandler("unsetlog", cmd_unsetlog, filters=GROUP))
    app.add_handler(CommandHandler("logchannel", cmd_logchannel, filters=GROUP))
    logger.info(f"[FACTORY] Log channel handlers registered")

    # ── Import / Export / Reset handlers ─────────────────────────────────
    from bot.handlers.import_export import cmd_export, cmd_import, cmd_reset, handle_reset_callback

    app.add_handler(CommandHandler("export", cmd_export, filters=GROUP))
    app.add_handler(CommandHandler("import", cmd_import, filters=GROUP))
    app.add_handler(CommandHandler("reset", cmd_reset, filters=GROUP))
    app.add_handler(
        CallbackQueryHandler(handle_reset_callback, pattern=r"^reset_(confirm:|cancel)")
    )
    logger.info(f"[FACTORY] Import/Export handlers registered")

    # ── Inline query handler ──────────────────────────────────────────────
    from telegram.ext import InlineQueryHandler

    from bot.handlers.inline_mode import handle_inline_query

    app.add_handler(InlineQueryHandler(handle_inline_query))
    logger.info(f"[FACTORY] Inline query handler registered")

    # ── Public command handlers ───────────────────────────────────────────
    from bot.handlers.public import (
        cmd_adminlist,
        cmd_groupinfo,
        cmd_invitelink,
        cmd_kickme,
        cmd_time,
    )

    app.add_handler(CommandHandler("time", cmd_time, filters=GROUP))
    app.add_handler(CommandHandler("kickme", cmd_kickme, filters=GROUP))
    app.add_handler(CommandHandler("adminlist", cmd_adminlist, filters=GROUP))
    app.add_handler(CommandHandler("staff", cmd_adminlist, filters=GROUP))
    app.add_handler(CommandHandler("invitelink", cmd_invitelink, filters=GROUP))
    app.add_handler(CommandHandler("groupinfo", cmd_groupinfo, filters=GROUP))
    logger.info(f"[FACTORY] Public command handlers registered")

    logger.info(f"[FACTORY] Application built successfully | is_primary={is_primary}")
    return app


async def setup_music_worker(app, bot_id: int, is_primary: bool, db):
    """
    Load music userbot from DB and attach MusicWorker to app.bot_data.
    For primary bot: load all accounts in pool (MUSIC_WORKER_COUNT).
    For clone bots: load their single account if configured.
    If no account found: set music_worker = None (commands show setup instructions).
    """
    import logging

    from pyrogram import Client

    from bot.userbot.music_worker import MusicWorker
    from bot.utils.crypto import decrypt_token
    from config import settings

    logger = logging.getLogger(__name__)

    if not db:
        app.bot_data["music_worker"] = None
        return

    owner_id = 0 if is_primary else bot_id
    rows = await db.fetch(
        "SELECT * FROM music_userbots WHERE owner_bot_id=$1 AND is_active=TRUE LIMIT 1", owner_id
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
            in_memory=True,
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
