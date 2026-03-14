-- Fix bots_group_limit_check to allow 0 (unlimited) for primary bots
-- The previous constraint was: CHECK (group_limit BETWEEN 1 AND 20)
-- Now allows: 0 (unlimited for primary bots) or 1-20 (for clone bots)

-- First, drop the existing check constraint
ALTER TABLE bots DROP CONSTRAINT IF EXISTS bots_group_limit_check;

-- Add the corrected check constraint that allows 0
ALTER TABLE bots ADD CONSTRAINT bots_group_limit_check CHECK (group_limit BETWEEN 0 AND 20);
