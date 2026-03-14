"""
db/ops/engagement.py

Database operations for the engagement system:
XP, reputation, badges, newsletter, and cross-group networks.
"""

import logging
from datetime import date, datetime
from typing import Optional

log = logging.getLogger("engagement.db")


# ── XP ───────────────────────────────────────────────────────────────────────


async def get_member_xp(pool, chat_id: int, user_id: int, bot_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM member_xp WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3",
            chat_id, user_id, bot_id,
        )
        return dict(row) if row else {}


async def upsert_member_xp(
    pool, chat_id: int, user_id: int, bot_id: int, xp_delta: int, level: int
) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO member_xp (chat_id, user_id, bot_id, xp, level, total_messages, last_xp_at)
            VALUES ($1, $2, $3, GREATEST(0, $4), $5, 1, NOW())
            ON CONFLICT (chat_id, user_id, bot_id) DO UPDATE
            SET xp = GREATEST(0, member_xp.xp + $4),
                level = $5,
                total_messages = member_xp.total_messages + 1,
                last_xp_at = NOW()
            RETURNING *
            """,
            chat_id, user_id, bot_id, xp_delta, level,
        )
        return dict(row) if row else {}


async def update_member_xp_direct(
    pool, chat_id: int, user_id: int, bot_id: int, new_xp: int, new_level: int
) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO member_xp (chat_id, user_id, bot_id, xp, level, last_xp_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (chat_id, user_id, bot_id) DO UPDATE
            SET xp = $4, level = $5, last_xp_at = NOW()
            RETURNING *
            """,
            chat_id, user_id, bot_id, new_xp, new_level,
        )
        return dict(row) if row else {}


async def get_xp_leaderboard(
    pool, chat_id: int, bot_id: int, limit: int = 10, offset: int = 0
) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, xp, level,
                   ROW_NUMBER() OVER (ORDER BY xp DESC) AS rank
            FROM member_xp
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY xp DESC
            LIMIT $3 OFFSET $4
            """,
            chat_id, bot_id, limit, offset,
        )
        return [dict(r) for r in rows]


async def get_member_rank(pool, chat_id: int, user_id: int, bot_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT rank, total_members, xp, level FROM (
                SELECT user_id, xp, level,
                       ROW_NUMBER() OVER (ORDER BY xp DESC) AS rank,
                       COUNT(*) OVER () AS total_members
                FROM member_xp
                WHERE chat_id=$1 AND bot_id=$2
            ) sub WHERE user_id=$3
            """,
            chat_id, bot_id, user_id,
        )
        return dict(row) if row else {}


async def get_xp_settings(pool, chat_id: int, bot_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM xp_settings WHERE chat_id=$1 AND bot_id=$2",
            chat_id, bot_id,
        )
        if row:
            return dict(row)
        return {
            "chat_id": chat_id, "bot_id": bot_id, "enabled": True,
            "xp_per_message": 1, "xp_per_daily": 10, "xp_per_game_win": 5,
            "xp_per_game_play": 1, "xp_admin_grant": 20, "message_cooldown_s": 60,
            "level_up_announce": True, "level_up_message": "🎉 {mention} reached Level {level}! {title}",
            "double_xp_active": False, "double_xp_until": None,
        }


async def upsert_xp_settings(pool, chat_id: int, bot_id: int, **settings) -> dict:
    fields = ", ".join(f"{k}=${i+3}" for i, k in enumerate(settings.keys()))
    values = list(settings.values())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            INSERT INTO xp_settings (chat_id, bot_id, {', '.join(settings.keys())})
            VALUES ($1, $2, {', '.join(f'${i+3}' for i in range(len(settings)))})
            ON CONFLICT (chat_id, bot_id) DO UPDATE
            SET {fields}
            RETURNING *
            """,
            chat_id, bot_id, *values,
        )
        return dict(row) if row else {}


async def log_xp_transaction(
    pool, chat_id: int, user_id: int, bot_id: int,
    amount: int, reason: str, given_by: Optional[int] = None
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO xp_transactions (chat_id, user_id, bot_id, amount, reason, given_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            chat_id, user_id, bot_id, amount, reason, given_by,
        )


async def get_xp_history(
    pool, chat_id: int, user_id: int, bot_id: int, limit: int = 20
) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM xp_transactions
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
            ORDER BY created_at DESC LIMIT $4
            """,
            chat_id, user_id, bot_id, limit,
        )
        return [dict(r) for r in rows]


async def get_level_config(pool, chat_id: int, bot_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM level_config WHERE chat_id=$1 AND bot_id=$2 ORDER BY level",
            chat_id, bot_id,
        )
        return [dict(r) for r in rows]


