-- Migration: Fix music_settings columns and add rotation support
-- Also adds play_count columns for userbot usage tracking

-- Add missing columns to music_settings with IF NOT EXISTS guards
-- These columns may be missing due to FK constraint failures during original migration
ALTER TABLE music_settings
    ADD COLUMN IF NOT EXISTS userbot_id BIGINT,
    ADD COLUMN IF NOT EXISTS volume INTEGER DEFAULT 100,
    ADD COLUMN IF NOT EXISTS rotation_mode TEXT DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS auto_rotate BOOLEAN DEFAULT FALSE;

-- Add comment explaining the columns
COMMENT ON COLUMN music_settings.userbot_id IS 'Assigned userbot for this chat - plain bigint, no FK constraint to avoid deployment issues';
COMMENT ON COLUMN music_settings.volume IS 'Default volume level (0-200)';
COMMENT ON COLUMN music_settings.rotation_mode IS 'Rotation strategy: manual, round_robin, least_used, random';
COMMENT ON COLUMN music_settings.auto_rotate IS 'Whether to automatically rotate between available userbots';

-- Add play_count columns to track userbot usage
ALTER TABLE music_userbots
    ADD COLUMN IF NOT EXISTS play_count INTEGER DEFAULT 0;

ALTER TABLE music_userbot_assignments
    ADD COLUMN IF NOT EXISTS play_count INTEGER DEFAULT 0;

COMMENT ON COLUMN music_userbots.play_count IS 'Total number of plays using this userbot';
COMMENT ON COLUMN music_userbot_assignments.play_count IS 'Number of plays using this userbot for this specific chat';

-- Create index for efficient rotation queries
CREATE INDEX IF NOT EXISTS idx_music_userbots_usage ON music_userbots(owner_bot_id, is_active, play_count);
CREATE INDEX IF NOT EXISTS idx_music_userbots_last_used ON music_userbots(owner_bot_id, is_active, last_used_at);
