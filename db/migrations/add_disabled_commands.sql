-- Add disabled_commands column to groups table
-- This column stores a JSON object of command names that are disabled for a group

ALTER TABLE groups ADD COLUMN IF NOT EXISTS disabled_commands JSONB DEFAULT NULL;

-- Create index for faster lookups (optional but helpful for query performance)
CREATE INDEX IF NOT EXISTS idx_groups_disabled_commands ON groups (chat_id) WHERE disabled_commands IS NOT NULL;

COMMENT ON COLUMN groups.disabled_commands IS 'JSON object storing disabled commands for the group, e.g. {"warn": false, "ban": false}';