async def upsert_level_config(
    pool, chat_id: int, bot_id: int, level: int, **config
):
    fields = ", ".join(f"{k}=${i+4}" for i, k in enumerate(config.keys()))
    values = list(config.values())
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO level_config (chat_id, bot_id, level, {', '.join(config.keys())})
            VALUES ($1, $2, $3, {', '.join(f'${i+4}' for i in range(len(config)))})
            ON CONFLICT (chat_id, bot_id, level) DO UPDATE
            SET {fields}
            """,
            chat_id, bot_id, level, *values,
        )


async def get_level_rewards(pool, chat_id: int, bot_id: int, level: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM level_rewards
            WHERE chat_id=$1 AND bot_id=$2 AND level=$3 AND is_active=TRUE
            """,
            chat_id, bot_id, level,
        )
        return [dict(r) for r in rows]


async def add_level_reward(
    pool, chat_id: int, bot_id: int, level: int,
    reward_type: str, reward_value: str
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO level_rewards (chat_id, bot_id, level, reward_type, reward_value)
            VALUES ($1, $2, $3, $4, $5)
            """,
            chat_id, bot_id, level, reward_type, reward_value,
        )


async def update_daily_checkin(
    pool, chat_id: int, user_id: int, bot_id: int, today: date, streak: int
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE member_xp
            SET last_daily_checkin=$4, streak_days=$5
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3
            """,
            chat_id, user_id, bot_id, today, streak,
        )


# ── Reputation ───────────────────────────────────────────────────────────────


async def get_member_rep(pool, chat_id: int, user_id: int, bot_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM member_reputation WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3",
            chat_id, user_id, bot_id,
        )
        return dict(row) if row else {"rep_score": 0, "total_given": 0, "total_received": 0}


async def update_rep(
    pool, chat_id: int, from_id: int, to_id: int,
    bot_id: int, amount: int, reason: Optional[str]
) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO member_reputation (chat_id, user_id, bot_id, rep_score, total_received)
                VALUES ($1, $2, $3, $4, 1)
                ON CONFLICT (chat_id, user_id, bot_id) DO UPDATE
                SET rep_score = member_reputation.rep_score + $4,
                    total_received = member_reputation.total_received + 1
                RETURNING *
                """,
                chat_id, to_id, bot_id, amount,
            )
            await conn.execute(
                """
                INSERT INTO member_reputation (chat_id, user_id, bot_id, total_given)
                VALUES ($1, $2, $3, 1)
                ON CONFLICT (chat_id, user_id, bot_id) DO UPDATE
                SET total_given = member_reputation.total_given + 1
                """,
                chat_id, from_id, bot_id,
            )
            await conn.execute(
                """
                INSERT INTO rep_transactions (chat_id, from_user_id, to_user_id, bot_id, amount, reason)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                chat_id, from_id, to_id, bot_id, amount, reason,
            )
        return dict(row) if row else {}


async def get_rep_leaderboard(pool, chat_id: int, bot_id: int, limit: int = 10) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, rep_score,
                   ROW_NUMBER() OVER (ORDER BY rep_score DESC) AS rank
            FROM member_reputation
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY rep_score DESC LIMIT $3
            """,
            chat_id, bot_id, limit,
        )
        return [dict(r) for r in rows]


async def get_daily_rep_count(
    pool, chat_id: int, user_id: int, bot_id: int, today: date
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT given_count FROM rep_daily_limits
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3 AND date=$4
            """,
            chat_id, user_id, bot_id, today,
        )
        return row["given_count"] if row else 0


async def increment_daily_rep(pool, chat_id: int, user_id: int, bot_id: int, today: date):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rep_daily_limits (chat_id, user_id, bot_id, date, given_count)
            VALUES ($1, $2, $3, $4, 1)
            ON CONFLICT (chat_id, user_id, bot_id, date) DO UPDATE
            SET given_count = rep_daily_limits.given_count + 1
            """,
            chat_id, user_id, bot_id, today,
        )


# ── Badges ───────────────────────────────────────────────────────────────────


async def get_all_badges(pool, bot_id: int, chat_id: Optional[int] = None) -> list:
    async with pool.acquire() as conn:
        if chat_id:
            rows = await conn.fetch(
                "SELECT * FROM badges WHERE bot_id=$1 AND (chat_id IS NULL OR chat_id=$2) ORDER BY id",
                bot_id, chat_id,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM badges WHERE bot_id=$1 AND chat_id IS NULL ORDER BY id",
                bot_id,
            )
        return [dict(r) for r in rows]


async def get_member_badges(pool, chat_id: int, user_id: int, bot_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mb.*, b.name, b.emoji, b.description, b.is_rare
            FROM member_badges mb
            JOIN badges b ON mb.badge_id = b.id
            WHERE mb.chat_id=$1 AND mb.user_id=$2 AND mb.bot_id=$3
            ORDER BY mb.earned_at DESC
            """,
            chat_id, user_id, bot_id,
        )
        return [dict(r) for r in rows]


