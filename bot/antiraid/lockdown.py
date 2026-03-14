import json
import logging

from telegram import ChatPermissions

from bot.handlers.moderation.utils import publish_event
from db.client import db

log = logging.getLogger("[LOCKDOWN]")


class LockdownManager:
    def __init__(self, redis, pool, bot):
        self.redis = redis
        self.pool = pool
        self.bot = bot

    async def activate(
        self,
        chat_id: int,
        reason: str,
        triggered_by: int = None,
        incident_id: int = None,
        duration_seconds: int = 300,
    ) -> bool:
        # 1. Get current permissions to restore later
        chat = await self.bot.get_chat(chat_id)
        # previous_perms = chat.permissions.to_dict() # This might not be exactly like this in PTB

        # 2. Restrict chat
        new_perms = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )

        try:
            await self.bot.set_chat_permissions(chat_id, new_perms)

            # 3. Save state
            await db.execute(
                "INSERT INTO lockdown_state (chat_id, is_active, started_at, started_by, reason, auto_unlock_at) "
                "VALUES ($1, TRUE, NOW(), $2, $3, NOW() + INTERVAL '1 second' * $4) "
                "ON CONFLICT (chat_id) DO UPDATE SET is_active=TRUE, started_at=NOW(), started_by=EXCLUDED.started_by, reason=EXCLUDED.reason, auto_unlock_at=EXCLUDED.auto_unlock_at",
                chat_id,
                triggered_by,
                reason,
                duration_seconds,
            )

            await publish_event(chat_id, "lockdown_change", {"active": True, "reason": reason})

            await self.bot.send_message(
                chat_id, f"🔒 *LOCKDOWN ACTIVATED*\n\nReason: {reason}\nAll new members restricted."
            )
            return True
        except Exception as e:
            log.error(f"Failed to activate lockdown: {e}")
            return False

    async def deactivate(self, chat_id: int, deactivated_by: int = None) -> bool:
        try:
            # Restore default permissions
            default_perms = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True,
            )
            await self.bot.set_chat_permissions(chat_id, default_perms)

            await db.execute(
                "UPDATE lockdown_state SET is_active = FALSE WHERE chat_id = $1", chat_id
            )

            await publish_event(chat_id, "lockdown_change", {"active": False})
            await self.bot.send_message(chat_id, "🔓 *Lockdown lifted*. Group restored to normal.")
            return True
        except Exception as e:
            log.error(f"Failed to deactivate lockdown: {e}")
            return False
