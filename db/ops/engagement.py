"""
db/ops/engagement.py

Database operations for the engagement system:
- XP & Levels
- Reputation
- Badges
- Newsletter
- Network
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)


# ── XP Operations ────────────────────────────────────────────────────────────


async def get_member_xp(pool, chat_id: int, user_id: int, bot_id: int) -> dict:
    """Get XP data for a member."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM member_xp
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
            """,
            chat_id,
            user_id,
            bot_id,
        )

        if row:
            return {
                "xp": row["xp"],
                "level": row["level"],
                "total_messages": row["total_messages"],
                "streak_days": row["streak_days"],
                "last_daily_checkin": row["last_daily_checkin"],
            }
        return {"xp": 0, "level": 1, "total_messages": 0, "streak_days": 0}


async def upsert_member_xp(
    pool, chat_id: int, user_id: int, bot_id: int, xp_delta: int = 0, level: int = None
) -> dict:
    """Update or insert member XP."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO member_xp (chat_id, user_id, bot_id, xp, level, last_xp_at)
            VALUES ($1, $2, $3, $4, COALESCE($5, 1), NOW())
            ON CONFLICT (chat_id, user_id, bot_id)
            DO UPDATE SET
                xp = member_xp.xp + $4,
                level = COALESCE($5, member_xp.level),
                last_xp_at = NOW()
            RETURNING xp, level
            """,
            chat_id,
            user_id,
            bot_id,
            xp_delta,
            level,
        )
        return {"xp": row["xp"], "level": row["level"]}


async def get_xp_leaderboard(
    pool, chat_id: int, bot_id: int, limit: int = 10, offset: int = 0
) -> list:
    """Get XP leaderboard for a group."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, xp, level,
                   ROW_NUMBER() OVER (ORDER BY level DESC, xp DESC) as rank
            FROM member_xp
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY level DESC, xp DESC
            LIMIT $3 OFFSET $4
            """,
            chat_id,
            bot_id,
            limit,
            offset,
        )
        return [dict(r) for r in rows]


async def get_xp_settings(pool, chat_id: int, bot_id: int) -> dict:
    """Get XP settings for a group."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM xp_settings
            WHERE chat_id=$1 AND bot_id=$2
            """,
            chat_id,
            bot_id,
        )

        if row:
            return dict(row)

        return {
            "enabled": True,
            "xp_per_message": 1,
            "xp_per_daily": 10,
            "message_cooldown_s": 60,
            "level_up_announce": True,
        }


async def upsert_xp_settings(pool, chat_id: int, bot_id: int, **settings) -> dict:
    """Update XP settings for a group."""
    async with pool.acquire() as conn:
        # Build dynamic query
        fields = []
        values = []
        for k, v in settings.items():
            fields.append(f"{k} = ${len(values) + 3}")
            values.append(v)

        if not fields:
            return await get_xp_settings(pool, chat_id, bot_id)

        query = f"""
            INSERT INTO xp_settings (chat_id, bot_id, {', '.join(settings.keys())})
            VALUES ($1, $2, {', '.join(f'${i+3}' for i in range(len(values)))})
            ON CONFLICT (chat_id, bot_id)
            DO UPDATE SET {', '.join(fields)}
        """

        await conn.execute(query, chat_id, bot_id, *values)
        return await get_xp_settings(pool, chat_id, bot_id)


async def log_xp_transaction(
    pool, chat_id: int, user_id: int, bot_id: int, amount: int, reason: str, given_by: int = None
):
    """Log an XP transaction."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO xp_transactions
                (chat_id, user_id, bot_id, amount, reason, given_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            chat_id,
            user_id,
            bot_id,
            amount,
            reason,
            given_by,
        )


async def get_xp_history(pool, chat_id: int, user_id: int, bot_id: int, limit: int = 20) -> list:
    """Get XP transaction history for a member."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM xp_transactions
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
            ORDER BY created_at DESC
            LIMIT $4
            """,
            chat_id,
            user_id,
            bot_id,
            limit,
        )
        return [dict(r) for r in rows]


async def get_level_config(pool, chat_id: int, bot_id: int) -> list:
    """Get level configuration for a group."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM level_config
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY level
            """,
            chat_id,
            bot_id,
        )
        return [dict(r) for r in rows]


