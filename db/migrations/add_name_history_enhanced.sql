-- ============================================
-- Name History Enhanced Migration v22
-- Adds federation support and profile photo tracking
-- ============================================

-- Add is_federated column to user_name_history
ALTER TABLE user_name_history 
    ADD COLUMN IF NOT EXISTS is_federated BOOLEAN DEFAULT FALSE;

-- Add profile photo tracking table
CREATE TABLE IF NOT EXISTS user_photo_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    photo_id TEXT,
    photo_url TEXT,
    photo_hash TEXT,  -- For detecting changes without storing images
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    source_chat_id BIGINT,
    is_federated BOOLEAN DEFAULT FALSE
);

-- Add user_snapshots composite unique constraint if not exists
-- (ensures one snapshot per user per chat)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_user_snapshots_unique'
    ) THEN
        CREATE UNIQUE INDEX idx_user_snapshots_unique 
        ON user_snapshots(user_id, source_chat_id);
    END IF;
EXCEPTION WHEN duplicate_table THEN
    NULL;
END $$;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_name_history_federated ON user_name_history(is_federated) WHERE is_federated = TRUE;
CREATE INDEX IF NOT EXISTS idx_photo_history_user ON user_photo_history(user_id);
CREATE INDEX IF NOT EXISTS idx_photo_history_changed ON user_photo_history(changed_at);

-- Add change_type column to user_name_history for better filtering
ALTER TABLE user_name_history 
    ADD COLUMN IF NOT EXISTS change_type TEXT DEFAULT 'name';

-- Update existing records to set change_type based on what changed
UPDATE user_name_history 
SET change_type = CASE
    WHEN old_username IS NOT NULL AND old_first_name IS NULL AND old_last_name IS NULL THEN 'username'
    WHEN old_username IS NOT NULL AND (old_first_name IS NOT NULL OR old_last_name IS NOT NULL) THEN 'both'
    ELSE 'name'
END
WHERE change_type = 'name';
