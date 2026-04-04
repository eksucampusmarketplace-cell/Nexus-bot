-- ============================================
-- Add Name History Settings to Groups Table
-- ============================================

-- Add name history tracking columns to groups table
ALTER TABLE groups ADD COLUMN IF NOT EXISTS name_history_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS name_history_limit INTEGER DEFAULT 10;

-- Update user_name_history table to track old and new names properly
ALTER TABLE user_name_history ADD COLUMN IF NOT EXISTS old_first_name TEXT;
ALTER TABLE user_name_history ADD COLUMN IF NOT EXISTS old_last_name TEXT;
ALTER TABLE user_name_history ADD COLUMN IF NOT EXISTS old_username TEXT;