async def upsert_level_config(pool, chat_id: int, bot_id: int, level: int, **config) -> dict:
    """Update level configuration."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO level_config
                (chat_id, bot_id, level, xp_required, title, unlock_description)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (chat_id, bot_id, level)
            DO UPDATE SET
                xp_required = COALESCE($4, level_config.xp_required),
                title = COALESCE($5, level_config.title),
                unlock_description = COALESCE($6, level_config.unlock_description)
            """,
            chat_id,
            bot_id,
            level,
            config.get("xp_required"),
            config.get("title"),
            config.get("unlock_description"),
        )
        return await get_level_config(pool, chat_id, bot_id)


async def get_level_rewards(pool, chat_id: int, bot_id: int, level: int) -> list:
    """Get rewards for a specific level."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM level_rewards
            WHERE chat_id=$1 AND bot_id=$2 AND level=$3 AND is_active=TRUE
            """,
            chat_id,
            bot_id,
            level,
        )
        return [dict(r) for r in rows]


async def add_level_reward(
    pool, chat_id: int, bot_id: int, level: int, reward_type: str, reward_value: str
) -> bool:
    """Add a reward for a level."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO level_rewards
                (chat_id, bot_id, level, reward_type, reward_value)
            VALUES ($1, $2, $3, $4, $5)
            """,
            chat_id,
            bot_id,
            level,
            reward_type,
            reward_value,
        )
        return True


# ── Reputation Operations ────────────────────────────────────────────────────


async def get_member_rep(pool, chat_id: int, user_id: int, bot_id: int) -> dict:
    """Get reputation for a member."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM member_reputation
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
            """,
            chat_id,
            user_id,
            bot_id,
        )

        if row:
            return {
                "rep_score": row["rep_score"],
                "total_given": row["total_given"],
                "total_received": row["total_received"],
            }
        return {"rep_score": 0, "total_given": 0, "total_received": 0}


async def update_rep(
    pool, chat_id: int, from_id: int, to_id: int, bot_id: int, amount: int, reason: str = None
) -> dict:
    """Update reputation between users."""
    async with pool.acquire() as conn:
        # Log transaction
        await conn.execute(
            """
            INSERT INTO rep_transactions
                (chat_id, from_user_id, to_user_id, bot_id, amount, reason)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            chat_id,
            from_id,
            to_id,
            bot_id,
            amount,
            reason,
        )

        # Update receiver
        row = await conn.fetchrow(
            """
            INSERT INTO member_reputation
                (chat_id, user_id, bot_id, rep_score, total_received)
            VALUES ($1, $2, $3, $4, $4)
            ON CONFLICT (chat_id, user_id, bot_id)
            DO UPDATE SET
                rep_score = member_reputation.rep_score + $4,
                total_received = member_reputation.total_received + $4
            RETURNING rep_score
            """,
            chat_id,
            to_id,
            bot_id,
            amount,
        )

        # Update giver
        await conn.execute(
            """
            INSERT INTO member_reputation
                (chat_id, user_id, bot_id, total_given)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (chat_id, user_id, bot_id)
            DO UPDATE SET total_given = member_reputation.total_given + $4
            """,
            chat_id,
            from_id,
            bot_id,
            abs(amount),
        )

        return {"rep_score": row["rep_score"]}


async def get_rep_leaderboard(pool, chat_id: int, bot_id: int, limit: int = 10) -> list:
    """Get reputation leaderboard."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, rep_score, total_received,
                   ROW_NUMBER() OVER (ORDER BY rep_score DESC) as rank
            FROM member_reputation
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY rep_score DESC
            LIMIT $3
            """,
            chat_id,
            bot_id,
            limit,
        )
        return [dict(r) for r in rows]


async def get_daily_rep_count(pool, chat_id: int, user_id: int, bot_id: int, date: date) -> int:
    """Get count of rep given today by a user."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT given_count FROM rep_daily_limits
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3 AND date=$4
            """,
            chat_id,
            user_id,
            bot_id,
            date,
        )
        return row["given_count"] if row else 0


async def increment_daily_rep(pool, chat_id: int, user_id: int, bot_id: int, date: date):
    """Increment daily rep count for a user."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rep_daily_limits
                (chat_id, user_id, bot_id, date, given_count)
            VALUES ($1, $2, $3, $4, 1)
            ON CONFLICT (chat_id, user_id, bot_id, date)
            DO UPDATE SET given_count = rep_daily_limits.given_count + 1
            """,
            chat_id,
            user_id,
            bot_id,
            date,
        )


# ── Badge Operations ─────────────────────────────────────────────────────────


async def get_all_badges(pool, bot_id: int, chat_id: int = None) -> list:
    """Get all badges."""
    async with pool.acquire() as conn:
        if chat_id:
            rows = await conn.fetch(
                """
                SELECT b.*, COUNT(mb.id) as earned_count
                FROM badges b
                LEFT JOIN member_badges mb ON b.id = mb.badge_id
                WHERE b.bot_id=$1 AND (b.chat_id=$2 OR b.chat_id IS NULL)
                GROUP BY b.id
                ORDER BY b.condition_value
                """,
                bot_id,
                chat_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT b.*, COUNT(mb.id) as earned_count
                FROM badges b
                LEFT JOIN member_badges mb ON b.id = mb.badge_id
                WHERE b.bot_id=$1 AND b.chat_id IS NULL
                GROUP BY b.id
                ORDER BY b.condition_value
                """,
                bot_id,
            )
        return [dict(r) for r in rows]


