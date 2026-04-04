-- Group Insurance / SLA System

-- Insurance status per group
CREATE TABLE IF NOT EXISTS group_insurance (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'free',
    -- free, basic, premium, enterprise
    active BOOLEAN DEFAULT FALSE,
    auto_lockdown BOOLEAN DEFAULT FALSE,
    -- Automatically lock group on incident
    auto_cleanup BOOLEAN DEFAULT FALSE,
    -- Automatically remove spam/raid members
    max_claims_per_month INTEGER DEFAULT 0,
    claims_used INTEGER DEFAULT 0,
    protection_types TEXT[],
    -- Array: raid, spam, compromise, ddos
    sla_reporting BOOLEAN DEFAULT FALSE,
    -- Send incident reports to admin
    last_incident_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chat_id, bot_id)
);

-- Incident history
CREATE TABLE IF NOT EXISTS insurance_incidents (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    incident_type TEXT NOT NULL,
    -- raid, spam, compromise, ddos
    severity TEXT NOT NULL,
    -- low, medium, high, critical
    details TEXT,
    -- JSON details about incident
    members_removed INTEGER DEFAULT 0,
    members_quarantined INTEGER DEFAULT 0,
    auto_action_taken BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- SLA report configurations per group
CREATE TABLE IF NOT EXISTS sla_reports (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    report_type TEXT NOT NULL,
    -- daily, weekly, monthly
    channels TEXT[],
    -- Array of chat IDs to send reports
    include_incidents BOOLEAN DEFAULT TRUE,
    include_stats BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    last_sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_group_insurance_active ON group_insurance(active, expires_at);
CREATE INDEX IF NOT EXISTS idx_insurance_incidents_chat ON insurance_incidents(chat_id, bot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sla_reports_active ON sla_reports(chat_id, bot_id, is_active);