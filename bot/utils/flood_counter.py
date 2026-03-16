import logging
import time
from db.client import db

logger = logging.getLogger(__name__)

class FloodCounter:
    """Use Redis if available, fall back to in-memory dict if not."""
    
    _in_memory_counts = {} # {(chat_id, user_id): [timestamp, timestamp, ...]}
    
    async def increment(self, chat_id: int, user_id: int, window_secs: int) -> int:
        """Increment counter. Return current count in window."""
        if db.redis:
            try:
                key = f"flood:{chat_id}:{user_id}"
                # INCR then EXPIRE
                count = await db.redis.incr(key)
                if count == 1:
                    await db.redis.expire(key, window_secs)
                return count
            except Exception as e:
                logger.debug(f"Redis flood counter error: {e}")
                # Fallback to in-memory on redis failure
                pass
        
        # In-memory fallback
        now = time.time()
        key = (chat_id, user_id)
        if key not in self._in_memory_counts:
            self._in_memory_counts[key] = []
            
        # Add current timestamp
        self._in_memory_counts[key].append(now)
        
        # Cleanup old timestamps
        cutoff = now - window_secs
        self._in_memory_counts[key] = [ts for ts in self._in_memory_counts[key] if ts > cutoff]
        
        # Occasionally cleanup other keys to prevent memory leak
        # Not implemented here for brevity, but recommended
        
        return len(self._in_memory_counts[key])

    async def is_flooding(self, chat_id: int, user_id: int,
                          limit: int, window_secs: int) -> bool:
        """Checks if the user is currently flooding."""
        count = await self.increment(chat_id, user_id, window_secs)
        return count > limit

# Module-level singleton
flood_counter = FloodCounter()
