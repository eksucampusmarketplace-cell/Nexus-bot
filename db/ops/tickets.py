"""
db/ops/tickets.py

Database operations for the ticket / support system.

Handles CRUD for tickets, messages, assignments, SLA config,
auto-assignment based on staff workload, and analytics.

Logs prefix: [TICKETS_DB]
"""

import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger("tickets_db")


# ── Ticket CRUD ────────────────────────────────────────────────────────────


async def create_ticket(
    pool,
    chat_id: int,
    creator_id: int,
    creator_name: str,
    subject: str,
    description: str = "",
    priority: str = "normal",
    category: str | None = None,
    bot_message_id: int | None = None,
) -> dict:
    """Create a new support ticket. Returns the created ticket row."""
    # Compute SLA deadlines from config
    sla = await get_sla_config(pool, chat_id, priority)
    now = datetime.now(timezone.utc)
    response_deadline = None
    resolution_deadline = None
    if sla:
        response_deadline = now + timedelta(minutes=sla["response_time_mins"])
        resolution_deadline = now + timedelta(minutes=sla["resolution_time_mins"])

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO tickets
               (chat_id, creator_id, creator_name, subject, description,
                priority, category, bot_message_id,
                sla_response_deadline, sla_resolution_deadline)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
               RETURNING *""",
            chat_id,
            creator_id,
            creator_name,
            subject,
            description,
            priority,
            category,
            bot_message_id,
            response_deadline,
            resolution_deadline,
        )
    ticket = dict(row) if row else {}
    log.info(
        f"[TICKETS_DB] Created ticket #{ticket.get('id')} | chat={chat_id} creator={creator_id}"
    )
    return ticket


async def get_ticket(pool, ticket_id: int) -> dict | None:
    """Get a single ticket by ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
    return dict(row) if row else None


async def get_ticket_by_message(pool, chat_id: int, message_id: int) -> dict | None:
    """Find a ticket by its bot confirmation message ID in a group."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tickets WHERE chat_id = $1 AND bot_message_id = $2",
            chat_id,
            message_id,
        )
    return dict(row) if row else None


async def get_tickets(
    pool,
    chat_id: int,
    status: str | None = None,
    assigned_to: int | None = None,
    priority: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List tickets for a group with optional filters."""
    conditions = ["chat_id = $1"]
    params: list = [chat_id]
    idx = 2

    if status and status != "all":
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if assigned_to is not None:
        conditions.append(f"assigned_to = ${idx}")
        params.append(assigned_to)
        idx += 1
    if priority:
        conditions.append(f"priority = ${idx}")
        params.append(priority)
        idx += 1

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT * FROM tickets
                WHERE {where}
                ORDER BY
                  CASE status
                    WHEN 'escalated' THEN 0
                    WHEN 'open' THEN 1
                    WHEN 'in_progress' THEN 2
                    WHEN 'closed' THEN 3
                  END,
                  CASE priority
                    WHEN 'urgent' THEN 0
                    WHEN 'high' THEN 1
                    WHEN 'normal' THEN 2
                    WHEN 'low' THEN 3
                  END,
                  updated_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params,
        )
    return [dict(r) for r in rows]


async def count_tickets(pool, chat_id: int, status: str | None = None) -> int:
    """Count tickets for a group, optionally filtered by status."""
    if status and status != "all":
        async with pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT COUNT(*) FROM tickets WHERE chat_id = $1 AND status = $2",
                chat_id,
                status,
            )
    else:
        async with pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT COUNT(*) FROM tickets WHERE chat_id = $1",
                chat_id,
            )
    return int(val or 0)


async def update_ticket_status(
    pool, ticket_id: int, status: str, closed_by: int | None = None
) -> bool:
    """Update ticket status. If closing, set closed_at and closed_by."""
    now = datetime.now(timezone.utc)
    if status == "closed":
        async with pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE tickets
                   SET status = $1, closed_at = $2, closed_by = $3, updated_at = $2
                   WHERE id = $4""",
                status,
                now,
                closed_by,
                ticket_id,
            )
    else:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE tickets SET status = $1, updated_at = $2 WHERE id = $3",
                status,
                now,
                ticket_id,
            )
    return "UPDATE 1" in str(result)


async def update_ticket_priority(pool, ticket_id: int, priority: str) -> bool:
    """Update ticket priority and recalculate SLA deadlines."""
    ticket = await get_ticket(pool, ticket_id)
    if not ticket:
        return False

    sla = await get_sla_config(pool, ticket["chat_id"], priority)
    now = datetime.now(timezone.utc)
    response_deadline = None
    resolution_deadline = None
    if sla:
        response_deadline = now + timedelta(minutes=sla["response_time_mins"])
        resolution_deadline = now + timedelta(minutes=sla["resolution_time_mins"])

    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE tickets
               SET priority = $1, sla_response_deadline = $2,
                   sla_resolution_deadline = $3, updated_at = $4
               WHERE id = $5""",
            priority,
            response_deadline,
            resolution_deadline,
            now,
            ticket_id,
        )
    return "UPDATE 1" in str(result)


