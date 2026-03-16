import logging
from datetime import datetime, timezone, timedelta
from db.client import db

logger = logging.getLogger(__name__)

# Global cache for warnings time column detection
_WARNINGS_TIME_COL = None


async def _get_warnings_time_col(conn) -> str:
    """
    Auto-detect whether warnings table uses 'issued_at' or 'created_at'.
    The warnings table has TWO possible schemas depending on which migration ran first:
    - add_games_expansion.sql → created_at column (no issued_at)
    - add_moderation_v3.sql   → issued_at column (no created_at)
    Result is cached globally after first detection.
    """
    global _WARNINGS_TIME_COL

    if _WARNINGS_TIME_COL is not None:
        return _WARNINGS_TIME_COL

    try:
        # Check information_schema for column existence
        row = await conn.fetchrow(
            """SELECT column_name FROM information_schema.columns
               WHERE table_name = 'warnings' AND column_name = 'issued_at'"""
        )
        if row:
            _WARNINGS_TIME_COL = "issued_at"
            logger.info(f"[ANALYTICS] warnings time col: issued_at (moderation_v3 schema)")
        else:
            _WARNINGS_TIME_COL = "created_at"
            logger.info(f"[ANALYTICS] warnings time col: created_at (games_expansion schema)")
    except Exception as e:
        # Fallback to created_at if query fails
        logger.warning(f"[ANALYTICS] Could not detect warnings time column: {e}, defaulting to created_at")
        _WARNINGS_TIME_COL = "created_at"

    return _WARNINGS_TIME_COL


