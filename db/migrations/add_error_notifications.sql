-- ============================================
-- Error Notifications Migration
-- ============================================
-- Moved from add_federation.sql (Bug #9 fix)
-- Contains all error notification tables

-- Owner error notification preferences
CREATE TABLE IF NOT EXISTS owner_error_prefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id BIGINT NOT NULL,
    error_type TEXT NOT NULL,
    notify_dm BOOLEAN DEFAULT TRUE,
    notify_channel BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(owner_id, error_type)
);

-- Error notifications log (Bug #1 fix: added bot_id column)
CREATE TABLE IF NOT EXISTS error_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id BIGINT NOT NULL,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    bot_id BIGINT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE
);

-- Bug fix: Add bot_id column if table exists but column doesn't (from old migration)
ALTER TABLE error_notifications ADD COLUMN IF NOT EXISTS bot_id BIGINT;

-- Index for error notifications (dedup query - Bug #6)
CREATE INDEX IF NOT EXISTS idx_error_notifications_dedup
    ON error_notifications(owner_id, error_type, bot_id, sent_at);

-- Index for owner lookups
CREATE INDEX IF NOT EXISTS idx_error_notifications_owner 
    ON error_notifications(owner_id);
