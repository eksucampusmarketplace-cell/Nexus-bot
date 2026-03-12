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
    from bot.handlers.music import (
        play_command, skip_command, queue_command, stop_command,
        pause_command, resume_command, nowplaying_command,
        music_callback_handler
    )
    from bot.handlers.music_advanced import (
        play_youtube_command, volume_command, repeat_command,
        shuffle_command, playlist_create_command, playlist_list_command,
        playlist_play_command, playlist_delete_command, history_command,
        search_command, sync_command, music_settings_command,
        music_advanced_callback_handler
    )
    from bot.handlers.errors import error_handler as global_error_handler
    
    # ── Basic commands (all bots) ─────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("panel", panel))
    
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
    app.add_handler(CommandHandler("play",           play_command,           filters=GROUP))
    app.add_handler(CommandHandler("skip",           skip_command,           filters=GROUP))
    app.add_handler(CommandHandler("queue",          queue_command,          filters=GROUP))
    app.add_handler(CommandHandler("stop",           stop_command,           filters=GROUP))
    app.add_handler(CommandHandler("pause",          pause_command,          filters=GROUP))
    app.add_handler(CommandHandler("resume",         resume_command,         filters=GROUP))
    app.add_handler(CommandHandler("nowplaying",     nowplaying_command,     filters=GROUP))

    # ── Advanced music commands (groups only) ─────────────────────────────
    app.add_handler(CommandHandler("play_youtube",   play_youtube_command,   filters=GROUP))
    app.add_handler(CommandHandler("volume",         volume_command,         filters=GROUP))
    app.add_handler(CommandHandler("repeat",         repeat_command,         filters=GROUP))
    app.add_handler(CommandHandler("shuffle",        shuffle_command,        filters=GROUP))
    app.add_handler(CommandHandler("playlist_create", playlist_create_command, filters=GROUP))
    app.add_handler(CommandHandler("playlist_list",   playlist_list_command,   filters=GROUP))
    app.add_handler(CommandHandler("playlist_play",   playlist_play_command,   filters=GROUP))
    app.add_handler(CommandHandler("playlist_delete", playlist_delete_command, filters=GROUP))
    app.add_handler(CommandHandler("history",        history_command,        filters=GROUP))
    app.add_handler(CommandHandler("search",         search_command,         filters=GROUP))
    app.add_handler(CommandHandler("sync",           sync_command,           filters=GROUP))
    app.add_handler(CommandHandler("music_settings", music_settings_command, filters=GROUP))
    
    # ── Clone commands — PRIMARY BOT ONLY ─────────────────────────────────
    if is_primary:
        from bot.handlers.clone import (
            clone_command_handler,
            myclones_command_handler,
            token_input_handler,
            clone_callback_handler
        )
        app.add_handler(CommandHandler("clone",    clone_command_handler,    filters=PRIVATE))
        app.add_handler(CommandHandler("myclones", myclones_command_handler, filters=PRIVATE))
        app.add_handler(MessageHandler(
            PRIVATE & filters.TEXT & filters.Regex(r'^\d{8,10}:[\w-]{35}$'),
            token_input_handler
        ))
        app.add_handler(CallbackQueryHandler(clone_callback_handler, pattern=r'^clone:'))
        logger.info(f"[FACTORY] Clone handlers registered (primary bot only)")
    else:
        logger.info(f"[FACTORY] Clone handlers SKIPPED (clone bot)")
    
    # ── Captcha callbacks (all bots) ──────────────────────────────────────
    app.add_handler(CallbackQueryHandler(captcha_callback_handler, pattern=r'^captcha:'))

    # ── Music callbacks (all bots) ─────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(music_callback_handler, pattern=r'^music:skip|stop|queue|pause'))
    app.add_handler(CallbackQueryHandler(music_advanced_callback_handler, pattern=r'^music:vol|repeat|shuffle'))
    
    # ── AutoMod message handlers (groups, priority groups 1-3) ───────────
    app.add_handler(MessageHandler(GROUP & filters.ALL,  antiflood_handler), group=1)
    app.add_handler(MessageHandler(GROUP & filters.TEXT, antispam_handler),  group=2)
    app.add_handler(MessageHandler(GROUP & filters.TEXT, antilink_handler),  group=3)
    
    # ── New member joins ──────────────────────────────────────────────────
    app.add_handler(ChatMemberHandler(new_member_handler, ChatMemberHandler.CHAT_MEMBER))
    
    # ── Global error handler ──────────────────────────────────────────────
    app.add_error_handler(global_error_handler)
    
    logger.info(f"[FACTORY] Application built successfully | is_primary={is_primary}")
    return app


# Keep backward compatibility
def create_bot_app(token: str) -> Application:
    """Legacy function - use create_application instead."""
    return create_application(token, is_primary=False)