async def aggregate_hourly(pool) -> None:
    """
    Runs every hour. Counts activity in the past hour.
    Per-chat error isolation - one bad chat never stops all others.
    """
    global _WARNINGS_TIME_COL

    now = datetime.now(timezone.utc)
    target_hour = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    logger.info(f"[ANALYTICS] Running hourly aggregation for {target_hour}")

    async with pool.acquire() as conn:
        # Detect warnings time column on first run
        warnings_time_col = await _get_warnings_time_col(conn)

        # Get all active chats
        try:
            chats = await conn.fetch("SELECT chat_id FROM groups")
        except Exception as e:
            logger.error(f"[ANALYTICS] Failed to fetch groups: {e}")
            return

        success_count = 0
        error_count = 0

        for chat in chats:
            chat_id = chat['chat_id']

            try:
                # Spam detected (from spam_signals)
                spam_detected = 0
                try:
                    spam_detected = await conn.fetchval(
                        """SELECT COUNT(*) FROM spam_signals
                           WHERE chat_id = $1 AND label = 'spam'
                           AND created_at >= $2 AND created_at < $3""",
                        chat_id, target_hour, target_hour + timedelta(hours=1)
                    ) or 0
                except Exception as e:
                    logger.debug(f"[ANALYTICS] spam_signals query failed for {chat_id}: {e}")

                # Bans issued - try bans table first, fall back to mod_logs
                bans_issued = 0
                try:
                    bans_issued = await conn.fetchval(
                        """SELECT COUNT(*) FROM bans
                           WHERE chat_id = $1 AND banned_at >= $2 AND banned_at < $3""",
                        chat_id, target_hour, target_hour + timedelta(hours=1)
                    ) or 0
                except Exception as e:
                    logger.debug(f"[ANALYTICS] bans query failed for {chat_id}: {e}")
                    # Fallback: count from mod_logs
                    try:
                        bans_issued = await conn.fetchval(
                            """SELECT COUNT(*) FROM mod_logs
                               WHERE chat_id = $1 AND action = 'ban'
                               AND done_at >= $2 AND done_at < $3""",
                            chat_id, target_hour, target_hour + timedelta(hours=1)
                        ) or 0
                    except Exception:
                        pass

                # Warnings issued - use detected column
                warns_issued = 0
                try:
                    warns_issued = await conn.fetchval(
                        f"""SELECT COUNT(*) FROM warnings
                            WHERE chat_id = $1 AND {warnings_time_col} >= $2 AND {warnings_time_col} < $3""",
                        chat_id, target_hour, target_hour + timedelta(hours=1)
                    ) or 0
                except Exception as e:
                    logger.debug(f"[ANALYTICS] warnings query failed for {chat_id}: {e}")

                # Members joined - use member_events if available, fall back to users
                members_joined = 0
                try:
                    # Try member_events first (from add_antiraid_captcha.sql)
                    members_joined = await conn.fetchval(
                        """SELECT COUNT(*) FROM member_events
                           WHERE chat_id = $1 AND event_type = 'join'
                           AND created_at >= $2 AND created_at < $3""",
                        chat_id, target_hour, target_hour + timedelta(hours=1)
                    ) or 0
                except Exception:
                    # Fallback to users table
                    try:
                        members_joined = await conn.fetchval(
                            """SELECT COUNT(*) FROM users
                               WHERE chat_id = $1 AND joined_at >= $2 AND joined_at < $3""",
                            chat_id, target_hour, target_hour + timedelta(hours=1)
                        ) or 0
                    except Exception as e2:
                        logger.debug(f"[ANALYTICS] members query failed for {chat_id}: {e2}")

                # Members left
                members_left = 0
                try:
                    members_left = await conn.fetchval(
                        """SELECT COUNT(*) FROM member_events
                           WHERE chat_id = $1 AND event_type = 'leave'
                           AND created_at >= $2 AND created_at < $3""",
                        chat_id, target_hour, target_hour + timedelta(hours=1)
                    ) or 0
                except Exception:
                    pass

                # Message count estimation (if available)
                message_count = 0
                try:
                    # This is a placeholder - actual implementation would depend on message tracking
                    message_count = await conn.fetchval(
                        """SELECT COUNT(*) FROM mod_logs
                           WHERE chat_id = $1 AND done_at >= $2 AND done_at < $3""",
                        chat_id, target_hour, target_hour + timedelta(hours=1)
                    ) or 0
                except Exception:
                    pass

                # Upsert into bot_stats_hourly
                try:
                    await conn.execute(
                        """INSERT INTO bot_stats_hourly
                           (chat_id, hour, message_count, spam_detected, bans_issued, warns_issued, members_joined, members_left)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                           ON CONFLICT (chat_id, hour) DO UPDATE
                           SET message_count = EXCLUDED.message_count,
                               spam_detected = EXCLUDED.spam_detected,
                               bans_issued = EXCLUDED.bans_issued,
                               warns_issued = EXCLUDED.warns_issued,
                               members_joined = EXCLUDED.members_joined,
                               members_left = EXCLUDED.members_left""",
                        chat_id, target_hour, message_count, spam_detected, bans_issued, warns_issued, members_joined, members_left
                    )
                    success_count += 1
                except Exception as e:
                    logger.warning(f"[ANALYTICS] Failed to upsert hourly stats for {chat_id}: {e}")
                    error_count += 1

            except Exception as e:
                # Per-chat error isolation - log but continue
                logger.warning(f"[ANALYTICS] Error processing chat {chat_id}: {e}")
                error_count += 1

        logger.info(f"[ANALYTICS] Hourly aggregation complete: {success_count} success, {error_count} errors")


