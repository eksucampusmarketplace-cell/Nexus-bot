"""
bot/scheduler/engine.py

Persistent scheduler for Nexus.
Runs as background asyncio task inside the bot process.

Architecture:
  - Single async loop runs every 60 seconds
  - Queries scheduled_messages WHERE next_send_at <= NOW() AND is_active=TRUE
  - Sends each due message via bot
  - Updates last_sent_at, send_count, next_send_at
  - Deactivates if max_sends reached

Schedule types:
  once      → send at scheduled_at, then deactivate
  interval  → send every interval_mins minutes
  daily     → send at time_of_day every day (group timezone)
  weekly    → send at time_of_day on specific days_of_week
  cron      → full cron expression (using croniter)

Silent time scheduler:
  Separate loop checks silent_times slots every minute.
  When entering a silent time window:
    - Send slot.start_text if set
    - Enable mute (restrict all members from sending)
  When leaving a silent time window:
    - Send slot.end_text if set
    - Remove mute

Logs prefix: [SCHEDULER]
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import asyncpg
import pytz
from croniter import croniter

from bot.logging.log_channel import log_event
from db.ops.automod import get_group_settings
from db.ops.scheduler import (
    deactivate_message,
    get_active_silent_times,
    get_due_messages,
    mark_sent,
)

log = logging.getLogger("scheduler")


class NexusScheduler:
    """
    Background scheduler.
    Instantiated once at bot startup.
    Call start() to begin the async loops.
    """

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self._tasks = []
        self._silent_active: dict[int, dict[int, bool]] = {}

    async def start(self):
        """Start all scheduler loops."""
        self._tasks = [
            asyncio.create_task(self._message_loop()),
            asyncio.create_task(self._silent_time_loop()),
            asyncio.create_task(
                self._name_history_purge_loop()
            ),  # F-06: Auto-purge old name history
            asyncio.create_task(self._name_sync_loop()),  # Bug fix: Sync name history periodically
        ]
        log.info("[SCHEDULER] Started")

    async def stop(self):
        for t in self._tasks:
            t.cancel()
        log.info("[SCHEDULER] Stopped")

    async def _message_loop(self):
        """Polls DB every 60s for due messages."""
        while True:
            try:
                await self._process_due_messages()
            except asyncpg.UndefinedTableError as e:
                log.warning(
                    f"[SCHEDULER] scheduled_messages table missing — " f"run migrations: {e}"
                )
                await asyncio.sleep(300)
                continue
            except Exception as e:
                log.error(f"[SCHEDULER] Message loop error: {e}")
            await asyncio.sleep(60)

    async def _process_due_messages(self):
        due = await get_due_messages(self.db)
        for msg in due:
            try:
                await self._send_scheduled(msg)
            except Exception as e:
                log.warning(f"[SCHEDULER] Send failed | id={msg['id']} err={e}")

    async def _send_scheduled(self, msg: dict):
        chat_id = msg["chat_id"]
        content = msg.get("content") or ""
        sent_id = None

        try:
            media_type = msg.get("media_type")
            media_file_id = msg.get("media_file_id")

            if media_type and media_file_id:
                if media_type == "photo":
                    sent = await self.bot.send_photo(
                        chat_id=chat_id, photo=media_file_id, caption=content or None
                    )
                elif media_type == "video":
                    sent = await self.bot.send_video(
                        chat_id=chat_id, video=media_file_id, caption=content or None
                    )
                elif media_type == "document":
                    sent = await self.bot.send_document(
                        chat_id=chat_id, document=media_file_id, caption=content or None
                    )
                else:
                    sent = await self.bot.send_message(
                        chat_id=chat_id, text=content or "(scheduled)"
                    )
            else:
                sent = await self.bot.send_message(
                    chat_id=chat_id, text=content or "(scheduled)", parse_mode="HTML"
                )
            sent_id = sent.message_id
        except Exception as e:
            log.warning(f"[SCHEDULER] Message send error | chat={chat_id} err={e}")
            raise

        if msg.get("pin_after_send") and sent_id:
            try:
                await self.bot.pin_chat_message(
                    chat_id=chat_id, message_id=sent_id, disable_notification=True
                )
            except Exception:
                pass

        new_count = msg["send_count"] + 1
        max_sends = msg.get("max_sends", 0)

        if max_sends > 0 and new_count >= max_sends:
            await deactivate_message(self.db, msg["id"])
            log.info(f"[SCHEDULER] Deactivated (max sends reached) | id={msg['id']}")
            return

        next_send = _calc_next_send(msg)
        await mark_sent(self.db, msg["id"], new_count, next_send)
        await log_event(
            bot=self.bot,
            db=self.db,
            chat_id=chat_id,
            event_type="schedule_send",
            details={
                "schedule_type": msg.get("schedule_type"),
                "message_id": msg["id"],
            },
            bot_id=self.bot.id,
        )
        log.info(
            f"[SCHEDULER] Sent | id={msg['id']} chat={chat_id} "
            f"count={new_count} next={next_send}"
        )

    async def _silent_time_loop(self):
        """Checks silent time windows every 60s."""
        while True:
            try:
                await self._check_silent_times()
            except asyncpg.UndefinedTableError as e:
                log.warning(f"[SCHEDULER] Silent time table missing — " f"run migrations: {e}")
                await asyncio.sleep(300)
                continue
            except asyncpg.UndefinedColumnError as e:
                log.warning(f"[SCHEDULER] Column missing — run migrations: {e}")
                await asyncio.sleep(300)
                continue
            except Exception as e:
                log.error(f"[SCHEDULER] Silent time loop error: {e}")
            await asyncio.sleep(60)

    async def _check_silent_times(self):
        slots = await get_active_silent_times(self.db)

        for slot in slots:
            chat_id = slot["chat_id"]
            slot_num = slot["slot"]
            start_str = str(slot["start_time"])
            end_str = str(slot["end_time"])
            start_text = slot.get("start_text", "")
            end_text = slot.get("end_text", "")

            settings = await get_group_settings(self.db, chat_id)
            tz_name = settings.get("timezone", "UTC") if settings else "UTC"

            from bot.automod.detectors import is_in_time_window

            now_time = _now_in_tz(tz_name)
            in_window = is_in_time_window(now_time, start_str, end_str)

            prev = self._silent_active.get(chat_id, {}).get(slot_num, False)

            if in_window and not prev:
                self._silent_active.setdefault(chat_id, {})[slot_num] = True
                await self._enable_silent_mode(chat_id, start_text or "🔕 Silent mode activated.")
                log.info(f"[SCHEDULER] Silent start | chat={chat_id} slot={slot_num}")

            elif not in_window and prev:
                self._silent_active.setdefault(chat_id, {})[slot_num] = False
                await self._disable_silent_mode(chat_id, end_text or "🔔 Silent mode ended.")
                log.info(f"[SCHEDULER] Silent end | chat={chat_id} slot={slot_num}")

    async def _enable_silent_mode(self, chat_id: int, text: str):
        """Restrict all members from sending messages."""
        try:
            from telegram import ChatPermissions

            await self.bot.set_chat_permissions(
                chat_id=chat_id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                ),
            )
            if text:
                await self.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            log.warning(f"[SCHEDULER] Silent enable failed | chat={chat_id} err={e}")

    async def _disable_silent_mode(self, chat_id: int, text: str):
        """Restore all member permissions."""
        try:
            from telegram import ChatPermissions

            await self.bot.set_chat_permissions(
                chat_id=chat_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            if text:
                await self.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            log.warning(f"[SCHEDULER] Silent disable failed | chat={chat_id} err={e}")

    # F-06: Name History Purge Extension
    async def _name_history_purge_loop(self):
        """Runs nightly to purge old name history records based on retention settings."""
        # Wait a bit before first run to not interfere with startup
        await asyncio.sleep(300)  # 5 minutes

        while True:
            try:
                await self._purge_old_name_history()
            except asyncpg.UndefinedTableError as e:
                log.warning(f"[SCHEDULER] Name history table missing — run migrations: {e}")
                await asyncio.sleep(3600)
                continue
            except asyncpg.UndefinedColumnError as e:
                log.warning(f"[SCHEDULER] Column missing — run migrations: {e}")
                await asyncio.sleep(3600)
                continue
            except Exception as e:
                log.error(f"[SCHEDULER] Name history purge error: {e}")

            # Run once per day
            await asyncio.sleep(86400)

    async def _purge_old_name_history(self):
        """Delete name history records older than retention period for each group."""
        async with self.db.acquire() as conn:
            # Find all groups with name history enabled and retention > 0
            rows = await conn.fetch("""SELECT chat_id, name_history_retention_days
                   FROM groups
                   WHERE name_history_enabled = TRUE
                     AND COALESCE(name_history_retention_days, 0) > 0""")

        total_deleted = 0
        for row in rows:
            chat_id = row["chat_id"]
            retention_days = row["name_history_retention_days"]

            try:
                async with self.db.acquire() as conn:
                    result = await conn.execute(
                        """DELETE FROM user_name_history
                           WHERE source_chat_id = $1
                             AND changed_at < NOW() - INTERVAL '$2 days'""",
                        chat_id,
                        retention_days,
                    )
                    # Extract count from result (e.g., "DELETE 42")
                    deleted = int(result.split()[1]) if result and len(result.split()) > 1 else 0
                    total_deleted += deleted

                    if deleted > 0:
                        log.info(
                            f"[SCHEDULER] Purged {deleted} old name history for "
                            f"chat={chat_id} (retention={retention_days}d)"
                        )
            except Exception as e:
                log.warning(f"[SCHEDULER] Failed to purge name history for chat={chat_id}: {e}")

        if total_deleted > 0:
            log.info(f"[SCHEDULER] Total name history records purged: {total_deleted}")

    # Bug fix: Name history sync loop - detects name changes without requiring messages
    async def _name_sync_loop(self):
        """Runs every 30 minutes to sync name history by scanning group administrators."""
        # Wait before first run to not interfere with startup
        await asyncio.sleep(60)

        while True:
            try:
                await self._sync_name_history()
            except asyncpg.UndefinedTableError as e:
                log.warning(f"[SCHEDULER] Name history table missing — run migrations: {e}")
                await asyncio.sleep(1800)
                continue
            except asyncpg.UndefinedColumnError as e:
                log.warning(f"[SCHEDULER] Column missing — run migrations: {e}")
                await asyncio.sleep(1800)
                continue
            except Exception as e:
                log.error(f"[SCHEDULER] Name sync error: {e}")

            # Run every 30 minutes
            await asyncio.sleep(1800)

    async def _sync_name_history(self):
        """Sync name history by checking administrators in groups where it's enabled."""
        async with self.db.acquire() as conn:
            # Find all groups with name history enabled
            rows = await conn.fetch("""SELECT chat_id
                   FROM groups
                   WHERE name_history_enabled = TRUE""")

        for row in rows:
            chat_id = row["chat_id"]
            try:
                await self._sync_group_admin_names(chat_id)
            except Exception as e:
                error_msg = str(e).lower()
                # Silent handling for expected errors (bot kicked, etc.)
                if any(
                    x in error_msg
                    for x in ["bot was kicked", "bot is not a member", "chat not found"]
                ):
                    log.debug(f"[SCHEDULER] Skipping name sync for chat={chat_id}: {e}")
                else:
                    log.warning(f"[SCHEDULER] Failed to sync names for chat={chat_id}: {e}")

    async def _sync_group_admin_names(self, chat_id: int):
        """Check administrators in a group and record any name changes."""
        from telegram.error import Forbidden

        try:
            admins = await self.bot.get_chat_administrators(chat_id)
        except Forbidden as e:
            # Bot was kicked or doesn't have permission - log at debug and skip
            log.debug(f"[SCHEDULER] Cannot get admins for chat={chat_id}: {e}")
            return

        async with self.db.acquire() as conn:
            for admin in admins:
                user = admin.user

                # Skip bots
                if user.is_bot:
                    continue

                # Check if user has opted out
                optout = await conn.fetchval(
                    "SELECT 1 FROM user_history_optout WHERE user_id = $1", user.id
                )
                if optout:
                    continue

                # Get last snapshot
                last_snapshot = await conn.fetchrow(
                    """SELECT first_name, last_name, username
                       FROM user_snapshots
                       WHERE user_id = $1 AND source_chat_id = $2""",
                    user.id,
                    chat_id,
                )

                current_first = user.first_name or ""
                current_last = user.last_name or ""
                current_username = user.username or ""

                # Check for changes (normalize NULL from DB to empty string for comparison)
                if last_snapshot:
                    prev_first = last_snapshot["first_name"] or ""
                    prev_last = last_snapshot["last_name"] or ""
                    prev_username = last_snapshot["username"] or ""
                    changed = (
                        prev_first != current_first
                        or prev_last != current_last
                        or prev_username != current_username
                    )

                    if not changed:
                        continue

                    # Record the name change to history
                    await conn.execute(
                        """INSERT INTO user_name_history
                           (user_id, first_name, last_name, username, source_chat_id,
                            old_first_name, old_last_name, old_username)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                        user.id,
                        current_first,
                        current_last,
                        current_username,
                        chat_id,
                        prev_first,
                        prev_last,
                        prev_username,
                    )

                    log.debug(
                        f"[SCHEDULER] Name change detected for user {user.id} in chat {chat_id}: "
                        f"first='{prev_first}'->'{current_first}', "
                        f"last='{prev_last}'->'{current_last}', "
                        f"user='{prev_username}'->'{current_username}'"
                    )

                # Create/update snapshot using upsert
                await conn.execute(
                    """INSERT INTO user_snapshots
                       (user_id, first_name, last_name, username, source_chat_id)
                       VALUES ($1, $2, $3, $4, $5)
                       ON CONFLICT (user_id, source_chat_id) DO UPDATE
                         SET first_name = EXCLUDED.first_name,
                             last_name  = EXCLUDED.last_name,
                             username   = EXCLUDED.username,
                             captured_at = NOW()""",
                    user.id,
                    current_first,
                    current_last,
                    current_username,
                    chat_id,
                )


def _calc_next_send(msg: dict) -> datetime:
    """Calculate next send time based on schedule type."""
    now = datetime.now(timezone.utc)
    stype = msg["schedule_type"]
    tz_name = msg.get("timezone", "UTC")

    if stype == "once":
        return msg.get("scheduled_at") or now

    if stype == "interval":
        mins = msg.get("interval_mins") or 60
        return now + timedelta(minutes=mins)

    if stype in ("daily", "weekly"):
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.utc
        tod = msg.get("time_of_day")
        now_local = datetime.now(tz)

        if stype == "daily":
            next_local = now_local.replace(
                hour=tod.hour, minute=tod.minute, second=0, microsecond=0
            )
            if next_local <= now_local:
                next_local += timedelta(days=1)
            return next_local.astimezone(timezone.utc)

        if stype == "weekly":
            days = msg.get("days_of_week") or [0]
            current_dow = now_local.weekday()
            for offset in range(1, 8):
                candidate_dow = (current_dow + offset) % 7
                tg_dow = (candidate_dow + 1) % 7
                if tg_dow in days:
                    next_local = now_local + timedelta(days=offset)
                    next_local = next_local.replace(
                        hour=tod.hour, minute=tod.minute, second=0, microsecond=0
                    )
                    return next_local.astimezone(timezone.utc)

    if stype == "cron":
        try:
            cron = croniter(msg["cron_expr"], now)
            return cron.get_next(datetime).replace(tzinfo=timezone.utc)
        except Exception:
            pass

    return now + timedelta(hours=1)


def _now_in_tz(tz_name: str):
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        return now.time()
    except Exception:
        return datetime.now().time()
