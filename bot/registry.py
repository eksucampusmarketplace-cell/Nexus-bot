"""
bot/registry.py

In-memory map of bot_id → running PTB Application instance.
Built at startup, updated dynamically as clones are added/removed.

Thread safety: all mutations go through asyncio.Lock().
Read operations (get, get_all, count) are lock-free — safe for concurrent reads.

Key design decisions:
  - bot_id is always the Telegram numeric ID (permanent, never changes)
  - When replacing an existing entry, always stop the old app first
  - Registry does NOT persist — it is rebuilt from DB on every startup
"""

import asyncio
import logging
from telegram.ext import Application

logger = logging.getLogger(__name__)

_registry: dict[int, Application] = {}
_lock = asyncio.Lock()


async def register(bot_id: int, app: Application) -> None:
    """
    Add a PTB Application to the registry.
    If bot_id already exists, stops the old instance first.
    Logs: [REGISTRY] Registered bot_id={bot_id} @{username}
    """
    async with _lock:
        if bot_id in _registry:
            logger.warning(
                f"[REGISTRY] bot_id={bot_id} already registered — "
                f"stopping old instance before replacing"
            )
            try:
                await _registry[bot_id].stop()
                await _registry[bot_id].shutdown()
            except Exception as e:
                logger.error(f"[REGISTRY] Error stopping old instance for {bot_id}: {e}")

        _registry[bot_id] = app
        username = getattr(app.bot, "username", "unknown") if hasattr(app, "bot") else "unknown"
        logger.info(
            f"[REGISTRY] Registered bot_id={bot_id} "
            f"@{username} "
            f"| Total bots in registry: {len(_registry)}"
        )


async def deregister(bot_id: int) -> bool:
    """
    Remove and stop a PTB Application.
    Returns True if found and stopped, False if not found.
    Logs: [REGISTRY] Deregistered bot_id={bot_id}
    """
    async with _lock:
        app = _registry.pop(bot_id, None)
        if not app:
            logger.warning(
                f"[REGISTRY] Tried to deregister bot_id={bot_id} but it was not registered"
            )
            return False

        try:
            await app.stop()
            await app.shutdown()
        except Exception as e:
            logger.error(f"[REGISTRY] Error during shutdown of bot_id={bot_id}: {e}")

        logger.info(
            f"[REGISTRY] Deregistered bot_id={bot_id} " f"| Remaining bots: {len(_registry)}"
        )
        return True


def get(bot_id: int) -> Application | None:
    """Lock-free read. Returns None if not found."""
    return _registry.get(bot_id)


def get_all() -> dict[int, Application]:
    """Lock-free snapshot copy of the full registry."""
    return dict(_registry)


def count() -> int:
    """Total number of registered bots including primary."""
    return len(_registry)


def is_registered(bot_id: int) -> bool:
    return bot_id in _registry


def get_summary() -> list[dict]:
    """
    Returns a list of dicts summarizing registered bots.
    Safe to serialize — no PTB objects.
    Used by health check and debug routes.
    Format: [{bot_id, username, is_registered}]
    """
    return [
        {
            "bot_id": bot_id,
            "username": getattr(app.bot, "username", "unknown"),
            "is_registered": True,
        }
        for bot_id, app in _registry.items()
    ]
