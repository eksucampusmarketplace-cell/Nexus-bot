import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from bot.handlers.moderation.utils import publish_event
from db.client import db

log = logging.getLogger("antiraid")


@dataclass
class MemberProfile:
    user_id: int
    joined_at: float
    account_age_days: int = 0
    has_photo: bool = True
    has_bio: bool = False
    has_username: bool = True
    username: str = ""
    first_name: str = ""

    def suspicion_score(self) -> int:
        score = 0
        if self.account_age_days < 7:
            score += 40
        elif self.account_age_days < 30:
            score += 20

        if not self.has_photo:
            score += 25
        if not self.has_username:
            score += 10
        if not self.has_bio:
            score += 5

        # Simple name pattern check
        import re

        if re.search(r"\d{5,}", self.first_name):
            score += 30

        return min(100, score)


class RaidDetector:
    def __init__(self, redis, pool, bot):
        self.redis = redis
        self.pool = pool
        self.bot = bot
        self._settings_cache = {}

    async def on_member_join(self, chat_id: int, member: MemberProfile) -> str:
        # 1. Record join in Redis
        now = time.time()
        key = f"nexus:raid:joins:{chat_id}"
        if self.redis:
            await self.redis.zadd(key, {str(member.user_id): now})
            # 2. Calculate current join rate
            await self.redis.zremrangebyscore(key, 0, now - 60)
            joins_per_minute = await self.redis.zcard(key)
        else:
            joins_per_minute = 1  # Fallback

        # 3. Determine threat level
        settings = await self.get_settings(chat_id)
        threat_level = "green"
        if joins_per_minute >= settings.get("threshold_critical", 50):
            threat_level = "critical"
        elif joins_per_minute >= settings.get("threshold_red", 20):
            threat_level = "red"
        elif joins_per_minute >= settings.get("threshold_orange", 10):
            threat_level = "orange"
        elif joins_per_minute >= settings.get("threshold_yellow", 5):
            threat_level = "yellow"

        # 4. If threat level changed or high -> trigger response
        if threat_level != "green":
            await self._trigger_response(chat_id, threat_level, joins_per_minute)

        # 5. Score member
        score = member.suspicion_score()
        if (
            score > 80
            and settings.get("ban_suspicious_on_raid")
            and threat_level in ["red", "critical"]
        ):
            await self.bot.ban_chat_member(chat_id, member.user_id)
            log.info(f"Auto-banned suspicious member {member.user_id} in {chat_id}")

        return threat_level

    async def get_settings(self, chat_id: int) -> dict:
        if (
            chat_id in self._settings_cache
            and time.time() - self._settings_cache[chat_id]["time"] < 300
        ):
            return self._settings_cache[chat_id]["data"]

        row = await db.fetchrow("SELECT * FROM antiraid_settings WHERE chat_id = $1", chat_id)
        if not row:
            data = {
                "threshold_yellow": 5,
                "threshold_orange": 10,
                "threshold_red": 20,
                "threshold_critical": 50,
                "action_yellow": "alert",
                "action_orange": "captcha",
                "action_red": "lockdown",
                "action_critical": "lockdown_ban",
            }
        else:
            data = dict(row)

        self._settings_cache[chat_id] = {"time": time.time(), "data": data}
        return data

    async def _trigger_response(self, chat_id: int, threat_level: str, jpm: int):
        log.warning(f"[ANTIRAID] Threat level {threat_level} in {chat_id} ({jpm} joins/min)")
        await publish_event(
            chat_id, "raid_threat", {"level": threat_level, "joins_per_minute": jpm}
        )
        # Logic to activate lockdown etc would go here
