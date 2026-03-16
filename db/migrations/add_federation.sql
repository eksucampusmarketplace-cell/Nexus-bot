-- ============================================
-- TrustNet (Federation) Migration v21
-- ============================================

-- Federations table
CREATE TABLE IF NOT EXISTS federations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    invite_code TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    log_channel_id BIGINT,
    settings JSONB DEFAULT '{}'::jsonb,
    ban_mode TEXT DEFAULT 'notify'  -- notify, auto, manual
);

-- Federation members (groups in federation)
CREATE TABLE IF NOT EXISTS federation_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    federation_id UUID REFERENCES federations(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    joined_by BIGINT,
    UNIQUE(federation_id, chat_id)
);

-- Federation admins
CREATE TABLE IF NOT EXISTS federation_admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    federation_id UUID REFERENCES federations(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    promoted_by BIGINT,
    promoted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(federation_id, user_id)
);

-- Federation bans (shared across all groups in federation)
CREATE TABLE IF NOT EXISTS federation_bans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    federation_id UUID REFERENCES federations(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    reason TEXT,
    banned_by BIGINT NOT NULL,
    banned_at TIMESTAMPTZ DEFAULT NOW(),
    silent BOOLEAN DEFAULT FALSE,
    UNIQUE(federation_id, user_id)
);

-- Federation ban actions log
CREATE TABLE IF NOT EXISTS federation_ban_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    federation_id UUID REFERENCES federations(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    action TEXT NOT NULL,  -- ban, unban, silent_ban
    performed_by BIGINT NOT NULL,
    performed_at TIMESTAMPTZ DEFAULT NOW(),
    reason TEXT,
    target_chat_id BIGINT
);

-- Federation appeals
CREATE TABLE IF NOT EXISTS federation_appeals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    federation_id UUID REFERENCES federations(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_by BIGINT,
    reviewed_at TIMESTAMPTZ
);

-- Federation reputation/trust scores
CREATE TABLE IF NOT EXISTS federation_reputation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    federation_id UUID REFERENCES federations(id) ON DELETE CASCADE,
    score INTEGER DEFAULT 50,  -- 0-100
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, federation_id)
);

-- Federation trust events (for audit trail)
CREATE TABLE IF NOT EXISTS federation_trust_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    federation_id UUID REFERENCES federations(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    event_type TEXT NOT NULL,  -- warn, ban, kick, mute, good_behavior, appeal
    points_delta INTEGER NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    source_chat_id BIGINT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_federations_owner ON federations(owner_id);
CREATE INDEX IF NOT EXISTS idx_federations_invite ON federations(invite_code);
CREATE INDEX IF NOT EXISTS idx_federation_members_fed ON federation_members(federation_id);
CREATE INDEX IF NOT EXISTS idx_federation_members_chat ON federation_members(chat_id);
CREATE INDEX IF NOT EXISTS idx_federation_bans_fed ON federation_bans(federation_id);
CREATE INDEX IF NOT EXISTS idx_federation_bans_user ON federation_bans(user_id);
CREATE INDEX IF NOT EXISTS idx_federation_reputation_user ON federation_reputation(user_id);
CREATE INDEX IF NOT EXISTS idx_federation_appeals_fed ON federation_appeals(federation_id);

-- Add persona columns to bots table
ALTER TABLE bots 
    ADD COLUMN IF NOT EXISTS persona_name TEXT,
    ADD COLUMN IF NOT EXISTS persona_tone TEXT DEFAULT 'neutral',  -- warm, professional, strict, playful, neutral
    ADD COLUMN IF NOT EXISTS persona_language TEXT DEFAULT 'en',
    ADD COLUMN IF NOT EXISTS persona_emoji BOOLEAN DEFAULT TRUE;

-- Add persona columns to groups table
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS persona_name TEXT,
    ADD COLUMN IF NOT EXISTS persona_tone TEXT DEFAULT 'neutral',
    ADD COLUMN IF NOT EXISTS persona_language TEXT DEFAULT 'en',
    ADD COLUMN IF NOT EXISTS persona_emoji BOOLEAN DEFAULT TRUE;

-- Owner error notification preferences
-- MOVED to add_error_notifications.sql (Bug #9 fix)
-- CREATE TABLE IF NOT EXISTS owner_error_prefs (...)

-- Error notifications log
-- MOVED to add_error_notifications.sql (Bug #9 fix)
-- CREATE TABLE IF NOT EXISTS error_notifications (...)

-- Index for error notifications
-- MOVED to add_error_notifications.sql (Bug #9 fix)
-- CREATE INDEX IF NOT EXISTS idx_error_notifications_owner ON error_notifications(owner_id);
