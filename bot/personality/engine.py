"""
bot/personality/engine.py

Personality Engine - Tone templates for moderation actions.
5 tone options: warm, professional, strict, playful, neutral
"""

import logging
from typing import Optional, Dict, Any

from bot.utils.localization import get_locale, SUPPORTED_LANGUAGES, DEFAULT_LANG

logger = logging.getLogger(__name__)

# Tone definitions
TONES = {
    "warm": {
        "description": "Friendly and approachable",
        "emoji": True,
        "templates": {
            "warn": [
                "Hey {user}, just a friendly reminder to follow our group rules. {reason} Thanks for understanding! 💙",
                "Hi {user}, we noticed {reason}. Let's keep things friendly here. This is warning {count}/{limit}. 🤝",
            ],
            "ban": [
                "We had to say goodbye to {user}. {reason} We wish you the best. 👋",
                "Sorry {user}, but {reason} means we can't have you in the group anymore. Take care. 🍂",
            ],
            "kick": [
                "{user} has been removed. {reason} They can rejoin if they follow the rules. 🚪",
                "We've asked {user} to step out. {reason} Everyone deserves a second chance! 🌱",
            ],
            "mute": [
                "{user}, let's take a short break. {reason} You'll be able to chat again in {duration}. ☕",
                "Time out for {user}! {reason} Muted for {duration}. See you soon! ⏰",
            ],
        }
    },
    "professional": {
        "description": "Formal and courteous",
        "emoji": False,
        "templates": {
            "warn": [
                "User {user} has been issued a formal warning. Reason: {reason}. Warning count: {count}/{limit}.",
                "Notice: {user} has received a warning for {reason}. This is warning {count} of {limit}.",
            ],
            "ban": [
                "User {user} has been permanently removed from the group. Reason: {reason}.",
                "Action taken: {user} banned. Reason: {reason}. This action is final.",
            ],
            "kick": [
                "User {user} has been removed from the group. Reason: {reason}.",
                "Action: {user} kicked. Reason: {reason}. User may rejoin with proper conduct.",
            ],
            "mute": [
                "User {user} has been temporarily restricted. Duration: {duration}. Reason: {reason}.",
                "Restriction applied to {user}. Mute duration: {duration}. Reason: {reason}.",
            ],
        }
    },
    "strict": {
        "description": "Firm and authoritative",
        "emoji": True,
        "templates": {
            "warn": [
                "⚠️ WARNING: {user} violated rules. {reason} Strike {count}/{limit}. Next violation results in removal.",
                "🚨 {user} — {reason} This is your {count} of {limit} warnings. Comply or face consequences.",
            ],
            "ban": [
                "🚫 BANNED: {user} is no longer welcome here. {reason} Zero tolerance policy enforced.",
                "❌ {user} PERMANENTLY REMOVED. {reason} Don't let the door hit you on the way out.",
            ],
            "kick": [
                "👢 {user} KICKED. {reason} Return only if you can follow rules.",
                "🚪 {user} REMOVED. {reason} One chance to rejoin — use it wisely.",
            ],
            "mute": [
                "🔇 {user} SILENCED. {reason} Duration: {duration}. Consider this a lesson.",
                "⛔ {user} MUTED. {reason} {duration} to reflect on your behavior.",
            ],
        }
    },
    "playful": {
        "description": "Fun and lighthearted",
        "emoji": True,
        "templates": {
            "warn": [
                "Oopsie! {user} got a little warning 🎈 {reason} That's strike {count}/{limit} — play nice!",
                "Heads up {user}! {reason} Consider this a gentle nudge {count}/{limit} 😊",
            ],
            "ban": [
                "Bye bye {user}! 👋 {reason} It's been real! Don't forget to write! ✉️",
                "{user} has left the building! 🎭 {reason} Thanks for the memories!",
            ],
            "kick": [
                "{user} got the boot! 👢 {reason} They can come back if they behave! 🎪",
                "See ya later {user}! 🎈 {reason} The door's open for round two!",
            ],
            "mute": [
                "Shhh! {user} is taking a nap 😴 {reason} Back in {duration}!",
                "{user} is in timeout corner! ⏱️ {reason} {duration} to think about it!",
            ],
        }
    },
    "neutral": {
        "description": "Balanced and straightforward",
        "emoji": True,
        "templates": {
            "warn": [
                "⚠️ {user} warned. Reason: {reason} ({count}/{limit})",
                "Warning issued to {user}. {reason} Count: {count}/{limit}",
            ],
            "ban": [
                "🚫 {user} banned. Reason: {reason}",
                "Banned: {user} — {reason}",
            ],
            "kick": [
                "👢 {user} kicked. Reason: {reason}",
                "Kicked: {user} — {reason}",
            ],
            "mute": [
                "🔇 {user} muted for {duration}. Reason: {reason}",
                "Muted: {user} ({duration}) — {reason}",
            ],
        }
    },
}


