"""
bot/antiraid/engine.py

Anti-raid detection and enforcement.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from telegram import Bot, Chat, User
from telegram.error import TelegramError

from db.ops.antiraid import (
    record_join, count_recent_joins,
    create_antiraid_session, get_active_session,
    end_antiraid_session, get_session_join_count,
    increment_session_joins, log_member_event
)
from api.routes.events import push_event

log = logging.getLogger("antiraid")

# Per-chat locks to prevent concurrent trigger races
_locks: dict[int, asyncio.Lock] = {}


def _get_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _locks:
        _locks[chat_id] = asyncio.Lock()
    return _locks[chat_id]


async def handle_new_member(
    bot: Bot,
    chat_id: int,
    user: User,
    settings: dict,
    db,
    owner_id: int | None
):
    """
    Called for every new member join event.
    Returns True if user was restricted/banned (caller should stop processing).
    """
    # Always record the join
    await record_join(db, chat_id, user.id)
    await log_member_event(db, chat_id, user, "join")

    # Check if raid already active
    session = await get_active_session(db, chat_id)
    if session:
        await _handle_raid_join(bot, chat_id, user, session, settings, db)
        await _push_join_sse(owner_id, chat_id, user, is_raid=True)
        return True

    # Auto anti-raid detection
    if not settings.get("auto_antiraid_enabled"):
        await _push_join_sse(owner_id, chat_id, user, is_raid=False)
        return False

    threshold = settings.get("auto_antiraid_threshold", 15)
    join_count = await count_recent_joins(db, chat_id, window_seconds=60)

    if join_count < threshold:
        await _push_join_sse(owner_id, chat_id, user, is_raid=False)
        return False

    # Threshold hit — trigger raid
    async with _get_lock(chat_id):
        # Re-check inside lock (another coroutine may have triggered already)
        session = await get_active_session(db, chat_id)
        if session:
            await _handle_raid_join(bot, chat_id, user, session, settings, db)
            return True

        await _trigger_raid(bot, chat_id, settings, db, owner_id, join_count)
        session = await get_active_session(db, chat_id)
        if session:
            await _handle_raid_join(bot, chat_id, user, session, settings, db)

    await _push_join_sse(owner_id, chat_id, user, is_raid=True)
    return True


async def _trigger_raid(
    bot, chat_id, settings, db, owner_id, join_count
):
    """Create session, alert group, schedule auto-end."""
    duration = settings.get("antiraid_duration_mins", 15)
    ends_at  = (
        datetime.now(timezone.utc) + timedelta(minutes=duration)
        if duration > 0 else None
    )

    session_id = await create_antiraid_session(
        db, chat_id, triggered_by="auto",
        ends_at=ends_at, join_count=join_count
    )

    log.warning(
        f"[ANTIRAID] RAID TRIGGERED | chat={chat_id} "
        f"joins/min={join_count} mode={settings.get('antiraid_mode')}"
    )

    # Alert message
    try:
        alert = await bot.send_message(
            chat_id=chat_id,
            text=(
                "🚨 <b>Anti-Raid Activated</b>\n\n"
                f"Unusual join activity detected ({join_count} joins/min).\n"
                "New members will be " +
                {
                    "restrict": "muted",
                    "ban":      "banned",
                    "captcha":  "required to solve CAPTCHA",
                }.get(settings.get("antiraid_mode", "restrict"), "restricted") +
                " until the raid ends.\n\n" +
                (f"Auto-ends in {duration} minutes." if duration else
                 "Use /antiraid off to end manually.")
            ),
            parse_mode="HTML"
        )
    except TelegramError as e:
        log.warning(f"[ANTIRAID] Alert failed: {e}")

    # Push SSE to Mini App
    if owner_id:
        try:
            push_event(owner_id, {
                "type":    "raid",
                "title":   "🚨 Raid Detected",
                "body":    f"{join_count} joins/min in {chat_id}",
                "chat_id": chat_id,
            })
        except Exception:
            pass

    # Schedule auto-end
    if duration > 0:
        asyncio.create_task(
            _auto_end_raid(bot, chat_id, session_id, duration * 60, db)
        )


async def _handle_raid_join(bot, chat_id, user, session, settings, db):
    """Apply raid penalty to newly joining user."""
    mode = settings.get("antiraid_mode", "restrict")
    await increment_session_joins(db, session["id"])

    try:
        if mode == "ban":
            await bot.ban_chat_member(chat_id, user.id)
            log.info(f"[ANTIRAID] Banned raid joiner | user={user.id}")

        elif mode == "restrict":
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions={"can_send_messages": False}
            )
            log.info(f"[ANTIRAID] Restricted raid joiner | user={user.id}")

        elif mode == "captcha":
            # Force CAPTCHA on this user
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions={"can_send_messages": False}
            )
            # CAPTCHA handler will send challenge (handled in new_member.py)

    except TelegramError as e:
        log.warning(f"[ANTIRAID] Penalty failed | user={user.id} err={e}")


async def _auto_end_raid(bot, chat_id, session_id, delay_seconds, db):
    await asyncio.sleep(delay_seconds)
    # Check if session is still active before ending
    session = await db.fetchrow("SELECT is_active FROM antiraid_sessions WHERE id = $1", session_id)
    if session and session['is_active']:
        await end_antiraid_session(db, session_id)
        log.info(f"[ANTIRAID] Auto-ended | chat={chat_id}")
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="✅ Anti-raid protection deactivated. Group is open again."
            )
        except TelegramError:
            pass


async def manual_toggle_raid(
    bot, chat_id, enable: bool, settings, db, triggered_by: int
):
    """Called by /antiraid on|off command."""
    if enable:
        session = await get_active_session(db, chat_id)
        if session:
            return "⚠️ Anti-raid is already active"
        await _trigger_raid(bot, chat_id, settings, db, None, 0)
        return "🚨 Anti-raid activated manually"
    else:
        session = await get_active_session(db, chat_id)
        if not session:
            return "ℹ️ Anti-raid is not active"
        await end_antiraid_session(db, session["id"])
        return "✅ Anti-raid deactivated"


async def _push_join_sse(owner_id, chat_id, user, is_raid: bool):
    if not owner_id:
        return
    try:
        push_event(owner_id, {
            "type":    "raid_join" if is_raid else "join",
            "title":   f"{'🚨 Raid' if is_raid else '👋'} {user.full_name}",
            "body":    f"@{user.username or user.id} joined {chat_id}",
            "chat_id": chat_id,
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "is_raid": is_raid,
        })
    except Exception:
        pass
