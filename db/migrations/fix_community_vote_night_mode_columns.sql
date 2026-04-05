-- ============================================-- Fix: Add missing community_vote and night_mode columns to groups table-- ============================================

-- Community Vote columns (required by api/routes/community_vote.py)
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS community_vote_enabled BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS vote_threshold INTEGER DEFAULT 5,
    ADD COLUMN IF NOT EXISTS vote_timeout INTEGER DEFAULT 10,
    ADD COLUMN IF NOT EXISTS vote_action TEXT DEFAULT 'ban',
    ADD COLUMN IF NOT EXISTS auto_detect_scams BOOLEAN DEFAULT TRUE;

-- Night Mode columns (required by api/routes/night_mode.py)
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS night_mode_enabled BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS night_mode_start TEXT DEFAULT '23:00',
    ADD COLUMN IF NOT EXISTS night_mode_end TEXT DEFAULT '07:00',
    ADD COLUMN IF NOT EXISTS night_mode_tz TEXT DEFAULT 'UTC',
    ADD COLUMN IF NOT EXISTS night_message TEXT,
    ADD COLUMN IF NOT EXISTS morning_message TEXT;
