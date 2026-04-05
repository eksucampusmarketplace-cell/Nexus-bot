-- Add forward_bot and forward_channel lock columns
-- These allow granular control over blocking forwarded messages from bots vs channels
-- IDEMPOTENT - safe to run multiple times

-- Add to locks table
ALTER TABLE locks ADD COLUMN IF NOT EXISTS forward_bot BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS forward_channel BOOLEAN DEFAULT FALSE;

-- Add to groups table settings (for API compatibility)
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_forward_bot BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_forward_channel BOOLEAN DEFAULT FALSE;
