import logging
from telegram.ext import Application, CommandHandler

logger = logging.getLogger(__name__)

ALIASES = {
    # Moderation
    "/w":   "/warn",
    "/uw":  "/unwarn",
    "/m":   "/mute",
    "/um":  "/unmute",
    "/tm":  "/tmute",
    "/b":   "/ban",
    "/ub":  "/unban",
    "/tb":  "/tban",
    "/k":   "/kick",
    "/p":   "/purge",
    "/d":   "/del",       # delete a message
    "/s":   "/silence",   # alias for lock
    "/r":   "/rules",

    # Reputation
    "+rep": "/giverep",
    "-rep": "/takerep",
    "/bal": "/balance",
    "/rep": "/reputation",

    # Notes
    "/n":   "/note",
    "/gn":  "/getnote",
    "/sn":  "/savednotes",

    # Info
    "/i":   "/info",
    "/wi":  "/whois",
    "/ci":  "/chatinfo",

    # Warnings
    "/ws":  "/warnstatus",
    "/wl":  "/warnlimit",
    "/wa":  "/warnaction",

    # Channel posting
    "/post":   "/channelpost",
    "/sched":  "/schedulepost",
    "/ap":     "/approvepost",
    "/cp":     "/cancelpost",
    "/ep":     "/editpost",
    "/dp":     "/deletepost",

    # More moderation
    "/unmuteall": "/unmute",
    "/unbanall":  "/unban",
    "/clearwarns": "/unwarn",
    "/warns":      "/warnstatus",
    "/sw":         "/setwelcome",
    "/sg":         "/setgoodbye",
    "/sr":         "/setrules",
    "/rw":         "/resetwelcome",
    "/rg":         "/resetgoodbye",
    "/rr":         "/resetrules",

    # Security
    "/sc":         "/captcha",
    "/antiraid":   "/raidmode",

    # Utilities
    "/afk":        "/setafk",
    "/pinner":     "/pin",
    "/unpinner":   "/unpin",
}

def register_aliases(app: Application, handlers: dict):
    """
    Register every alias as a CommandHandler pointing to the same
    function as its canonical command.
    handlers = { "/warn": warn_handler_func, ... }
    """
    count = 0
    for alias, canonical in ALIASES.items():
        if canonical in handlers and alias.startswith("/"):
            cmd = alias[1:]  # remove leading /
            app.add_handler(CommandHandler(cmd, handlers[canonical]))
            count += 1
            logger.debug(f"[ALIAS] Registered {alias} -> {canonical}")
    
    logger.info(f"[ALIAS] Registered {count} aliases")
