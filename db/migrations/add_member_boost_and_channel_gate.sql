-- Migration: Add member boost records and channel gate tables
-- These tables are required for the member boost system and channel verification features

-- Member boost records for tracking invite requirements
CREATE TABLE IF NOT EXISTS member_boost_records (
    id SERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT,
    first_name TEXT,
    invite_link TEXT,
    invite_link_name TEXT,
    required_count INTEGER DEFAULT 0,
    invited_count INTEGER DEFAULT 0,
    manual_credits INTEGER DEFAULT 0,
    join_source TEXT DEFAULT 'unknown',
    is_unlocked BOOLEAN DEFAULT FALSE,
    is_restricted BOOLEAN DEFAULT FALSE,
    is_exempted BOOLEAN DEFAULT FALSE,
    exempted_by BIGINT,
    exemption_reason TEXT,
    unlocked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_boost_records_group ON member_boost_records(group_id);
CREATE INDEX IF NOT EXISTS idx_boost_records_user ON member_boost_records(group_id, user_id);
CREATE INDEX IF NOT EXISTS idx_boost_records_restricted ON member_boost_records(group_id, is_restricted, is_unlocked);

-- Member invite events for tracking who invited whom
CREATE TABLE IF NOT EXISTS member_invite_events (
    id SERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL,
    inviter_user_id BIGINT NOT NULL,
    invited_user_id BIGINT NOT NULL,
    invited_username TEXT,
    invited_first_name TEXT,
    invite_link TEXT,
    source TEXT DEFAULT 'link',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_id, invited_user_id)
);

CREATE INDEX IF NOT EXISTS idx_invite_events_group ON member_invite_events(group_id);
CREATE INDEX IF NOT EXISTS idx_invite_events_inviter ON member_invite_events(group_id, inviter_user_id);

-- Force channel records for channel verification gate
CREATE TABLE IF NOT EXISTS force_channel_records (
    id SERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT,
    channel_id BIGINT,
    is_verified BOOLEAN DEFAULT FALSE,
    is_restricted BOOLEAN DEFAULT FALSE,
    check_count INTEGER DEFAULT 0,
    verified_at TIMESTAMPTZ,
    last_checked TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_records_group ON force_channel_records(group_id);
CREATE INDEX IF NOT EXISTS idx_channel_records_user ON force_channel_records(group_id, user_id);
CREATE INDEX IF NOT EXISTS idx_channel_records_unverified ON force_channel_records(group_id, is_verified);

-- Manual add credits requests
CREATE TABLE IF NOT EXISTS manual_add_credits (
    id SERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL,
    claimant_user_id BIGINT NOT NULL,
    claimant_username TEXT,
    claimed_count INTEGER DEFAULT 1,
    claimed_user_ids JSONB DEFAULT '[]',
    status TEXT DEFAULT 'pending',
    approved_count INTEGER DEFAULT 0,
    reviewed_by BIGINT,
    review_note TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_manual_adds_group ON manual_add_credits(group_id);
CREATE INDEX IF NOT EXISTS idx_manual_adds_pending ON manual_add_credits(group_id, status);

-- Manual adds detected (users added without invite link)
CREATE TABLE IF NOT EXISTS manual_adds_detected (
    id SERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL,
    added_user_id BIGINT NOT NULL,
    added_username TEXT,
    added_first_name TEXT,
    added_by_user_id BIGINT,
    credited_to BIGINT,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_id, added_user_id)
);

CREATE INDEX IF NOT EXISTS idx_manual_detected_group ON manual_adds_detected(group_id);
CREATE INDEX IF NOT EXISTS idx_manual_detected_uncredited ON manual_adds_detected(group_id, credited_to);