class PersonalityEngine:
    """
    Personality-aware message formatter for bot responses.
    
    Usage:
        personality = PersonalityEngine(tone="warm", language="en")
        msg = personality.format_action("warn", user="@john", reason="spam", count=1, limit=3)
    """
    
    def __init__(
        self,
        tone: str = "neutral",
        language: str = DEFAULT_LANG,
        emoji: Optional[bool] = None,
        bot_name: Optional[str] = None
    ):
        self.tone = tone if tone in TONES else "neutral"
        self.language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANG
        self.locale = get_locale(self.language)
        self.emoji = emoji if emoji is not None else TONES[self.tone]["emoji"]
        self.bot_name = bot_name or "Nexus"
    
    def format_action(self, action: str, lang: str = None, **kwargs) -> str:
        """Format a moderation action message with personality."""
        from bot.utils.localization import get_locale
        
        lang = lang or self.language
        locale = get_locale(lang)
        
        # If not English, use the same STRINGS keys as the default handler
        if lang != 'en':
            key_map = {
                'warn': 'warn_issued', 
                'ban': 'user_banned',
                'mute': 'user_muted',
                'kick': 'user_kicked'
            }
            key = key_map.get(action, action)
            return locale.get(key, **kwargs)

        # For English, use personality templates if available
        templates = TONES[self.tone]["templates"].get(action)
        if not templates:
            # Fallback to localization
            key_map = {
                'warn': 'warn_issued', 
                'ban': 'user_banned',
                'mute': 'user_muted',
                'kick': 'user_kicked'
            }
            key = key_map.get(action, action)
            return locale.get(key, **kwargs)
        
        # Use first template
        template = templates[0]
        
        # Add emoji preference
        if not self.emoji:
            # Strip emojis from template (simple approach)
            import re
            template = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+', '', template)
            template = template.strip()
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing format arg {e} for action {action}")
            return self.locale.get(f"{action}_user", **kwargs)
    
    def get_preview(self) -> Dict[str, str]:
        """Get preview messages for all actions."""
        preview_data = {
            "user": "@username",
            "reason": "example reason",
            "count": 1,
            "limit": 3,
            "duration": "1 hour"
        }
        return {
            "tone": self.tone,
            "description": TONES[self.tone]["description"],
            "warn": self.format_action("warn", **preview_data),
            "ban": self.format_action("ban", **preview_data),
            "kick": self.format_action("kick", **preview_data),
            "mute": self.format_action("mute", **preview_data),
        }
    
    @classmethod
    def get_available_tones(cls) -> Dict[str, str]:
        """Get list of available tones with descriptions."""
        return {tone: data["description"] for tone, data in TONES.items()}


async def get_personality(pool, bot_id: Optional[int] = None, chat_id: Optional[int] = None) -> PersonalityEngine:
    """
    Get personality configuration from database.
    Priority: chat settings > bot settings > defaults
    """
    tone = "neutral"
    language = DEFAULT_LANG
    emoji = True
    bot_name = "Nexus"
    
    try:
        if pool and chat_id:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT persona_tone, persona_language, persona_emoji 
                       FROM groups WHERE chat_id = $1""",
                    chat_id
                )
                if row:
                    tone = row.get("persona_tone") or tone
                    language = row.get("persona_language") or language
                    emoji = row.get("persona_emoji") if row.get("persona_emoji") is not None else emoji
        
        if pool and bot_id:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT persona_tone, persona_language, persona_emoji, persona_name
                       FROM bots WHERE bot_id = $1""",
                    bot_id
                )
                if row:
                    tone = row.get("persona_tone") or tone
                    language = row.get("persona_language") or language
                    emoji = row.get("persona_emoji") if row.get("persona_emoji") is not None else emoji
                    bot_name = row.get("persona_name") or bot_name
    except Exception as e:
        logger.debug(f"Failed to load personality from DB: {e}")
    
    return PersonalityEngine(tone=tone, language=language, emoji=emoji, bot_name=bot_name)


# Export
__all__ = ["PersonalityEngine", "get_personality", "TONES"]
