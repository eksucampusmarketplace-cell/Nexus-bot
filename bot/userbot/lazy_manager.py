"""
bot/userbot/lazy_manager.py

Manages Pyrogram client lifecycle with lazy loading and LRU eviction.

Public API:
  get_client(bot_id) → Pyrogram Client | None
    Returns active client, loading from DB if needed.
    Evicts LRU client if PYROGRAM_MAX_ACTIVE exceeded.
    Returns None if no session configured for bot.

  release_client(bot_id)
    Mark client as no longer actively needed.
    Does NOT unload — just updates last_used timestamp.
    Actual unload happens via _unload_idle_task.

  force_unload(bot_id)
    Immediately disconnect and remove client.

  get_memory_usage() → dict
    Returns current memory stats.

Logs prefix: [LAZY]
"""

import asyncio
import logging
import time
import os
from collections import OrderedDict

import psutil
from pyrogram import Client

from config import settings
from bot.utils.crypto import decrypt_token

log = logging.getLogger("lazy_manager")


class LazyClientManager:

    def __init__(self, db):
        self.db = db
        self._clients:    dict[int, Client]  = {}
        # bot_id → active Pyrogram client
        self._last_used:  dict[int, float]   = {}
        # bot_id → timestamp of last use
        self._loading:    set[int]           = set()
        # bot_ids currently being loaded (prevent double-load)
        self._lock        = asyncio.Lock()
        self._started     = False


    async def start(self):
        """Start background tasks."""
        self._started = True
        asyncio.create_task(self._unload_idle_task())
        asyncio.create_task(self._memory_monitor_task())
        log.info("[LAZY] LazyClientManager started")


    async def get_client(self, bot_id: int) -> Client | None:
        """
        Get Pyrogram client for bot_id.
        Loads from DB if not active. Evicts LRU if at capacity.
        Returns None if no session configured.
        """
        async with self._lock:
            # Already loaded
            if bot_id in self._clients:
                self._last_used[bot_id] = time.time()
                return self._clients[bot_id]

            # Currently loading (avoid double-load)
            if bot_id in self._loading:
                pass  # wait below

        # Wait for ongoing load if any
        if bot_id in self._loading:
            for _ in range(20):  # wait up to 5s
                await asyncio.sleep(0.25)
                if bot_id in self._clients:
                    self._last_used[bot_id] = time.time()
                    return self._clients[bot_id]
            return None

        # Load from DB
        return await self._load_client(bot_id)


    async def _load_client(self, bot_id: int) -> Client | None:
        """Load Pyrogram client from DB. Evict LRU if needed."""
        self._loading.add(bot_id)
        try:
            # Get session from DB
            row = await self.db.fetchrow(
                "SELECT session_string FROM music_userbots "
                "WHERE owner_bot_id=$1 AND is_active=TRUE LIMIT 1",
                bot_id
            )
            if not row:
                log.debug(f"[LAZY] No session found | bot={bot_id}")
                return None

            # Evict LRU if at capacity
            async with self._lock:
                if len(self._clients) >= settings.PYROGRAM_MAX_ACTIVE:
                    await self._evict_lru()

            raw = decrypt_token(row["session_string"])
            client = Client(
                name=f"lazy_{bot_id}",
                api_id=settings.PYROGRAM_API_ID,
                api_hash=settings.PYROGRAM_API_HASH,
                session_string=raw,
                in_memory=True
            )
            await client.start()

            async with self._lock:
                self._clients[bot_id]   = client
                self._last_used[bot_id] = time.time()

            log.info(f"[LAZY] Client loaded | bot={bot_id} active={len(self._clients)}")
            return client

        except Exception as e:
            log.error(f"[LAZY] Load failed | bot={bot_id} error={e}")
            return None
        finally:
            self._loading.discard(bot_id)


    async def _evict_lru(self):
        """Evict the least recently used client. Called within lock."""
        if not self._last_used:
            return
        lru_bot = min(self._last_used, key=self._last_used.get)
        await self._disconnect(lru_bot)
        log.info(f"[LAZY] LRU evicted | bot={lru_bot}")


    async def release_client(self, bot_id: int):
        """Update last_used. Does not unload."""
        if bot_id in self._last_used:
            self._last_used[bot_id] = time.time()


    async def force_unload(self, bot_id: int):
        """Immediately disconnect and remove client."""
        async with self._lock:
            await self._disconnect(bot_id)
        log.info(f"[LAZY] Force unloaded | bot={bot_id}")


    async def _disconnect(self, bot_id: int):
        """Disconnect and remove client. Must be called within lock."""
        client = self._clients.pop(bot_id, None)
        self._last_used.pop(bot_id, None)
        if client:
            try:
                await client.stop()
            except Exception:
                pass


    async def _unload_idle_task(self):
        """Every 5 min: unload clients idle longer than LAZY_UNLOAD_TIMEOUT."""
        while self._started:
            await asyncio.sleep(300)
            try:
                now     = time.time()
                to_evict = [
                    bot_id for bot_id, last in self._last_used.items()
                    if now - last > settings.LAZY_UNLOAD_TIMEOUT
                ]
                async with self._lock:
                    for bot_id in to_evict:
                        await self._disconnect(bot_id)
                        log.info(f"[LAZY] Idle unload | bot={bot_id}")
            except Exception as e:
                log.warning(f"[LAZY] Unload task error | {e}")


    async def _memory_monitor_task(self):
        """Every 5 min: check process memory, force-evict if critical."""
        while self._started:
            await asyncio.sleep(300)
            try:
                usage = self.get_memory_usage()
                mb    = usage["rss_mb"]

                if mb > settings.MEMORY_CRITICAL_MB:
                    log.error(
                        f"[LAZY] CRITICAL memory | {mb}MB — force evicting all idle clients"
                    )
                    # Force unload ALL clients not used in last 5 min
                    now = time.time()
                    async with self._lock:
                        to_evict = [
                            bot_id for bot_id, last in self._last_used.items()
                            if now - last > 300
                        ]
                        for bot_id in to_evict:
                            await self._disconnect(bot_id)

                elif mb > settings.MEMORY_WARN_MB:
                    log.warning(f"[LAZY] High memory | {mb}MB")

                else:
                    log.debug(
                        f"[LAZY] Memory ok | {mb}MB | "
                        f"active_clients={len(self._clients)}"
                    )

            except Exception as e:
                log.warning(f"[LAZY] Memory monitor error | {e}")


    def get_memory_usage(self) -> dict:
        """Return current process memory stats."""
        try:
            proc = psutil.Process(os.getpid())
            mem  = proc.memory_info()
            return {
                "rss_mb":       mem.rss // (1024 * 1024),
                "vms_mb":       mem.vms // (1024 * 1024),
                "active_clients": len(self._clients),
                "client_bot_ids": list(self._clients.keys()),
            }
        except Exception:
            return {"rss_mb": 0, "vms_mb": 0, "active_clients": 0}
