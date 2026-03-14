"""
bot/engagement/__init__.py

Member engagement system: XP/levels, reputation, badges, weekly newsletters,
and cross-group networks.

Exports:
- XPEngine: Core XP calculation and awarding
- reputation: Reputation system functions
- badges: Badge system functions
- newsletter: Weekly newsletter generation and sending
- network: Cross-group network management
"""

from .xp import XPEngine, calculate_level, xp_for_level, xp_to_next_level
from .reputation import give_rep, get_reputation, get_rep_leaderboard
from .badges import seed_default_badges, check_and_award_badges, get_member_badges
from .newsletter import generate_newsletter, send_newsletter, get_week_stats
from .network import (
    create_network,
    join_network,
    leave_network,
    broadcast_to_network,
    get_network_leaderboard,
)

__all__ = [
    "XPEngine",
    "calculate_level",
    "xp_for_level",
    "xp_to_next_level",
    "give_rep",
    "get_reputation",
    "get_rep_leaderboard",
    "seed_default_badges",
    "check_and_award_badges",
    "get_member_badges",
    "generate_newsletter",
    "send_newsletter",
    "get_week_stats",
    "create_network",
    "join_network",
    "leave_network",
    "broadcast_to_network",
    "get_network_leaderboard",
]