# ── Assignment ──────────────────────────────────────────────────────────────


async def assign_ticket(
    pool, ticket_id: int, staff_id: int, staff_name: str = "", assigned_by: int | None = None
) -> bool:
    """Assign a ticket to a staff member. Unassigns previous if any."""
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Close previous assignment
            await conn.execute(
                """UPDATE ticket_assignments SET unassigned_at = $1
                   WHERE ticket_id = $2 AND unassigned_at IS NULL""",
                now,
                ticket_id,
            )
            # Create new assignment
            await conn.execute(
                """INSERT INTO ticket_assignments
                   (ticket_id, staff_id, staff_name, assigned_by)
                   VALUES ($1, $2, $3, $4)""",
                ticket_id,
                staff_id,
                staff_name,
                assigned_by,
            )
            # Update ticket
            await conn.execute(
                """UPDATE tickets
                   SET assigned_to = $1, assigned_name = $2,
                       status = CASE WHEN status = 'open' THEN 'in_progress' ELSE status END,
                       updated_at = $3
                   WHERE id = $4""",
                staff_id,
                staff_name,
                now,
                ticket_id,
            )
    log.info(f"[TICKETS_DB] Assigned ticket #{ticket_id} to staff={staff_id}")
    return True


async def auto_assign_ticket(pool, chat_id: int, ticket_id: int) -> int | None:
    """
    Auto-assign ticket to the staff member with the fewest active tickets.
    Returns the assigned staff_id or None if no staff available.
    """
    async with pool.acquire() as conn:
        # Get admins who have handled tickets before in this group
        row = await conn.fetchrow(
            """SELECT ta.staff_id, ta.staff_name, COUNT(t.id) AS active_count
               FROM ticket_assignments ta
               JOIN tickets t ON t.id = ta.ticket_id AND t.chat_id = $1
                   AND t.status IN ('open', 'in_progress')
                   AND ta.unassigned_at IS NULL
               WHERE ta.staff_id IN (
                   SELECT DISTINCT staff_id FROM ticket_assignments
                   WHERE ticket_id IN (SELECT id FROM tickets WHERE chat_id = $1)
               )
               GROUP BY ta.staff_id, ta.staff_name
               ORDER BY active_count ASC
               LIMIT 1""",
            chat_id,
        )

    if row:
        await assign_ticket(pool, ticket_id, row["staff_id"], row["staff_name"])
        return row["staff_id"]
    return None


async def get_staff_workload(pool, chat_id: int) -> list[dict]:
    """Get active ticket count per staff member for a group."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ta.staff_id, ta.staff_name,
                      COUNT(t.id) FILTER (
                        WHERE t.status IN ('open', 'in_progress', 'escalated')
                      ) AS active_tickets,
                      COUNT(t.id) FILTER (WHERE t.status = 'closed') AS closed_tickets
               FROM ticket_assignments ta
               JOIN tickets t ON t.id = ta.ticket_id AND t.chat_id = $1
               WHERE ta.unassigned_at IS NULL
               GROUP BY ta.staff_id, ta.staff_name
               ORDER BY active_tickets DESC""",
            chat_id,
        )
    return [dict(r) for r in rows]


# ── Escalation ──────────────────────────────────────────────────────────────