async def aggregate_daily(pool) -> None:
    """
    Runs at midnight UTC. Rolls up bot_stats_hourly → bot_stats_daily.
    Dual-schema support for bot_stats_daily (date,bot_id vs chat_id,day).
    """
    now = datetime.now(timezone.utc)
    target_day = (now - timedelta(days=1)).date()

    logger.info(f"[ANALYTICS] Running daily aggregation for {target_day}")

    async with pool.acquire() as conn:
        # Get all chats
        try:
            chats = await conn.fetch("SELECT chat_id FROM groups")
        except Exception as e:
            logger.error(f"[ANALYTICS] Failed to fetch groups: {e}")
            return

        success_count = 0

        for chat in chats:
            chat_id = chat['chat_id']

            try:
                # Roll up hourly stats
                stats = await conn.fetchrow(
                    """SELECT
                        SUM(message_count) as msg_sum,
                        SUM(spam_detected) as spam_sum,
                        SUM(members_joined) as join_sum,
                        SUM(members_left) as left_sum,
                        SUM(bans_issued) as ban_sum,
                        SUM(warns_issued) as warn_sum
                       FROM bot_stats_hourly
                       WHERE chat_id = $1 AND hour::date = $2""",
                    chat_id, target_day
                )

                if not stats or (not stats['msg_sum'] and not stats['spam_sum'] and not stats['join_sum']):
                    continue

                # Most active hour
                most_active_hour_row = await conn.fetchrow(
                    """SELECT EXTRACT(HOUR FROM hour) as hr
                       FROM bot_stats_hourly
                       WHERE chat_id = $1 AND hour::date = $2
                       ORDER BY message_count DESC LIMIT 1""",
                    chat_id, target_day
                )
                most_active_hour = int(most_active_hour_row['hr']) if most_active_hour_row else None

                # Top spammers
                top_spammer_ids = []
                try:
                    top_spammers = await conn.fetch(
                        """SELECT user_id, COUNT(*) as cnt
                           FROM spam_signals
                           WHERE chat_id = $1 AND label = 'spam' AND created_at::date = $2
                           GROUP BY user_id
                           ORDER BY cnt DESC LIMIT 5""",
                        chat_id, target_day
                    )
                    top_spammer_ids = [r['user_id'] for r in top_spammers]
                except Exception:
                    pass

                # Churn rate calculation
                total_members = await conn.fetchval(
                    "SELECT member_count FROM groups WHERE chat_id = $1", chat_id
                ) or 1
                members_left = stats['left_sum'] or 0
                members_joined = stats['join_sum'] or 0
                churn_rate = members_left / (members_joined + total_members) if (members_joined + total_members) > 0 else 0

                # Try new schema first (chat_id, day)
                try:
                    await conn.execute(
                        """INSERT INTO bot_stats_daily (
                            chat_id, day, message_count, spam_detected, members_joined,
                            members_left, bans_issued, warns_issued, top_spammer_user_ids,
                            most_active_hour, churn_rate
                           )
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                           ON CONFLICT (chat_id, day) DO UPDATE
                           SET message_count = EXCLUDED.message_count,
                               spam_detected = EXCLUDED.spam_detected,
                               members_joined = EXCLUDED.members_joined,
                               members_left = EXCLUDED.members_left,
                               bans_issued = EXCLUDED.bans_issued,
                               warns_issued = EXCLUDED.warns_issued,
                               top_spammer_user_ids = EXCLUDED.top_spammer_user_ids,
                               most_active_hour = EXCLUDED.most_active_hour,
                               churn_rate = EXCLUDED.churn_rate""",
                        chat_id, target_day, stats['msg_sum'] or 0, stats['spam_sum'] or 0,
                        stats['join_sum'] or 0, stats['left_sum'] or 0, stats['ban_sum'] or 0,
                        stats['warn_sum'] or 0, top_spammer_ids, most_active_hour, churn_rate
                    )
                except Exception as e:
                    # Silently fall back to old schema (date, bot_id)
                    logger.debug(f"[ANALYTICS] New schema failed for {chat_id}, trying legacy: {e}")
                    try:
                        # Get bot_id for this chat
                        bot_id = await conn.fetchval(
                            "SELECT bot_id FROM groups WHERE chat_id = $1", chat_id
                        ) or 0

                        await conn.execute(
                            """INSERT INTO bot_stats_daily (
                                date, bot_id, commands_count, music_plays, games_played,
                                new_groups, active_users
                               )
                               VALUES ($1, $2, $3, 0, 0, 0, 0)
                               ON CONFLICT (date, bot_id) DO UPDATE
                               SET commands_count = EXCLUDED.commands_count + bot_stats_daily.commands_count""",
                            target_day, bot_id, stats['msg_sum'] or 0
                        )
                    except Exception as e2:
                        logger.warning(f"[ANALYTICS] Both schemas failed for {chat_id}: {e2}")
                        continue

                success_count += 1

            except Exception as e:
                logger.warning(f"[ANALYTICS] Error processing daily stats for {chat_id}: {e}")

        logger.info(f"[ANALYTICS] Daily aggregation complete: {success_count} chats processed")