async def award_badge(
    pool, chat_id: int, user_id: int, bot_id: int,
    badge_id: int, granted_by: Optional[int] = None
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO member_badges (chat_id, user_id, bot_id, badge_id, granted_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING
            """,
            chat_id, user_id, bot_id, badge_id, granted_by,
        )


async def has_badge(pool, chat_id: int, user_id: int, bot_id: int, badge_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM member_badges
            WHERE chat_id=$1 AND user_id=$2 AND bot_id=$3 AND badge_id=$4
            """,
            chat_id, user_id, bot_id, badge_id,
        )
        return row is not None


async def create_custom_badge(pool, bot_id: int, chat_id: Optional[int], **badge_data) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO badges (bot_id, chat_id, name, emoji, description,
                                condition_type, condition_value, is_rare)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            bot_id, chat_id,
            badge_data.get("name"), badge_data.get("emoji"),
            badge_data.get("description"), badge_data.get("condition_type", "manual"),
            badge_data.get("condition_value", 0), badge_data.get("is_rare", False),
        )
        return dict(row) if row else {}


async def seed_default_badges(pool, bot_id: int):
    defaults = [
        ("🌱", "Newcomer", "First message in group", "messages", 1),
        ("💬", "Chatterbox", "Send 100 messages", "messages", 100),
        ("🗣️", "Active", "Send 500 messages", "messages", 500),
        ("📣", "Veteran", "Send 1000 messages", "messages", 1000),
        ("⭐", "Rising Star", "Reach level 5", "level", 5),
        ("🌟", "Star", "Reach level 10", "level", 10),
        ("💫", "Legend", "Reach level 20", "level", 20),
        ("👑", "Elite", "Reach level 50", "level", 50),
        ("🔥", "On Fire", "7 day streak", "streak", 7),
        ("♾️", "Dedicated", "30 day streak", "streak", 30),
        ("💎", "Diamond", "100 day streak", "streak", 100),
        ("👍", "Helpful", "Receive 10 rep", "rep_received", 10),
        ("🏆", "Respected", "Receive 50 rep", "rep_received", 50),
        ("🎮", "Gamer", "Win 10 games", "game_wins", 10),
        ("🎯", "Champion", "Win 50 games", "game_wins", 50),
        ("🤝", "Generous", "Give 20 rep to others", "rep_given", 20),
    ]
    async with pool.acquire() as conn:
        for emoji, name, desc, ctype, cval in defaults:
            await conn.execute(
                """
                INSERT INTO badges (bot_id, name, emoji, description, condition_type, condition_value)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                """,
                bot_id, name, emoji, desc, ctype, cval,
            )


# ── Newsletter ───────────────────────────────────────────────────────────────


async def get_newsletter_config(pool, chat_id: int, bot_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM newsletter_config WHERE chat_id=$1 AND bot_id=$2",
            chat_id, bot_id,
        )
        if row:
            return dict(row)
        return {
            "chat_id": chat_id, "bot_id": bot_id, "enabled": True,
            "send_day": 0, "send_hour_utc": 9,
            "include_top_members": True, "include_top_messages": True,
            "include_new_members": True, "include_leaderboard": True,
            "include_milestones": True, "custom_intro": None,
        }


async def upsert_newsletter_config(pool, chat_id: int, bot_id: int, **config):
    fields = ", ".join(f"{k}=${i+3}" for i, k in enumerate(config.keys()))
    values = list(config.values())
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO newsletter_config (chat_id, bot_id, {', '.join(config.keys())})
            VALUES ($1, $2, {', '.join(f'${i+3}' for i in range(len(config)))})
            ON CONFLICT (chat_id, bot_id) DO UPDATE
            SET {fields}
            """,
            chat_id, bot_id, *values,
        )


async def save_newsletter_history(
    pool, chat_id: int, bot_id: int,
    message_id: Optional[int], stats: dict
):
    import json
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO newsletter_history (chat_id, bot_id, message_id, stats_snapshot)
            VALUES ($1, $2, $3, $4)
            """,
            chat_id, bot_id, message_id, json.dumps(stats),
        )


