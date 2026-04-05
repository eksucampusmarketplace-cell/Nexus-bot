-- ============================================
-- Name History Retention Period Migration (F-06)
-- Adds column for auto-purging old name history
-- ============================================

-- Add retention period column to groups table
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS name_history_retention_days INTEGER DEFAULT 0;

-- Comment: 0 = never purge, 30 = 30 days, 90 = 90 days, 180 = 6 months, 365 = 1 year
