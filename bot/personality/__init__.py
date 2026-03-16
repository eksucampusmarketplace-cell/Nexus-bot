"""
bot/personality/__init__.py

Bot Personality Engine for Nexus Bot v21.
Provides tone templates and message formatting per-clone.
"""

from .engine import PersonalityEngine, get_personality

__all__ = ["PersonalityEngine", "get_personality"]
