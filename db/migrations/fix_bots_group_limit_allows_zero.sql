-- ── Fix bots group_limit to allow 0 for unlimited ───────────────────────────────
-- Issue: CHECK constraint only allowed 1-20, but 0 is used for "unlimited"
-- This caused clone registration to fail when user selected "∞ Unlimited"
-- IDEMPOTENT - safe to run multiple times

-- Drop the old constraint
ALTER TABLE bots DROP CONSTRAINT IF EXISTS bots_group_limit_check;

-- Add new constraint allowing 0 (unlimited) and 1-20
ALTER TABLE bots ADD CONSTRAINT bots_group_limit_check
    CHECK (group_limit BETWEEN 0 AND 20);
