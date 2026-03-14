"""
bot/utils/rate_limiter.py

Token-bucket rate limiter for commands, reports, and other actions.
Pure Python implementation - swap to Redis for high-traffic groups.
"""

from collections import defaultdict
from time import time
from typing import Optional


class RateLimiter:
    """
    Token-bucket rate limiter.

    Usage:
        limiter = RateLimiter(max_calls=5, period=60)
        if not limiter.allow('user_123'):
            # rate limited

    Args:
        max_calls: Maximum number of calls allowed in the period
        period: Time window in seconds
    """

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls: dict = defaultdict(list)

    def allow(self, key: str) -> bool:
        """Check if action is allowed for the given key."""
        now = time()
        window = self._calls[key]

        # Remove expired entries
        cutoff = now - self.period
        self._calls[key] = [t for t in window if t > cutoff]

        # Check if under limit
        if len(self._calls[key]) >= self.max_calls:
            return False

        self._calls[key].append(now)
        return True

    def get_remaining(self, key: str) -> int:
        """Get remaining calls for this key."""
        now = time()
        cutoff = now - self.period
        self._calls[key] = [t for t in self._calls[key] if t > cutoff]
        return max(0, self.max_calls - len(self._calls[key]))

    def get_reset_time(self, key: str) -> float:
        """Get time in seconds until rate limit resets."""
        if not self._calls[key]:
            return 0
        now = time()
        cutoff = now - self.period
        valid_calls = [t for t in self._calls[key] if t > cutoff]
        if len(valid_calls) < self.max_calls:
            return 0
        return valid_calls[0] + self.period - now

    def reset(self, key: str):
        """Reset rate limit for a key."""
        self._calls.pop(key, None)


# Pre-built limiters for common use cases
command_limiter = RateLimiter(max_calls=10, period=60)  # 10 cmds/min
report_limiter = RateLimiter(max_calls=3, period=300)  # 3 reports/5min
clone_limiter = RateLimiter(max_calls=5, period=3600)  # 5 clones/hour
warn_limiter = RateLimiter(max_calls=20, period=60)  # 20 warns/min
broadcast_limiter = RateLimiter(max_calls=5, period=3600)  # 5 broadcasts/hour
webhook_limiter = RateLimiter(max_calls=10, period=60)  # 10 webhook tests/min
game_xp_limiter = RateLimiter(max_calls=50, period=3600)  # 50 game XP awards/hour


def format_wait_time(seconds: float) -> str:
    """Format seconds into human-readable wait time."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m"
    else:
        return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"
