-- ── Raid members tracking ─────────────────────────────────────────────────
-- Records individual users who joined during an anti-raid session
-- Note: antiraid_sessions table is created by add_antiraid_captcha.sql
-- v22 FIX: Made idempotent with column existence checks for mixed schema states

-- Create raid_members table only if it doesn't exist
-- If it already exists from add_moderation_v3.sql with different schema, we'll add columns below
CREATE TABLE IF NOT EXISTS raid_members (
    id         BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL,
    user_id    BIGINT NOT NULL,
    username   TEXT,
    first_name TEXT,
    joined_at  TIMESTAMPTZ DEFAULT NOW(),
    was_banned BOOLEAN DEFAULT FALSE
);

-- Add columns if they don't exist (for tables created by older migrations)
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS session_id BIGINT;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS username TEXT;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS first_name TEXT;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS was_banned BOOLEAN DEFAULT FALSE;

-- Also ensure incident_id column exists (for backward compatibility with add_moderation_v3.sql schema)
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS incident_id BIGINT;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS chat_id BIGINT;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS suspicion_score INTEGER DEFAULT 0;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS action_taken TEXT;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS account_age_days INTEGER;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS had_photo BOOLEAN;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS had_bio BOOLEAN;
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS had_username BOOLEAN;

CREATE INDEX IF NOT EXISTS idx_raid_members_session
    ON raid_members(session_id);

CREATE INDEX IF NOT EXISTS idx_raid_members_user
    ON raid_members(user_id);

-- Add foreign key constraint ONLY if both session_id column AND antiraid_sessions table exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'raid_members' AND column_name = 'session_id')
       AND EXISTS (SELECT 1 FROM information_schema.tables 
                   WHERE table_name = 'antiraid_sessions') THEN
        ALTER TABLE raid_members
        DROP CONSTRAINT IF EXISTS fk_raid_members_session;
        
        ALTER TABLE raid_members
        ADD CONSTRAINT fk_raid_members_session
        FOREIGN KEY (session_id) REFERENCES antiraid_sessions(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add FK constraint for incident_id if it exists and raid_incidents table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'raid_members' AND column_name = 'incident_id')
       AND EXISTS (SELECT 1 FROM information_schema.tables 
                   WHERE table_name = 'raid_incidents') THEN
        ALTER TABLE raid_members
        DROP CONSTRAINT IF EXISTS fk_raid_members_incident;
        
        ALTER TABLE raid_members
        ADD CONSTRAINT fk_raid_members_incident
        FOREIGN KEY (incident_id) REFERENCES raid_incidents(id) ON DELETE CASCADE;
    END IF;
END $$;
