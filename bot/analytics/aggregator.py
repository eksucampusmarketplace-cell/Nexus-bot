import logging
from datetime import datetime, timezone, timedelta
from db.client import db

logger = logging.getLogger(__name__)

async def aggregate_hourly(pool) -> None:
    """Runs every hour. Counts activity in the past hour."""
    now = datetime.now(timezone.utc)
    target_hour = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    
    logger.info(f"Running hourly aggregation for {target_hour}")
    
    async with pool.acquire() as conn:
        # Get all active chats in the last hour
        chats = await conn.fetch("SELECT chat_id FROM groups")
        
        for chat in chats:
            chat_id = chat['chat_id']
            
            # Message count (not tracked per message currently, but we can estimate or skip)
            # Actually, the users table has message_count but it's cumulative.
            # For now, let's gather what we can from existing logs.
            
            # Spam detected
            spam_detected = await conn.fetchval(
                "SELECT COUNT(*) FROM spam_signals WHERE chat_id = $1 AND label = 'spam' AND created_at >= $2 AND created_at < $3",
                chat_id, target_hour, target_hour + timedelta(hours=1)
            ) or 0
            
            # Bans issued
            # Assuming mod_logs or similar exists. Based on prompt: mod_logs, member_events, warnings, bans
            bans_issued = await conn.fetchval(
                "SELECT COUNT(*) FROM bans WHERE chat_id = $1 AND banned_at >= $2 AND banned_at < $3",
                chat_id, target_hour, target_hour + timedelta(hours=1)
            ) or 0
            
            # Warnings issued
            warns_issued = await conn.fetchval(
                "SELECT COUNT(*) FROM warnings WHERE chat_id = $1 AND issued_at >= $2 AND issued_at < $3",
                chat_id, target_hour, target_hour + timedelta(hours=1)
            ) or 0
            
            # Members joined/left
            # Assuming member_events or similar exists. Let's check users table join_date for joins.
            members_joined = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE chat_id = $1 AND join_date >= $2 AND join_date < $3",
                chat_id, target_hour, target_hour + timedelta(hours=1)
            ) or 0
            
            # Upsert into bot_stats_hourly
            await conn.execute(
                """INSERT INTO bot_stats_hourly (chat_id, hour, spam_detected, bans_issued, warns_issued, members_joined)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (chat_id, hour) DO UPDATE 
                   SET spam_detected = EXCLUDED.spam_detected,
                       bans_issued = EXCLUDED.bans_issued,
                       warns_issued = EXCLUDED.warns_issued,
                       members_joined = EXCLUDED.members_joined""",
                chat_id, target_hour, spam_detected, bans_issued, warns_issued, members_joined
            )

async def aggregate_daily(pool) -> None:
    """Runs at midnight UTC. Rolls up bot_stats_hourly → bot_stats_daily."""
    now = datetime.now(timezone.utc)
    target_day = (now - timedelta(days=1)).date()
    
    logger.info(f"Running daily aggregation for {target_day}")
    
    async with pool.acquire() as conn:
        # Get all chats
        chats = await conn.fetch("SELECT chat_id FROM groups")
        
        for chat in chats:
            chat_id = chat['chat_id']
            
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
            
            if not stats or not stats['msg_sum'] and not stats['spam_sum']:
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
            top_spammers = await conn.fetch(
                """SELECT user_id, COUNT(*) as cnt
                   FROM spam_signals
                   WHERE chat_id = $1 AND label = 'spam' AND created_at::date = $2
                   GROUP BY user_id
                   ORDER BY cnt DESC LIMIT 5""",
                chat_id, target_day
            )
            top_spammer_ids = [r['user_id'] for r in top_spammers]
            
            # Churn rate: members_left / (members_joined + total_members)
            # Simplified for now
            total_members = await conn.fetchval("SELECT member_count FROM groups WHERE chat_id = $1", chat_id) or 1
            members_left = stats['left_sum'] or 0
            members_joined = stats['join_sum'] or 0
            churn_rate = members_left / (members_joined + total_members) if (members_joined + total_members) > 0 else 0
            
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
