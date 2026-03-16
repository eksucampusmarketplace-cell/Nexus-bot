-- ── Raid members tracking ─────────────────────────────────────────────────
-- Records individual users who joined during an anti-raid session
-- Note: antiraid_sessions table is created by add_antiraid_captcha.sql

-- Create raid_members table (without foreign key constraint to avoid order issues)
CREATE TABLE IF NOT EXISTS raid_members (
    id         BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL,
    user_id    BIGINT NOT NULL,
    username   TEXT,
    first_name TEXT,
    joined_at  TIMESTAMPTZ DEFAULT NOW(),
    was_banned BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_raid_members_session
    ON raid_members(session_id);

CREATE INDEX IF NOT EXISTS idx_raid_members_user
    ON raid_members(user_id);

-- Add foreign key constraint separately if antiraid_sessions exists
DO $
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables 
               WHERE table_name = 'antiraid_sessions') THEN
        ALTER TABLE raid_members
        DROP CONSTRAINT IF EXISTS fk_raid_members_session;
        
        ALTER TABLE raid_members
        ADD CONSTRAINT fk_raid_members_session
        FOREIGN KEY (session_id) REFERENCES antiraid_sessions(id) ON DELETE CASCADE;
    END IF;
END $;
