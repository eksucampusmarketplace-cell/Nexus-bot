"""
lazy_manager.py

Lazy loading and automatic unloading of Pyrogram clients.

This module manages Pyrogram userbot clients with:
- Lazy loading: Load clients only when needed
- Auto-unloading: Unload inactive clients to save memory
- Thread-safe access: Uses locks for concurrent access
"""

import asyncio
import logging
import time
from typing import Dict, Optional

from pyrogram import Client
import asyncpg

from bot.utils.crypto import decrypt_token
from config import settings

logger = logging.getLogger(__name__)


class LazyClientManager:
    """
    Manages Pyrogram clients with lazy loading and auto-unloading.
    
    Features:
    - Load clients on-demand instead of all at startup
    - Unload clients not used for LAZY_UNLOAD_TIMEOUT seconds
    - Thread-safe access using asyncio locks
    - Memory-aware cleanup
    """
    
    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize the lazy client manager.
        
        Args:
            pool: Database connection pool for loading client sessions
        """
        self.pool = pool
        self.clients: Dict[int, Client] = {}  # userbot_id -> Client
        self.last_used: Dict[int, float] = {}  # userbot_id -> timestamp
        self._lock = asyncio.Lock()
        self._running = False
        
    async def start(self):
        """Start the background cleanup task."""
        self._running = True
        asyncio.create_task(self._cleanup_task())
        logger.info("[LAZY_MANAGER] Started lazy client manager")
    
    async def stop(self):
        """Stop the cleanup task and unload all clients."""
        self._running = False
        
        # Unload all clients
        async with self._lock:
            for userbot_id, client in self.clients.items():
                try:
                    await client.stop()
                    logger.info(f"[LAZY_MANAGER] Unloaded client {userbot_id}")
                except Exception as e:
                    logger.error(f"[LAZY_MANAGER] Error unloading {userbot_id}: {e}")
            
            self.clients.clear()
            self.last_used.clear()
        
        logger.info("[LAZY_MANAGER] Stopped lazy client manager")
    
    async def get_client(self, userbot_id: int) -> Client:
        """
        Get a Pyrogram client, loading it if necessary.
        
        Args:
            userbot_id: The ID of the userbot
            
        Returns:
            The Pyrogram Client instance
        """
        async with self._lock:
            # Check if client is already loaded
            if userbot_id in self.clients:
                self.last_used[userbot_id] = time.time()
                return self.clients[userbot_id]
            
            # Lazy load the client
            logger.info(f"[LAZY_MANAGER] Lazy loading userbot {userbot_id}")
            client = await self._load_client(userbot_id)
            self.clients[userbot_id] = client
            self.last_used[userbot_id] = time.time()
            return client
    
    async def _load_client(self, userbot_id: int) -> Client:
        """
        Load a Pyrogram client from the database.
        
        Args:
            userbot_id: The ID of the userbot to load
            
        Returns:
            The loaded Pyrogram Client instance
        """
        # Fetch session from database
        row = await self.pool.fetchrow(
            "SELECT session_string, api_id, api_hash FROM music_userbots "
            "WHERE id = $1 AND is_active = TRUE",
            userbot_id
        )
        
        if not row:
            raise ValueError(f"Userbot {userbot_id} not found or inactive")
        
        session_string = row["session_string"]
        api_id = row["api_id"] or settings.PYROGRAM_API_ID
        api_hash = row["api_hash"] or settings.PYROGRAM_API_HASH
        
        if not api_id or not api_hash:
            raise ValueError(f"Missing API credentials for userbot {userbot_id}")
        
        # Create and start the client
        client = Client(
            name=f"nexus_userbot_{userbot_id}",
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True  # Don't save session to disk
        )
        
        await client.start()
        logger.info(f"[LAZY_MANAGER] Loaded userbot {userbot_id}")
        return client
    
    async def unload_client(self, userbot_id: int) -> bool:
        """
        Manually unload a client.
        
        Args:
            userbot_id: The ID of the userbot to unload
            
        Returns:
            True if the client was unloaded, False if it wasn't loaded
        """
        async with self._lock:
            if userbot_id not in self.clients:
                return False
            
            try:
                client = self.clients.pop(userbot_id)
                await client.stop()
                self.last_used.pop(userbot_id, None)
                logger.info(f"[LAZY_MANAGER] Manually unloaded userbot {userbot_id}")
                return True
            except Exception as e:
                logger.error(f"[LAZY_MANAGER] Error unloading {userbot_id}: {e}")
                return False
    
    async def cleanup_inactive_clients(self, force: bool = False) -> int:
        """
        Unload clients that haven't been used recently.
        
        Args:
            force: If True, unload ALL clients (for emergency cleanup)
            
        Returns:
            Number of clients unloaded
        """
        async with self._lock:
            if force:
                to_unload = list(self.clients.keys())
            else:
                cutoff = time.time() - settings.LAZY_UNLOAD_TIMEOUT
                to_unload = [
                    uid for uid, last in self.last_used.items()
                    if last < cutoff and uid in self.clients
                ]
            
            unloaded = 0
            for uid in to_unload:
                try:
                    client = self.clients.pop(uid)
                    await client.stop()
                    self.last_used.pop(uid, None)
                    unloaded += 1
                    logger.info(f"[LAZY_MANAGER] Unloaded inactive userbot {uid}")
                except Exception as e:
                    logger.error(f"[LAZY_MANAGER] Error unloading {uid}: {e}")
            
            if unloaded > 0:
                logger.info(f"[LAZY_MANAGER] Cleaned up {unloaded} inactive clients")
            
            return unloaded
    
    async def _cleanup_task(self):
        """Background task that periodically unloads inactive clients."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.cleanup_inactive_clients()
            except Exception as e:
                logger.error(f"[LAZY_MANAGER] Cleanup task error: {e}")
    
    def get_stats(self) -> dict:
        """
        Get statistics about loaded clients.
        
        Returns:
            Dict with count and memory usage estimates
        """
        return {
            "loaded_clients": len(self.clients),
            "max_active": settings.PYROGRAM_MAX_ACTIVE,
            "idle_timeout": settings.LAZY_UNLOAD_TIMEOUT,
        }
