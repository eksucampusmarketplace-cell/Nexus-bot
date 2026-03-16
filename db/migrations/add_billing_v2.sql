-- File: db/migrations/add_billing_v2.sql
--
-- Adds plan tiers, trial system, and billing v2 to Nexus Bot
--
-- Key changes:
-- - Adds plan, plan_expires_at, trial_ends_at, trial_used to bots table
-- - Adds chat_type to groups table (group vs channel)
-- - Creates indexes for efficient plan/property queries
-- - Backfills existing bots with appropriate plan values

-- Bots table additions
ALTER TABLE bots ADD COLUMN IF NOT EXISTS plan VARCHAR DEFAULT 'free';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMPTZ;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS trial_used BOOLEAN DEFAULT FALSE;

-- Groups table addition (track group vs channel)
ALTER TABLE groups ADD COLUMN IF NOT EXISTS chat_type VARCHAR DEFAULT 'group';

-- Index for trial checker
CREATE INDEX IF NOT EXISTS idx_bots_trial
  ON bots(plan, trial_ends_at)
  WHERE plan = 'trial';

-- Index for property count queries
CREATE INDEX IF NOT EXISTS idx_groups_token_hash
  ON groups(bot_token_hash);

-- Backfill existing bots
-- Primary bots get plan='primary' and trial_used=TRUE
UPDATE bots
SET plan = 'primary', trial_used = TRUE
WHERE is_primary = TRUE AND plan IS NULL;

-- Existing clone bots get plan='free' and trial_used=TRUE (they were created before trial system)
UPDATE bots
SET plan = 'free', trial_used = TRUE
WHERE is_primary = FALSE AND plan IS NULL;

-- Add check constraint for plan values
ALTER TABLE bots
ADD CONSTRAINT chk_bot_plan
CHECK (plan IN ('primary', 'free', 'trial', 'trial_expired', 'basic', 'starter', 'pro', 'unlimited'));