async def get_newsletter_history(pool, chat_id: int, bot_id: int, limit: int = 10) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM newsletter_history
            WHERE chat_id=$1 AND bot_id=$2
            ORDER BY sent_at DESC LIMIT $3
            """,
            chat_id, bot_id, limit,
        )
        return [dict(r) for r in rows]


async def get_groups_for_newsletter(pool, day_of_week: int, hour_utc: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chat_id, bot_id FROM newsletter_config
            WHERE enabled=TRUE AND send_day=$1 AND send_hour_utc=$2
            """,
            day_of_week, hour_utc,
        )
        return [dict(r) for r in rows]


# ── Network ──────────────────────────────────────────────────────────────────


async def create_network(
    pool, name: str, description: Optional[str],
    owner_user_id: int, owner_bot_id: int
) -> dict:
    import secrets
    invite_code = secrets.token_hex(4).upper()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO group_networks (name, description, owner_user_id, owner_bot_id, invite_code)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            name, description, owner_user_id, owner_bot_id, invite_code,
        )
        return dict(row) if row else {}


async def get_network_by_code(pool, invite_code: str) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM group_networks WHERE invite_code=$1",
            invite_code,
        )
        return dict(row) if row else {}


async def join_network(pool, network_id: int, chat_id: int, bot_id: int) -> bool:
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO network_members (network_id, chat_id, bot_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (network_id, chat_id) DO NOTHING
                """,
                network_id, chat_id, bot_id,
            )
            await conn.execute(
                "UPDATE group_networks SET member_count = member_count + 1 WHERE id=$1",
                network_id,
            )
            return True
        except Exception:
            return False


async def leave_network(pool, network_id: int, chat_id: int) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM network_members WHERE network_id=$1 AND chat_id=$2",
            network_id, chat_id,
        )
        if result != "DELETE 0":
            await conn.execute(
                "UPDATE group_networks SET member_count = GREATEST(0, member_count - 1) WHERE id=$1",
                network_id,
            )
            return True
        return False


async def get_chat_networks(pool, chat_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT gn.*, nm.role FROM group_networks gn
            JOIN network_members nm ON gn.id = nm.network_id
            WHERE nm.chat_id=$1
            """,
            chat_id,
        )
        return [dict(r) for r in rows]


async def get_network_groups(pool, network_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM network_members WHERE network_id=$1",
            network_id,
        )
        return [dict(r) for r in rows]


async def get_network_leaderboard(pool, network_id: int, limit: int = 20) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, total_xp, contributing_groups,
                   ROW_NUMBER() OVER (ORDER BY total_xp DESC) AS rank
            FROM network_xp
            WHERE network_id=$1
            ORDER BY total_xp DESC LIMIT $2
            """,
            network_id, limit,
        )
        return [dict(r) for r in rows]


async def sync_network_xp(pool, network_id: int, user_id: int, xp_delta: int):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO network_xp (network_id, user_id, total_xp, contributing_groups, last_updated)
            VALUES ($1, $2, GREATEST(0, $3), 1, NOW())
            ON CONFLICT (network_id, user_id) DO UPDATE
            SET total_xp = GREATEST(0, network_xp.total_xp + $3),
                last_updated = NOW()
            """,
            network_id, user_id, xp_delta,
        )


async def log_network_broadcast(
    pool, network_id: int, from_chat_id: int,
    sent_by: int, message: str
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO network_announcements
                (network_id, from_chat_id, sent_by, message_text)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            network_id, from_chat_id, sent_by, message,
        )
        return row["id"] if row else 0


async def update_broadcast_delivered(pool, announcement_id: int, count: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE network_announcements SET delivered_to=$2 WHERE id=$1",
            announcement_id, count,
        )


async def get_last_broadcast_time(pool, network_id: int) -> Optional[datetime]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT MAX(sent_at) AS last_sent FROM network_announcements WHERE network_id=$1",
            network_id,
        )
        return row["last_sent"] if row else None


# ── Milestones ───────────────────────────────────────────────────────────────


async def record_milestone(
    pool, chat_id: int, bot_id: int, milestone_type: str, milestone_value: int
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO group_milestones (chat_id, bot_id, milestone_type, milestone_value)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
            """,
            chat_id, bot_id, milestone_type, milestone_value,
        )


async def get_unannounced_milestones(pool, chat_id: int, bot_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM group_milestones
            WHERE chat_id=$1 AND bot_id=$2 AND announced=FALSE
            ORDER BY reached_at
            """,
            chat_id, bot_id,
        )
        return [dict(r) for r in rows]


async def mark_milestone_announced(pool, milestone_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE group_milestones SET announced=TRUE WHERE id=$1",
            milestone_id,
        )
