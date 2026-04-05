-- ============================================
-- Announcement Channel Settings Migration
-- Adds columns for linked announcement channel integration
-- ============================================

-- Add announcement channel settings columns to groups table
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS announcement_channel_id BIGINT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS announcement_notifications BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS announcement_auto_pin BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS announcement_auto_delete_mins INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS announcement_restrict_replies BOOLEAN DEFAULT FALSE;

-- Add index for efficient lookup by announcement channel
CREATE INDEX IF NOT EXISTS idx_groups_announcement_channel
    ON groups (announcement_channel_id) WHERE announcement_channel_id IS NOT NULL;
