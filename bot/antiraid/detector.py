"""
bot/antiraid/detector.py

Enhanced anti-raid detection with behavioral fingerprinting and spam scoring.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set

from bot.handlers.moderation.utils import publish_event
from db.client import db

log = logging.getLogger("antiraid")

# Anchor points for account age estimation from Telegram user ID
# These are approximate calibration points based on known ID/date pairs
ID_AGE_ANCHORS = [
    (100_000_000, datetime(2014, 1, 1, tzinfo=timezone.utc)),
    (1_000_000_000, datetime(2019, 1, 1, tzinfo=timezone.utc)),
    (5_000_000_000, datetime(2022, 1, 1, tzinfo=timezone.utc)),
    (7_000_000_000, datetime(2023, 6, 1, tzinfo=timezone.utc)),
    (9_000_000_000, datetime(2024, 6, 1, tzinfo=timezone.utc)),
]


def estimate_account_age_from_id(user_id: int) -> int:
    """
    Estimate account age in days from Telegram user ID.
    Telegram user IDs are roughly sequential and increase over time.
    Uses linear interpolation between known anchor points.
    """
    if user_id < 0:
        # Negative IDs are special (e.g., channels), treat as old
        return 9999
    
    # Find the anchor points to interpolate between
    lower_anchor = None
    upper_anchor = None
    
    for i, (anchor_id, anchor_date) in enumerate(ID_AGE_ANCHORS):
        if user_id < anchor_id:
            upper_anchor = (anchor_id, anchor_date)
            if i > 0:
                lower_anchor = ID_AGE_ANCHORS[i - 1]
            break
        lower_anchor = (anchor_id, anchor_date)
    
    now = datetime.now(timezone.utc)
    
    if lower_anchor is None:
        # Very high ID - assume very recent
        return 0
    
    if upper_anchor is None:
        # Low ID - interpolate beyond last anchor
        return max(0, (now - lower_anchor[1]).days)
    
    # Linear interpolation between anchors
    lower_id, lower_date = lower_anchor
    upper_id, upper_date = upper_anchor
    
    ratio = (user_id - lower_id) / (upper_id - lower_id)
    estimated_date = lower_date + (upper_date - lower_date) * ratio
    
    age_days = max(0, (now - estimated_date).days)
    return age_days


# Known spam name patterns
SPAM_NAME_PATTERNS = [
    r"^user\d{5,}$",  # user12345
    r"^User\d{5,}$",
    r"^USER\d{5,}$",
    r"^\d{5,}$",  # Just numbers
    r"^[a-zA-Z]{2,3}\d{5,}$",  # ab12345
    r"^\d{5,}[a-zA-Z]{2,3}$",  # 12345ab
    r"^User[A-Z]{1,3}\d{3,}$",  # UserABC123
    r"^Test\d+$",  # Test123
    r"^Guest\d+$",
    r"^New\d+User$",
    r"^User[_\-\.]?\d+$",
    r"^[a-z]{5,}\d{3,}[a-z]{0,3}$",  # random string with numbers
]

SPAM_NAME_REGEX = [re.compile(p, re.IGNORECASE) for p in SPAM_NAME_PATTERNS]


def matches_spam_name_pattern(name: str) -> bool:
    """Check if name matches known spam account patterns."""
    if not name:
        return False
    for pattern in SPAM_NAME_REGEX:
        if pattern.match(name):
            return True
    return False


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
    last_name: str = ""
    
    # Computed from fingerprint
    name_matches_pattern: bool = False
    fingerprint: dict = field(default_factory=dict)
    
    def compute_fingerprint(self) -> dict:
        """Generate a fingerprint dict for this member."""
        full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()
        
        self.name_matches_pattern = matches_spam_name_pattern(full_name)
        
        self.fingerprint = {
            "user_id": self.user_id,
            "account_age_days": self.account_age_days,
            "has_photo": self.has_photo,
            "has_username": self.has_username,
            "has_bio": self.has_bio,
            "full_name": full_name,
            "name_matches_pattern": self.name_matches_pattern,
        }
        return self.fingerprint
    
    # Weighted score components
    SCORE_WEIGHTS = {
        "account_age_lt_7_days": 30,
        "account_age_lt_30_days": 15,
        "no_profile_photo": 25,
        "no_username": 15,
        "no_bio": 5,
        "name_matches_pattern": 20,
    }
    
    def suspicion_score(self) -> int:
        """Calculate suspicion score based on all signals."""
        score = 0
        
        # Account age
        if self.account_age_days < 7:
            score += self.SCORE_WEIGHTS["account_age_lt_7_days"]
        elif self.account_age_days < 30:
            score += self.SCORE_WEIGHTS["account_age_lt_30_days"]
        
        # Profile details
        if not self.has_photo:
            score += self.SCORE_WEIGHTS["no_profile_photo"]
        if not self.has_username:
            score += self.SCORE_WEIGHTS["no_username"]
        if not self.has_bio:
            score += self.SCORE_WEIGHTS["no_bio"]
        
        # Name patterns
        if self.name_matches_pattern:
            score += self.SCORE_WEIGHTS["name_matches_pattern"]
        
        # First name digit check (legacy)
        if re.search(r"\d{5,}", self.first_name or ""):
            score += 10
        
        return min(100, score)


@dataclass 
class MessageFingerprint:
    """Fingerprint for message content similarity detection."""
    user_id: int
    chat_id: int
    message_text: str
    timestamp: float
    
    content_hash: str = ""
    forward_origin: str = ""
    
    def __post_init__(self):
        # Simple hash for content comparison
        self.content_hash = str(hash(self.message_text.lower().strip()[:200]))
    
    def similarity_to(self, other: "MessageFingerprint") -> float:
        """Return similarity ratio (0.0 to 1.0) using SequenceMatcher."""
        return SequenceMatcher(
            None, 
            self.message_text.lower().strip(), 
            other.message_text.lower().strip()
        ).ratio()


class JoinCluster:
    """Represents a cluster of users who joined together."""
    user_ids: List[int] = field(default_factory=list)
    joined_at_start: float = 0.0
    joined_at_end: float = 0.0
    
    # Aggregate fingerprints
    has_photo: bool = False
    has_username: bool = False
    account_ages: List[int] = field(default_factory=list)
    name_patterns: List[bool] = field(default_factory=list)
    
    def add_member(self, profile: MemberProfile):
        """Add a member to this cluster."""
        self.user_ids.append(profile.user_id)
        
        if self.joined_at_start == 0:
            self.joined_at_start = profile.joined_at
        self.joined_at_end = profile.joined_at
        
        # Aggregate signals
        self.has_photo = self.has_photo or profile.has_photo
        self.has_username = self.has_username or profile.has_username
        self.account_ages.append(profile.account_age_days)
        self.name_patterns.append(profile.name_matches_pattern)
    
    def duration_seconds(self) -> float:
        """Return the duration of this join cluster."""
        if self.joined_at_start == 0:
            return 0
        return self.joined_at_end - self.joined_at_start
    
    def is_coordinated(self) -> bool:
        """
        Check if this looks like a coordinated raid.
        Criteria:
        - 3+ members joined within 60 seconds
        - Most have no photo
        - Most have no username  
        - Most have high user IDs (young accounts)
        """
        if len(self.user_ids) < 3:
            return False
        
        # Check timing
        if self.duration_seconds() > 60:
            return False
        
        # Count flagged members
        no_photo_count = sum(1 for p in self.has_photo if not p)
        no_username_count = sum(1 for u in self.has_username if not u)
        young_count = sum(1 for age in self.account_ages if age < 30)
        
        flagged_count = no_photo_count + no_username_count + young_count
        
        # If majority are flagged
        return flagged_count >= len(self.user_ids) * 0.6


class RaidDetector:
    def __init__(self, redis, pool, bot):
        self.redis = redis
        self.pool = pool
        self.bot = bot
        self._settings_cache = {}
        self._join_cache: Dict[int, List[MemberProfile]] = {}  # chat_id -> recent joins
        self._message_cache: Dict[int, List[MessageFingerprint]] = {}  # chat_id -> recent messages
    
    async def create_profile_from_user(self, user, bot) -> MemberProfile:
        """
        Create a MemberProfile from a Telegram User object.
        Includes API calls to check profile photo and bio.
        """
        profile = MemberProfile(
            user_id=user.id,
            joined_at=time.time(),
            has_username=bool(user.username),
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
        )
        
        # Estimate account age from ID
        profile.account_age_days = estimate_account_age_from_id(user.id)
        
        # Check for profile photo via API
        try:
            photos = await bot.get_user_profile_photos(user.id, limit=1)
            profile.has_photo = photos.total_count > 0
        except Exception:
            # API call failed, assume no photo
            profile.has_photo = False
        
        # Check for bio/about (requires get_chat)
        try:
            chat_member = await bot.get_chat_member(user.id, user.id)
            profile.has_bio = bool(getattr(chat_member.user, 'bio', None))
        except Exception:
            profile.has_bio = False
        
        # Compute fingerprint
        profile.compute_fingerprint()
        
        return profile
    
    async def check_join_cluster(self, chat_id: int) -> Optional[JoinCluster]:
        """
        Check if recent joins form a coordinated cluster.
        Returns cluster if detected, None otherwise.
        """
        if not self.redis:
            return None
        
        now = time.time()
        key = f"nexus:raid:joins:{chat_id}"
        
        try:
            # Get all joins in the last 60 seconds with their timestamps
            recent = await self.redis.zrangebyscore(key, now - 60, now)
            if not recent or len(recent) < 3:
                return None
            
            # Get detailed data for each join
            # We store JSON in the value field
            cluster = JoinCluster()
            
            for uid_str in recent:
                try:
                    data = await self.redis.hget(f"nexus:raid:member:{chat_id}", uid_str)
                    if data:
                        import json
                        member_data = json.loads(data)
                        # Reconstruct profile
                        profile = MemberProfile(
                            user_id=int(uid_str),
                            joined_at=member_data.get("joined_at", now),
                            account_age_days=member_data.get("account_age_days", 0),
                            has_photo=member_data.get("has_photo", True),
                            has_username=member_data.get("has_username", True),
                            has_bio=member_data.get("has_bio", False),
                            first_name=member_data.get("first_name", ""),
                        )
                        profile.compute_fingerprint()
                        cluster.add_member(profile)
                except Exception as e:
                    log.debug(f"Failed to load member data for {uid_str}: {e}")
            
            if cluster.is_coordinated():
                return cluster
            
        except Exception as e:
            log.debug(f"Join cluster check failed: {e}")
        
        return None
    
    async def store_member_fingerprint(self, chat_id: int, profile: MemberProfile):
        """Store member fingerprint in Redis for cluster analysis."""
        if not self.redis:
            return
        
        import json
        
        key = f"nexus:raid:member:{chat_id}"
        data = json.dumps({
            "joined_at": profile.joined_at,
            "account_age_days": profile.account_age_days,
            "has_photo": profile.has_photo,
            "has_username": profile.has_username,
            "has_bio": profile.has_bio,
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "username": profile.username,
        })
        
        await self.redis.hset(key, str(profile.user_id), data)
        # Set TTL of 2 minutes
        await self.redis.expire(key, 120)
    
    async def check_message_similarity(
        self, chat_id: int, user_id: int, message_text: str
    ) -> Optional[List[int]]:
        """
        Check if a message is similar to recent messages in the chat.
        Returns list of user IDs with similar messages if detected.
        """
        if not self.redis:
            return None
        
        now = time.time()
        key = f"nexus:messages:{chat_id}"
        
        # Store this message
        fp = MessageFingerprint(
            user_id=user_id,
            chat_id=chat_id,
            message_text=message_text,
            timestamp=now,
        )
        
        try:
            # Load recent messages
            recent_msgs = await self.redis.zrangebyscore(key, now - 300, now)
            
            similar_users = []
            
            for msg_data in recent_msgs:
                try:
                    other_fp = MessageFingerprint(
                        user_id=0,
                        chat_id=chat_id,
                        message_text="",
                        timestamp=0,
                    )
                    # Reconstruct from stored data
                    # Format: "user_id:message_hash:text"
                    parts = msg_data.split(b":", 2)
                    if len(parts) >= 2:
                        other_user_id = int(parts[0])
                        if other_user_id == user_id:
                            continue
                        
                        other_text = parts[2].decode() if len(parts) > 2 else ""
                        other_fp.message_text = other_text
                        
                        similarity = fp.similarity_to(other_fp)
                        
                        if similarity >= 0.8:  # 80% similar
                            similar_users.append(other_user_id)
                except Exception:
                    continue
            
            if similar_users:
                return similar_users
            
        except Exception as e:
            log.debug(f"Message similarity check failed: {e}")
        
        # Store this message
        try:
            store_key = f"{user_id}:{fp.content_hash}:{message_text[:100]}"
            await self.redis.zadd(key, {store_key: now})
            await self.redis.zremrangebyscore(key, 0, now - 300)  # 5 min TTL
        except Exception:
            pass
        
        return None
    
    async def on_member_join(self, chat_id: int, member: MemberProfile) -> str:
        # 0. Store member fingerprint for cluster detection
        await self.store_member_fingerprint(chat_id, member)
        
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
        
        # 2. Check for coordinated join cluster
        cluster = await self.check_join_cluster(chat_id)
        if cluster and cluster.is_coordinated():
            log.warning(
                f"[ANTIRAID] Coordinated cluster detected in {chat_id}: "
                f"{len(cluster.user_ids)} users joined within {cluster.duration_seconds():.1f}s"
            )
            # Escalate threat level
            joins_per_minute = max(joins_per_minute, len(cluster.user_ids))
        
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
        
        # 6. Additional checks for high-suspicion members
        if score >= 60 and threat_level in ["yellow", "orange", "red", "critical"]:
            # Force CAPTCHA
            return "captcha_required"
        
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
                "ban_suspicious_on_raid": True,
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