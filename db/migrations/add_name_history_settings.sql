-- ============================================
-- Add Name History Settings to Groups Table
-- ============================================

-- Add name history tracking columns to groups table
ALTER TABLE groups ADD COLUMN IF NOT EXISTS name_history_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS name_history_limit INTEGER DEFAULT 10;

-- Ensure user_name_history table exists before altering it
-- (handles case where this migration runs before add_sangmata_nightmode.sql)
CREATE TABLE IF NOT EXISTS user_name_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    source_chat_id BIGINT,
    snapshot_id UUID
);

-- Update user_name_history table to track old and new names properly
ALTER TABLE user_name_history ADD COLUMN IF NOT EXISTS old_first_name TEXT;
ALTER TABLE user_name_history ADD COLUMN IF NOT EXISTS old_last_name TEXT;
ALTER TABLE user_name_history ADD COLUMN IF NOT EXISTS old_username TEXT;
