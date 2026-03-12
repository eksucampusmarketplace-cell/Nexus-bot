"""
bot/automod/penalties.py

Apply penalties to users.
PenaltyType: delete | silence | kick | ban
"""

import logging
from enum import Enum
from datetime import datetime, timedelta, timezone

from telegram import Bot
from telegram.error import TelegramError

log = logging.getLogger("penalties")


class PenaltyType(str, Enum):
    delete  = "delete"
    silence = "silence"
    kick    = "kick"
    ban     = "ban"


async def apply_penalty(
    bot: Bot,
    chat_id: int,
    user_id: int,
    penalty: PenaltyType,
    duration_hours: int = 0
):
    """
    Apply penalty to user in chat.

    delete:  nothing extra (message already deleted by engine)
    silence: restrict user (can't send messages)
             duration_hours=0 → permanent
             duration_hours=1000 → permanent
    kick:    ban then unban immediately (can rejoin)
    ban:     ban permanently or for duration
    """
    try:
        if penalty == PenaltyType.silence:
            until = (
                datetime.now(timezone.utc) + timedelta(hours=duration_hours)
                if 0 < duration_hours < 1000
                else None
            )
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions={"can_send_messages": False},
                until_date=until
            )

        elif penalty == PenaltyType.kick:
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id)

        elif penalty == PenaltyType.ban:
            until = (
                datetime.now(timezone.utc) + timedelta(hours=duration_hours)
                if 0 < duration_hours < 1000
                else None
            )
            await bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                until_date=until
            )

        log.info(
            f"[PENALTIES] Applied | chat={chat_id} user={user_id} "
            f"penalty={penalty} duration={duration_hours}h"
        )

    except TelegramError as e:
        log.warning(f"[PENALTIES] Failed | {e}")
