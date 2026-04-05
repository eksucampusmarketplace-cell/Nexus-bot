-- ============================================
-- Fix user_snapshots unique constraint for per-chat tracking
-- ============================================

-- Drop the existing single-column unique constraint if it exists
ALTER TABLE user_snapshots DROP CONSTRAINT IF EXISTS user_snapshots_user_id_key;

-- Add composite unique index for per-chat user snapshots
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_snapshots_user_chat 
    ON user_snapshots (user_id, source_chat_id);

-- Add covering index for common lookup pattern
CREATE INDEX IF NOT EXISTS idx_user_snapshots_lookup
    ON user_snapshots (user_id, source_chat_id)
    INCLUDE (first_name, last_name, username);