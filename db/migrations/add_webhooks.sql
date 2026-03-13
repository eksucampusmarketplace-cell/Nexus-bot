-- Migration: Add Webhooks System
-- Allows groups to configure external webhook integrations

-- Webhook configurations table
CREATE TABLE IF NOT EXISTS webhook_configs (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL REFERENCES groups(chat_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    url TEXT NOT NULL,
    secret TEXT, -- For HMAC signature verification
    events TEXT[] DEFAULT '{}', -- Array of event types to subscribe to
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by BIGINT,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    last_triggered_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(chat_id, name)
);

-- Webhook delivery log for debugging and retry logic
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id SERIAL PRIMARY KEY,
    webhook_id INTEGER NOT NULL REFERENCES webhook_configs(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    delivery_duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success BOOLEAN DEFAULT FALSE
);

-- Index for efficient querying
CREATE INDEX IF NOT EXISTS idx_webhook_configs_chat_id ON webhook_configs(chat_id);
CREATE INDEX IF NOT EXISTS idx_webhook_configs_active ON webhook_configs(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_created_at ON webhook_deliveries(created_at);

-- Predefined event types documentation (for reference)
-- member_join: New member joins the group
-- member_leave: Member leaves or is removed
-- message: New message (use sparingly, high volume)
-- ban: Member is banned
-- mute: Member is muted
-- warn: Member is warned
-- kick: Member is kicked
-- automod_trigger: Automod takes action
-- report_created: New report submitted
-- settings_change: Group settings modified
