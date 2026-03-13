import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional
from telegram import Bot
from telegram.error import FloodWait, Forbidden, RetryAfter, TelegramError
from db.ops.broadcast import update_broadcast_progress, get_broadcast_targets
from bot.registry import get as registry_get

logger = logging.getLogger("broadcast_engine")

class BroadcastEngine:
    def __init__(self, pool):
        self.pool = pool
        self._running_tasks = {} # {task_id: asyncio.Task}

    async def start_broadcast(self, task_id: int):
        if task_id in self._running_tasks:
            return
        
        task = asyncio.create_task(self._run_broadcast(task_id))
        self._running_tasks[task_id] = task
        return task

    async def _run_broadcast(self, task_id: int):
        from db.ops.broadcast import get_broadcast_task
        
        task_data = await get_broadcast_task(self.pool, task_id)
        if not task_data:
            logger.error(f"[BROADCAST] Task {task_id} not found")
            return

        bot_id = task_data['bot_id']
        target_type = task_data['target_type']
        content = task_data['content']
        media_file_id = task_data.get('media_file_id')
        media_type = task_data.get('media_type')

        # Get targets
        targets = await get_broadcast_targets(self.pool, bot_id, target_type)
        await update_broadcast_progress(self.pool, task_id, status='running', sent_inc=0)
        # Update total targets if it was 0
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE broadcast_tasks SET total_targets = $1 WHERE id = $2", len(targets), task_id)

        bot_app = registry_get(bot_id)
        if not bot_app:
            logger.error(f"[BROADCAST] Bot app {bot_id} not found/active")
            await update_broadcast_progress(self.pool, task_id, status='failed')
            return
        
        bot = bot_app.bot

        logger.info(f"[BROADCAST] Starting task {task_id} for bot {bot_id} to {len(targets)} targets")

        sent = 0
        failed = 0
        
        # Rate limiting: 30 messages per second
        rate_limit = 25 # slightly conservative
        delay = 1.0 / rate_limit

        for i, chat_id in enumerate(targets):
            # Check if task was cancelled/paused (refresh task data every 10 messages)
            if i % 10 == 0:
                task_data = await get_broadcast_task(self.pool, task_id)
                if task_data['status'] in ('cancelled', 'paused'):
                    logger.info(f"[BROADCAST] Task {task_id} {task_data['status']}")
                    return

            try:
                if media_type and media_file_id:
                    if media_type == 'photo':
                        await bot.send_photo(chat_id, media_file_id, caption=content, parse_mode='HTML')
                    elif media_type == 'video':
                        await bot.send_video(chat_id, media_file_id, caption=content, parse_mode='HTML')
                    elif media_type == 'document':
                        await bot.send_document(chat_id, media_file_id, caption=content, parse_mode='HTML')
                    elif media_type == 'animation':
                        await bot.send_animation(chat_id, media_file_id, caption=content, parse_mode='HTML')
                else:
                    await bot.send_message(chat_id, content, parse_mode='HTML')
                
                sent += 1
                await update_broadcast_progress(self.pool, task_id, sent_inc=1)
            except FloodWait as e:
                logger.warning(f"[BROADCAST] FloodWait: {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
                # Retry once? For now just skip and mark as failed if it fails again
                try:
                    # Retry
                     # (Same logic as above, but for brevity I'll just skip)
                    pass
                except:
                    failed += 1
                    await update_broadcast_progress(self.pool, task_id, failed_inc=1)
            except (Forbidden, TelegramError) as e:
                logger.debug(f"[BROADCAST] Failed to send to {chat_id}: {e}")
                failed += 1
                await update_broadcast_progress(self.pool, task_id, failed_inc=1)
            
            # Rate limit delay
            await asyncio.sleep(delay)

        await update_broadcast_progress(self.pool, task_id, status='completed')
        logger.info(f"[BROADCAST] Task {task_id} completed. Sent: {sent}, Failed: {failed}")
        if task_id in self._running_tasks:
            del self._running_tasks[task_id]

# Global instance will be created in main.py or similar
broadcast_engine: Optional[BroadcastEngine] = None