async def escalate_ticket(pool, ticket_id: int) -> dict | None:
    """
    Escalate a ticket to the next level in the escalation chain.
    Returns updated ticket or None.
    """
    ticket = await get_ticket(pool, ticket_id)
    if not ticket:
        return None

    new_level = ticket["escalation_level"] + 1
    sla = await get_sla_config(pool, ticket["chat_id"], ticket["priority"])

    # Try to find next person in escalation chain
    next_staff_id = None
    if sla and sla.get("escalation_chain"):
        chain = sla["escalation_chain"]
        if new_level - 1 < len(chain):
            next_staff_id = chain[new_level - 1]

    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE tickets
               SET escalation_level = $1, status = 'escalated', updated_at = $2
               WHERE id = $3""",
            new_level,
            now,
            ticket_id,
        )

    # Auto-assign to escalation target if available
    if next_staff_id:
        await assign_ticket(pool, ticket_id, next_staff_id, assigned_by=0)

    # Add system message
    await add_ticket_message(
        pool,
        ticket_id,
        sender_id=0,
        sender_name="System",
        message_text=f"Ticket escalated to level {new_level}",
        is_staff=False,
        is_system=True,
    )

    return await get_ticket(pool, ticket_id)


# ── Messages ────────────────────────────────────────────────────────────────


async def add_ticket_message(
    pool,
    ticket_id: int,
    sender_id: int,
    sender_name: str = "",
    message_text: str = "",
    is_staff: bool = False,
    is_system: bool = False,
) -> dict:
    """Add a message to a ticket thread."""
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO ticket_messages
               (ticket_id, sender_id, sender_name, message_text, is_staff, is_system)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING *""",
            ticket_id,
            sender_id,
            sender_name,
            message_text,
            is_staff,
            is_system,
        )
        # Update ticket's updated_at and first_response_at if staff responds first time
        if is_staff:
            await conn.execute(
                """UPDATE tickets
                   SET updated_at = $1,
                       first_response_at = COALESCE(first_response_at, $1)
                   WHERE id = $2""",
                now,
                ticket_id,
            )
        else:
            await conn.execute(
                "UPDATE tickets SET updated_at = $1 WHERE id = $2",
                now,
                ticket_id,
            )
    return dict(row) if row else {}


async def get_ticket_messages(pool, ticket_id: int, limit: int = 100) -> list[dict]:
    """Get messages for a ticket thread, oldest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM ticket_messages
               WHERE ticket_id = $1
               ORDER BY created_at ASC
               LIMIT $2""",
            ticket_id,
            limit,
        )
    return [dict(r) for r in rows]


# ── SLA Configuration ──────────────────────────────────────────────────────


async def get_sla_config(pool, chat_id: int, priority: str = "normal") -> dict | None:
    """Get SLA config for a group and priority level."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sla_config WHERE chat_id = $1 AND priority = $2",
            chat_id,
            priority,
        )
    return dict(row) if row else None


async def get_all_sla_configs(pool, chat_id: int) -> list[dict]:
    """Get all SLA configs for a group."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM sla_config WHERE chat_id = $1 ORDER BY priority",
            chat_id,
        )
    return [dict(r) for r in rows]


async def upsert_sla_config(
    pool,
    chat_id: int,
    priority: str,
    response_time_mins: int = 60,
    resolution_time_mins: int = 1440,
    escalation_chain: list | None = None,
    auto_close_hours: int = 48,
) -> dict:
    """Create or update SLA config for a group and priority."""
    import json

    chain_json = json.dumps(escalation_chain or [])
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO sla_config
               (chat_id, priority, response_time_mins, resolution_time_mins,
                escalation_chain, auto_close_hours, updated_at)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
               ON CONFLICT (chat_id, priority) DO UPDATE SET
                 response_time_mins = EXCLUDED.response_time_mins,
                 resolution_time_mins = EXCLUDED.resolution_time_mins,
                 escalation_chain = EXCLUDED.escalation_chain,
                 auto_close_hours = EXCLUDED.auto_close_hours,
                 updated_at = EXCLUDED.updated_at
               RETURNING *""",
            chat_id,
            priority,
            response_time_mins,
            resolution_time_mins,
            chain_json,
            auto_close_hours,
            now,
        )
    return dict(row) if row else {}


# ── Stale Ticket Auto-Close ────────────────────────────────────────────────


async def get_stale_tickets(pool) -> list[dict]:
    """
    Find tickets that should be auto-closed based on SLA auto_close_hours.
    Returns tickets where last activity exceeds the configured auto-close window.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT t.* FROM tickets t
               LEFT JOIN sla_config sc ON sc.chat_id = t.chat_id AND sc.priority = t.priority
               WHERE t.status IN ('open', 'in_progress')
                 AND t.updated_at < NOW() - INTERVAL '1 hour' * COALESCE(sc.auto_close_hours, 48)"""
        )
    return [dict(r) for r in rows]


async def auto_close_stale_tickets(pool) -> int:
    """Auto-close stale tickets. Returns count of closed tickets."""
    stale = await get_stale_tickets(pool)
    count = 0
    now = datetime.now(timezone.utc)
    for ticket in stale:
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE tickets
                   SET status = 'closed', closed_at = $1, closed_by = 0, updated_at = $1
                   WHERE id = $2""",
                now,
                ticket["id"],
            )
        await add_ticket_message(
            pool,
            ticket["id"],
            sender_id=0,
            sender_name="System",
            message_text="Ticket auto-closed due to inactivity.",
            is_staff=False,
            is_system=True,
        )
        count += 1
        log.info(f"[TICKETS_DB] Auto-closed stale ticket #{ticket['id']}")
    return count


