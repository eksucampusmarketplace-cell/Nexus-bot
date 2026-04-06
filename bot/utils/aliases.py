import logging

from telegram.ext import Application, CommandHandler

logger = logging.getLogger(__name__)

ALIASES = {
    # Moderation
    "/w": "/warn",
    "/uw": "/unwarn",
    "/m": "/mute",
    "/um": "/unmute",
    "/tm": "/tmute",
    "/b": "/ban",
    "/ub": "/unban",
    "/tb": "/tban",
    "/k": "/kick",
    "/p": "/purge",
    "/d": "/del",
    "/s": "/lock",
    "/r": "/rules",
    # Notes
    "/n": "/note",
    "/gn": "/note",
    "/sn": "/notes",
    # Info
    "/i": "/info",
    "/wi": "/info",
    "/ci": "/groupinfo",
    # Warnings
    "/ws": "/warns",
    "/wl": "/warnlimit",
    "/wa": "/warnmode",
    # Channel posting
    "/post": "/channelpost",
    "/sched": "/schedulepost",
    "/ap": "/approvepost",
    "/cp": "/cancelpost",
    "/ep": "/editpost",
    "/dp": "/deletepost",
    # More moderation
    "/unmuteall": "/unmute",
    "/unbanall": "/unban",
    "/clearwarns": "/resetwarns",
    "/sw": "/setwelcome",
    "/sg": "/setgoodbye",
    "/sr": "/setrules",
    "/rw": "/resetwelcome",
    "/rg": "/resetgoodbye",
    "/rr": "/resetrules",
    # Security
    "/sc": "/captcha",
    "/raidmode": "/antiraid",
    # Admin requests
    "/areq": "/admin_requests",
    "/areq_stats": "/admin_req_stats",
    "/set_areq": "/set_admin_requests",
    # Utilities
    "/afk": "/setafk",
    "/pinner": "/pin",
    "/unpinner": "/unpin",
    "/verify": "/unrestrict",
    "/unhold": "/unrestrict",
    "/hold": "/mute",
}


def get_aliases_for_command(canonical: str) -> list:
    """Return all aliases that map to the given canonical command."""
    return [alias for alias, cmd in ALIASES.items() if cmd == canonical]


def register_aliases(app: Application, handlers: dict, quiet: bool = False):
    """
    Register every alias as a CommandHandler pointing to the same
    function as its canonical command.
    handlers = { "/warn": warn_handler_func, ... }
    """
    count = 0
    skipped = []
    for alias, canonical in ALIASES.items():
        if not alias.startswith("/"):
            continue
        if canonical in handlers:
            cmd = alias[1:]  # remove leading /
            app.add_handler(CommandHandler(cmd, handlers[canonical]))
            count += 1
            logger.debug(f"[ALIAS] Registered {alias} -> {canonical}")
        elif not quiet:
            skipped.append(f"{alias}->{canonical}")

    if skipped and not quiet:
        logger.warning(f"[ALIAS] Skipped (no handler): {', '.join(skipped)}")
    if count > 0 or not quiet:
        logger.info(f"[ALIAS] Registered {count} aliases")