async def get_member_badges(pool, chat_id: int, user_id: int, bot_id: int) -> list:
    """Get badges earned by a member."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.*, mb.earned_at, mb.granted_by
            FROM member_badges mb
            JOIN badges b ON mb.badge_id = b.id
            WHERE mb.chat_id=$1 AND mb.user_id=$2 AND mb.bot_id=$3
            ORDER BY mb.earned_at DESC
            """,
            chat_id,
            user_id,
            bot_id,
        )
        return [dict(r) for r in rows]


async def award_badge(
    pool, chat_id: int, user_id: int, bot_id: int, badge_id: int, granted_by: int = None
):
    """Award a badge to a member."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO member_badges
                (chat_id, user_id, bot_id, badge_id, granted_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING
            """,
            chat_id,
            user_id,
            bot_id,
            badge_id,
            granted_by,
        )


async def has_badge(pool, chat_id: int, user_id: int, bot_id: int, badge_id: int) -> bool:
    """Check if a member has a specific badge."""
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            """
            SELECT COUNT(*) FROM member_badges
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3 AND badge_id=$4
            """,
            chat_id,
            user_id,
            bot_id,
            badge_id,
        )
        return row > 0


async def create_custom_badge(pool, bot_id: int, chat_id: int, **badge_data) -> dict:
    """Create a custom badge."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO badges
                (bot_id, chat_id, name, emoji, description,
                 condition_type, condition_value, is_rare)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            bot_id,
            chat_id,
            badge_data.get("name"),
            badge_data.get("emoji"),
            badge_data.get("description"),
            badge_data.get("condition_type"),
            badge_data.get("condition_value", 0),
            badge_data.get("is_rare", False),
        )
        return {"id": row["id"]} if row else None


async def seed_default_badges(pool, bot_id: int):
    """Seed default badges for a bot."""
    from bot.engagement.badges import DEFAULT_BADGES

    async with pool.acquire() as conn:
        for badge in DEFAULT_BADGES:
            await conn.execute(
                """
                INSERT INTO badges
                    (bot_id, name, emoji, description,
                     condition_type, condition_value)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                """,
                bot_id,
                badge["name"],
                badge["emoji"],
                badge["description"],
                badge["condition_type"],
                badge["condition_value"],
            )


# ── Newsletter Operations ────────────────────────────────────────────────────


async def get_newsletter_config(pool, chat_id: int, bot_id: int) -> dict:
    """Get newsletter configuration."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM newsletter_config
            WHERE chat_id=$1 AND bot_id=$2
            """,
            chat_id,
            bot_id,
        )
        return dict(row) if row else None


async def upsert_newsletter_config(pool, chat_id: int, bot_id: int, **config) -> dict:
    """Update newsletter configuration."""
    async with pool.acquire() as conn:
        fields = []
        values = []
        for k, v in config.items():
            fields.append(f"{k} = ${len(values) + 3}")
            values.append(v)

        if not fields:
            return await get_newsletter_config(pool, chat_id, bot_id)

        query = f"""
            INSERT INTO newsletter_config
                (chat_id, bot_id, {', '.join(config.keys())})
            VALUES ($1, $2, {', '.join(f'${i+3}' for i in range(len(values)))})
            ON CONFLICT (chat_id, bot_id)
            DO UPDATE SET {', '.join(fields)}
        """

        await conn.execute(query, chat_id, bot_id, *values)
        return await get_newsletter_config(pool, chat_id, bot_id)


async def save_newsletter_history(pool, chat_id: int, bot_id: int, message_id: int, stats: dict):
    """Save newsletter to history."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO newsletter_history
                (chat_id, bot_id, message_id, stats_snapshot)
            VALUES ($1, $2, $3, $4)
            """,
            chat_id,
            bot_id,
            message_id,
            stats,
        )


async def get_newsletter_history(pool, chat_id: int, bot_id: int, limit: int = 10) -> list:
    """Get newsletter history."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM newsletter_history
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY sent_at DESC
            LIMIT $3
            """,
            chat_id,
            bot_id,
            limit,
        )
        return [dict(r) for r in rows]


async def get_groups_for_newsletter(pool, day_of_week: int, hour_utc: int) -> list:
    """Get groups that should receive newsletter now."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chat_id, bot_id FROM newsletter_config
            WHERE enabled=TRUE AND send_day=$1 AND send_hour_utc=$2
            """,
            day_of_week,
            hour_utc,
        )
        return [dict(r) for r in rows]


# ── Network Operations ───────────────────────────────────────────────────────


async def create_network(
    pool, name: str, description: str, owner_user_id: int, owner_bot_id: int, invite_code: str
) -> dict:
    """Create a network."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO group_networks
                (name, description, owner_user_id, owner_bot_id, invite_code)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, invite_code
            """,
            name,
            description,
            owner_user_id,
            owner_bot_id,
            invite_code,
        )
        return dict(row) if row else None


async def get_network_by_code(pool, invite_code: str) -> dict:
    """Get network by invite code."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM group_networks
            WHERE invite_code=$1
            """,
            invite_code.upper(),
        )
        return dict(row) if row else None


async def join_network(pool, network_id: int, chat_id: int, bot_id: int) -> bool:
    """Join a network."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO network_members (network_id, chat_id, bot_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            network_id,
            chat_id,
            bot_id,
        )
        await conn.execute(
            """
            UPDATE group_networks
            SET member_count = member_count + 1
            WHERE id=$1
            """,
            network_id,
        )
        return True