# ── Satisfaction Survey ────────────────────────────────────────────────────


async def get_unsurveyed_closed_tickets(pool, min_age_minutes: int = 30) -> list[dict]:
    """Get closed tickets that haven't had a satisfaction survey sent yet."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=min_age_minutes)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM tickets
               WHERE status = 'closed'
                 AND survey_sent = FALSE
                 AND closed_at IS NOT NULL
                 AND closed_at < $1""",
            cutoff,
        )
    return [dict(r) for r in rows]


async def mark_survey_sent(pool, ticket_id: int) -> None:
    """Mark that a satisfaction survey has been sent for a ticket."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tickets SET survey_sent = TRUE WHERE id = $1",
            ticket_id,
        )


async def submit_satisfaction(pool, ticket_id: int, rating: int, comment: str = "") -> bool:
    """Submit a satisfaction rating for a closed ticket."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE tickets
               SET satisfaction_rating = $1, satisfaction_comment = $2
               WHERE id = $3 AND status = 'closed'""",
            rating,
            comment,
            ticket_id,
        )
    return "UPDATE 1" in str(result)


# ── Analytics ──────────────────────────────────────────────────────────────


async def get_ticket_analytics(pool, chat_id: int) -> dict:
    """Get ticket analytics for a group."""
    async with pool.acquire() as conn:
        stats = await conn.fetchrow(
            """SELECT
                 COUNT(*) AS total,
                 COUNT(*) FILTER (WHERE status = 'open') AS open_count,
                 COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_count,
                 COUNT(*) FILTER (WHERE status = 'escalated') AS escalated_count,
                 COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
                 AVG(EXTRACT(EPOCH FROM (closed_at - created_at)) / 3600)
                   FILTER (WHERE status = 'closed'
                     AND closed_at IS NOT NULL) AS avg_resolution_hours,
                 AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 60)
                   FILTER (WHERE first_response_at IS NOT NULL) AS avg_first_response_mins,
                 AVG(satisfaction_rating)
                   FILTER (WHERE satisfaction_rating IS NOT NULL) AS avg_satisfaction,
                 COUNT(*) FILTER (WHERE sla_response_deadline < NOW()
                   AND first_response_at IS NULL
                   AND status IN ('open', 'in_progress')) AS sla_response_breached,
                 COUNT(*) FILTER (WHERE sla_resolution_deadline < NOW()
                   AND status IN ('open', 'in_progress', 'escalated')) AS sla_resolution_breached
               FROM tickets WHERE chat_id = $1""",
            chat_id,
        )
    if not stats:
        return {}

    result = dict(stats)
    # Round floats
    for key in ("avg_resolution_hours", "avg_first_response_mins", "avg_satisfaction"):
        if result.get(key) is not None:
            result[key] = round(float(result[key]), 1)
    return result


# ── Templates ──────────────────────────────────────────────────────────────


async def get_templates(pool, chat_id: int) -> list[dict]:
    """Get all response templates for a group."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM ticket_templates WHERE chat_id = $1 ORDER BY name",
            chat_id,
        )
    return [dict(r) for r in rows]


async def upsert_template(
    pool,
    chat_id: int,
    name: str,
    content: str,
    category: str | None = None,
    created_by: int | None = None,
) -> dict:
    """Create or update a response template."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO ticket_templates (chat_id, name, content, category, created_by)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (chat_id, name) DO UPDATE SET
                 content = EXCLUDED.content,
                 category = EXCLUDED.category
               RETURNING *""",
            chat_id,
            name,
            content,
            category,
            created_by,
        )
    return dict(row) if row else {}


async def delete_template(pool, chat_id: int, name: str) -> bool:
    """Delete a response template."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM ticket_templates WHERE chat_id = $1 AND name = $2",
            chat_id,
            name,
        )
    return "DELETE 1" in str(result)
