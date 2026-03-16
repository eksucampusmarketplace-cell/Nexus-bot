-- ============================================
-- Captcha v2 Migration (10 modes)
-- ============================================

-- Captcha statistics
CREATE TABLE IF NOT EXISTS captcha_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT NOT NULL,
    user_id BIGINT,
    mode TEXT NOT NULL,  -- button, math, emoji, word_scramble, odd_one_out, number_sequence, webapp
    passed BOOLEAN DEFAULT FALSE,
    failed BOOLEAN DEFAULT FALSE,
    attempts INTEGER DEFAULT 0,
    solved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Active captcha challenges
CREATE TABLE IF NOT EXISTS captcha_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    challenge_type TEXT NOT NULL,
    challenge_data JSONB NOT NULL,  -- question, answer, options, etc.
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(chat_id, user_id)
);

-- Add captcha_max_attempts to groups table
ALTER TABLE groups 
    ADD COLUMN IF NOT EXISTS captcha_max_attempts INTEGER DEFAULT 3;

-- Add preferred captcha mode to groups
-- Stored in groups.settings JSONB as: captcha_mode: "button"

-- Indexes
CREATE INDEX IF NOT EXISTS idx_captcha_stats_chat ON captcha_stats(chat_id);
CREATE INDEX IF NOT EXISTS idx_captcha_stats_user ON captcha_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_captcha_challenges_chat ON captcha_challenges(chat_id);
CREATE INDEX IF NOT EXISTS idx_captcha_challenges_expires ON captcha_challenges(expires_at);