async def leave_network(pool, network_id: int, chat_id: int) -> bool:
    """Leave a network."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM network_members
            WHERE network_id=$1 AND chat_id=$2
            """,
            network_id,
            chat_id,
        )
        await conn.execute(
            """
            UPDATE group_networks
            SET member_count = member_count - 1
            WHERE id=$1
            """,
            network_id,
        )
        return True


async def get_chat_networks(pool, chat_id: int) -> list:
    """Get all networks a chat belongs to."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT gn.*, nm.role
            FROM network_members nm
            JOIN group_networks gn ON nm.network_id = gn.id
            WHERE nm.chat_id=$1
            """,
            chat_id,
        )
        return [dict(r) for r in rows]


async def get_network_groups(pool, network_id: int) -> list:
    """Get all groups in a network."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chat_id, bot_id, role, joined_at
            FROM network_members
            WHERE network_id=$1
            """,
            network_id,
        )
        return [dict(r) for r in rows]


async def get_network_leaderboard(pool, network_id: int, limit: int = 20) -> list:
    """Get network leaderboard."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, total_xp, contributing_groups,
                   ROW_NUMBER() OVER (ORDER BY total_xp DESC) as rank
            FROM network_xp
            WHERE network_id=$1
            ORDER BY total_xp DESC
            LIMIT $2
            """,
            network_id,
            limit,
        )
        return [dict(r) for r in rows]


async def sync_network_xp(pool, network_id: int, user_id: int, xp_delta: int):
    """Sync XP to network leaderboard."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO network_xp
                (network_id, user_id, total_xp, contributing_groups)
            VALUES ($1, $2, $3, 1)
            ON CONFLICT (network_id, user_id)
            DO UPDATE SET
                total_xp = network_xp.total_xp + $3,
                last_updated = NOW()
            """,
            network_id,
            user_id,
            xp_delta,
        )


async def log_network_broadcast(
    pool, network_id: int, from_chat_id: int, sent_by: int, message: str
) -> int:
    """Log a network broadcast."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO network_announcements
                (network_id, from_chat_id, sent_by, message_text)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            network_id,
            from_chat_id,
            sent_by,
            message,
        )
        return row["id"] if row else None


async def get_last_broadcast_time(pool, network_id: int) -> datetime:
    """Get time of last broadcast."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT sent_at FROM network_announcements
            WHERE network_id=$1
            ORDER BY sent_at DESC
            LIMIT 1
            """,
            network_id,
        )
        return row["sent_at"] if row else None
