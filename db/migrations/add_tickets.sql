-- Migration: add_tickets
-- Full ticket/support system with SLA tracking, assignments, and satisfaction surveys

-- Main tickets table
CREATE TABLE IF NOT EXISTS tickets (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT      NOT NULL,
    creator_id      BIGINT      NOT NULL,
    creator_name    TEXT        NOT NULL DEFAULT '',
    assigned_to     BIGINT,
    assigned_name   TEXT,
    subject         TEXT        NOT NULL DEFAULT '',
    description     TEXT        NOT NULL DEFAULT '',
    status          TEXT        NOT NULL DEFAULT 'open',       -- open | in_progress | escalated | closed
    priority        TEXT        NOT NULL DEFAULT 'normal',     -- low | normal | high | urgent
    category        TEXT,
    escalation_level INT       NOT NULL DEFAULT 0,
    sla_response_deadline  TIMESTAMPTZ,
    sla_resolution_deadline TIMESTAMPTZ,
    first_response_at TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    closed_by       BIGINT,
    satisfaction_rating INT,                                   -- 1-5 star rating
    satisfaction_comment TEXT,
    survey_sent     BOOLEAN     NOT NULL DEFAULT FALSE,
    bot_message_id  BIGINT,                                    -- message_id of the ticket confirmation in group
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_chat_id      ON tickets (chat_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status        ON tickets (chat_id, status);
CREATE INDEX IF NOT EXISTS idx_tickets_creator       ON tickets (creator_id);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned      ON tickets (assigned_to);
CREATE INDEX IF NOT EXISTS idx_tickets_priority      ON tickets (chat_id, priority);
CREATE INDEX IF NOT EXISTS idx_tickets_sla_response  ON tickets (sla_response_deadline) WHERE status IN ('open', 'in_progress');
CREATE INDEX IF NOT EXISTS idx_tickets_sla_resolve   ON tickets (sla_resolution_deadline) WHERE status IN ('open', 'in_progress', 'escalated');
CREATE INDEX IF NOT EXISTS idx_tickets_updated       ON tickets (chat_id, updated_at DESC);

-- Ticket messages / conversation thread
CREATE TABLE IF NOT EXISTS ticket_messages (
    id          BIGSERIAL PRIMARY KEY,
    ticket_id   BIGINT      NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    sender_id   BIGINT      NOT NULL,
    sender_name TEXT        NOT NULL DEFAULT '',
    message_text TEXT       NOT NULL DEFAULT '',
    is_staff    BOOLEAN     NOT NULL DEFAULT FALSE,
    is_system   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages (ticket_id, created_at);

-- Assignment history for workload tracking
CREATE TABLE IF NOT EXISTS ticket_assignments (
    id           BIGSERIAL PRIMARY KEY,
    ticket_id    BIGINT      NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    staff_id     BIGINT      NOT NULL,
    staff_name   TEXT        NOT NULL DEFAULT '',
    assigned_by  BIGINT,
    assigned_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unassigned_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ticket_assignments_staff  ON ticket_assignments (staff_id) WHERE unassigned_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ticket_assignments_ticket ON ticket_assignments (ticket_id);

-- SLA configuration per group per priority
CREATE TABLE IF NOT EXISTS sla_config (
    id                  BIGSERIAL PRIMARY KEY,
    chat_id             BIGINT      NOT NULL,
    priority            TEXT        NOT NULL DEFAULT 'normal',
    response_time_mins  INT         NOT NULL DEFAULT 60,
    resolution_time_mins INT        NOT NULL DEFAULT 1440,
    escalation_chain    JSONB       NOT NULL DEFAULT '[]',     -- array of user_ids for escalation
    auto_close_hours    INT         NOT NULL DEFAULT 48,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chat_id, priority)
);

CREATE INDEX IF NOT EXISTS idx_sla_config_chat ON sla_config (chat_id);

-- Response templates for staff
CREATE TABLE IF NOT EXISTS ticket_templates (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT      NOT NULL,
    name        TEXT        NOT NULL,
    content     TEXT        NOT NULL,
    category    TEXT,
    created_by  BIGINT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chat_id, name)
);

CREATE INDEX IF NOT EXISTS idx_ticket_templates_chat ON ticket_templates (chat_id);
